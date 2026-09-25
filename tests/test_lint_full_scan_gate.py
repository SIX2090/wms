# -*- coding: utf-8 -*-
"""BUG-2026-09-25-005：A8/A9/A10/A13/A14 全量棘轮门禁的自测。

背景
----
A8/A9/A10/A13/A14 五条规则内部统一以 `get_staged_added_lines()` 为判据，
拿不到 staged 行就跳过整个文件。CI 是全新 checkout、git 索引里没有任何
staged 变更 → 这五条规则在 CI 里**长期恒为 0 违规、从未真正执行过**。

修复方式：`--full` 用统一机制（把模块级 `get_staged_added_lines` 替换为
`_all_lines`，即"返回全部行号"）把五条规则一起切到全量语义，再用
`--full-gate` 做棘轮比对（存量快照 `scripts/lint_full_scan_baseline.json`，
只减不增）。

本测试文件锁住三件事，防止这道门禁将来被无声破坏：
  1. `set_full_scan_for_staged_rules(True/False)` 能正确切换且可复原（幂等）；
  2. 切换后 `get_staged_added_lines` 真的返回全量行号，而不是空集；
  3. `check_full_scan_baseline` 在"违规数增加"时返回 1、"持平/下降"时返回 0。

第 3 条是核心：一道永远绿灯的门禁比没有门禁更危险，必须用测试证明它会失败。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lint_wms_rules as lw  # noqa: E402


def _load_lint_module():
    """独立加载一份 lint_wms_rules 模块，避免污染其他测试的全局状态。"""
    spec = importlib.util.spec_from_file_location(
        "lint_wms_rules_isolated", str(ROOT / "scripts" / "lint_wms_rules.py")
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


class TestFullScanToggle:
    def test_toggle_on_off_is_reversible(self):
        lw.set_full_scan_for_staged_rules(True)
        try:
            assert lw._FULL_SCAN_ACTIVE is True
            assert lw.get_staged_added_lines is lw._all_lines
        finally:
            lw.set_full_scan_for_staged_rules(False)
        assert lw._FULL_SCAN_ACTIVE is False
        assert lw.get_staged_added_lines is lw._ORIG_GET_STAGED_ADDED_LINES

    def test_toggle_is_idempotent(self):
        # 连续置位两次不应把"原始函数"记成 _all_lines（否则关不掉）
        lw.set_full_scan_for_staged_rules(True)
        lw.set_full_scan_for_staged_rules(True)
        try:
            assert lw.get_staged_added_lines is lw._all_lines
        finally:
            lw.set_full_scan_for_staged_rules(False)
        assert lw.get_staged_added_lines is lw._ORIG_GET_STAGED_ADDED_LINES

    def test_all_lines_returns_every_line(self, tmp_path):
        f = tmp_path / "sample.py"
        f.write_text("a\nb\nc\n", encoding="utf-8")
        lines = lw._all_lines(tmp_path, f)
        # 3 行文本 + 末尾空行 → 至少覆盖 1..3
        assert {1, 2, 3} <= lines

    def test_all_lines_degrades_silently_on_missing_file(self, tmp_path):
        """读不到文件时返回空集，与 get_staged_added_lines 的失败语义一致。"""
        assert lw._all_lines(tmp_path, tmp_path / "nope.py") == set()

    def test_staged_mode_yields_empty_in_fresh_checkout(self, tmp_path):
        """回归本源问题：非 staged 文件在默认模式下得到空集 → 规则静默跳过。

        这正是 CI 里五条规则恒为 0 违规的机制。若将来有人"顺手"把
        get_staged_added_lines 的失败语义改成失败即报错，本断言会提醒他
        重新评估 --full 的必要性。
        """
        f = tmp_path / "notstaged.py"
        f.write_text("x = 1\n", encoding="utf-8")
        assert lw._ORIG_GET_STAGED_ADDED_LINES(tmp_path, f) == set()


class TestFullScanBaseline:
    def _write_baseline(self, root: Path, counts: dict) -> None:
        p = root / lw._FULL_BASELINE_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"rules": {k: {"count": v} for k, v in counts.items()}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_no_regression_passes(self, tmp_path, capsys):
        self._write_baseline(tmp_path, {"a8": 5, "a9": 3, "a10": 2, "a14": 1})
        results = {"a8": [1] * 5, "a9": [1] * 3, "a10": [1] * 2, "a14": [1] * 1}
        assert lw.check_full_scan_baseline(tmp_path, results) == 0

    def test_new_violation_blocks(self, tmp_path, capsys):
        """核心断言：违规数增加必须返回 1（门禁真的会失败）。"""
        self._write_baseline(tmp_path, {"a8": 5, "a9": 3, "a10": 2, "a14": 1})
        results = {"a8": [1] * 6, "a9": [1] * 3, "a10": [1] * 2, "a14": [1] * 1}
        assert lw.check_full_scan_baseline(tmp_path, results) == 1
        out = capsys.readouterr().out
        assert "新增违规" in out
        assert "A8" in out

    def test_decrease_passes_and_hints(self, tmp_path, capsys):
        self._write_baseline(tmp_path, {"a8": 5, "a9": 3, "a10": 2, "a14": 1})
        results = {"a8": [1] * 2, "a9": [1] * 3, "a10": [1] * 2, "a14": [1] * 1}
        assert lw.check_full_scan_baseline(tmp_path, results) == 0
        assert "存量下降" in capsys.readouterr().out

    def test_missing_baseline_treated_as_zero(self, tmp_path):
        """基线文件缺失 → 视作全 0，因此任何违规都算新增（安全默认值）。"""
        results = {"a8": [1], "a9": [], "a10": [], "a14": []}
        assert lw.check_full_scan_baseline(tmp_path, results) == 1

    def test_corrupt_baseline_treated_as_zero(self, tmp_path):
        p = tmp_path / lw._FULL_BASELINE_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{not json", encoding="utf-8")
        results = {"a8": [1], "a9": [], "a10": [], "a14": []}
        assert lw.check_full_scan_baseline(tmp_path, results) == 1

    def test_roundtrip_write_then_check(self, tmp_path):
        """write_full_scan_baseline 写出的基线应能被 check 原值读回（互逆）。"""
        counts = {"a8": 66, "a9": 217, "a10": 102, "a13": 0, "a14": 32}
        lw.write_full_scan_baseline(tmp_path, counts)
        loaded = lw._load_full_scan_baseline(tmp_path)
        for rid, n in counts.items():
            assert loaded.get(rid) == n
        results = {rid: [1] * n for rid, n in counts.items()}
        assert lw.check_full_scan_baseline(tmp_path, results) == 0

    def test_update_baseline_preserves_description(self, tmp_path):
        p = tmp_path / lw._FULL_BASELINE_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(
                {"_comment": ["keep me"], "rules": {"a8": {"count": 1, "description": "desc8"}}},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        lw.write_full_scan_baseline(tmp_path, {"a8": 9})
        raw = json.loads(p.read_text(encoding="utf-8"))
        assert raw["_comment"] == ["keep me"]
        assert raw["rules"]["a8"]["count"] == 9
        assert raw["rules"]["a8"]["description"] == "desc8"


class TestShippedBaselineIsSane:
    """锁住仓库里真实那份基线文件：必须存在、可解析、五条规则齐全。"""

    def test_repo_baseline_exists_and_covers_gate_rules(self):
        path = ROOT / lw._FULL_BASELINE_REL
        assert path.exists(), "CI 依赖的全量扫描基线文件不存在"
        raw = json.loads(path.read_text(encoding="utf-8"))
        rules = raw.get("rules")
        assert isinstance(rules, dict)
        for rid in lw._FULL_GATE_RULES:
            assert rid in rules, f"基线缺少规则 {rid}"
            assert isinstance(rules[rid]["count"], int)

    def test_a13_is_hard_gate_at_zero(self):
        """A13 存量已清零 —— 它应当保持 0，任何新增都会立刻被 CI 拦下。"""
        raw = json.loads((ROOT / lw._FULL_BASELINE_REL).read_text(encoding="utf-8"))
        assert raw["rules"]["a13"]["count"] == 0
