# -*- coding: utf-8 -*-
"""F4.3 回归：lint 存量违规的季度棘轮 SLA。

背景：A8/A9/A10/A14（+A13）的存量违规自 2026-09-25 起由
scripts/lint_full_scan_baseline.json 快照 + --full-gate 管住（只减不增）。
缺口是"只减不增"没有时间压力——数字可以无限期停在原地。F4.3 补季度棘轮：
每过一个季度，允许上限至少再降 reduction_pct%（默认 10%）。

断言：
  T1 季度边界与整季度数计算正确
  T2 目标向下取整，保证实际降幅 ≥ pct%（217 → 195 而非 196）
  T3 基线建立当季（quarters=0）不收紧
  T4 过一季后存量高于目标 → 门禁返回 1
  T5 过一季后存量已达目标 → 通过
  T6 基线文件缺 _ratchet 块 → 退化为纯"只减不增"（不误伤）
  T7 write 会把 established 重置为当前季度首日
  T8 仓库真实基线含 _ratchet 且 reduction_pct=10
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import lint_wms_rules as lw  # noqa: E402


# ---------------- T1 季度算术 ----------------

def test_quarter_start():
    assert lw._quarter_start(date(2026, 1, 15)) == date(2026, 1, 1)
    assert lw._quarter_start(date(2026, 3, 31)) == date(2026, 1, 1)
    assert lw._quarter_start(date(2026, 4, 1)) == date(2026, 4, 1)
    assert lw._quarter_start(date(2026, 12, 31)) == date(2026, 10, 1)


def test_quarters_elapsed():
    est = date(2026, 10, 1)
    assert lw._quarters_elapsed(est, date(2026, 11, 15)) == 0  # 当季
    assert lw._quarters_elapsed(est, date(2027, 1, 5)) == 1
    assert lw._quarters_elapsed(est, date(2027, 4, 1)) == 2
    assert lw._quarters_elapsed(est, date(2026, 9, 30)) == 0  # 早于基线 → 夹到 0


# ---------------- T2 目标计算 ----------------

def test_ratchet_target_floor_guarantees_pct_drop():
    # 217 × 0.9 = 195.3 → 195（降 22/217 = 10.14% ≥ 10%）；ceil 会给 196（9.7%）
    assert lw._ratchet_target(217, 1, 10) == 195
    assert lw._ratchet_target(100, 1, 10) == 90
    assert lw._ratchet_target(32, 1, 10) == 28


def test_ratchet_target_zero_quarters_no_tighten():
    assert lw._ratchet_target(217, 0, 10) == 217
    assert lw._ratchet_target(66, 0, 10) == 66


def test_ratchet_target_multi_quarter_compounds():
    # 217 × 0.9² = 175.77 → 175；217 × 0.9³ = 158.19 → 158
    assert lw._ratchet_target(217, 2, 10) == 175
    assert lw._ratchet_target(217, 3, 10) == 158


# ---------------- T3~T6 门禁行为 ----------------

def _write_baseline(root: Path, counts: dict, ratchet: dict | None = None) -> None:
    p = root / lw._FULL_BASELINE_REL
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {"rules": {k: {"count": v} for k, v in counts.items()}}
    if ratchet is not None:
        payload["_ratchet"] = ratchet
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_same_quarter_does_not_tighten(tmp_path):
    """T3：基线当季，存量等于基线 → 通过（不因棘轮误红）。"""
    _write_baseline(tmp_path, {"a9": 217},
                    {"established": "2026-10-01", "reduction_pct": 10})
    results = {"a9": [1] * 217}
    assert lw.check_full_scan_baseline(tmp_path, results, today=date(2026, 11, 1)) == 0


def test_next_quarter_over_target_blocks(tmp_path, capsys):
    """T4：过一季后存量高于季度目标（但仍不超基线）→ 门禁红。"""
    _write_baseline(tmp_path, {"a9": 217},
                    {"established": "2026-10-01", "reduction_pct": 10})
    results = {"a9": [1] * 210}  # 210 < 基线 217，但 > 目标 195
    assert lw.check_full_scan_baseline(tmp_path, results, today=date(2027, 1, 5)) == 1
    out = capsys.readouterr().out
    assert "季度下降目标" in out
    assert "季度棘轮" in out


def test_next_quarter_at_target_passes(tmp_path):
    """T5：过一季后存量已降到目标（≤195）→ 通过。"""
    _write_baseline(tmp_path, {"a9": 217},
                    {"established": "2026-10-01", "reduction_pct": 10})
    results = {"a9": [1] * 195}
    assert lw.check_full_scan_baseline(tmp_path, results, today=date(2027, 1, 5)) == 0


def test_no_ratchet_block_degrades_to_plain_gate(tmp_path):
    """T6：无 _ratchet 块 → 只减不增，不启用季度收紧（向后兼容）。"""
    _write_baseline(tmp_path, {"a9": 217})  # 无棘轮块
    results = {"a9": [1] * 217}
    assert lw.check_full_scan_baseline(tmp_path, results, today=date(2030, 1, 1)) == 0


# ---------------- T7 写入重置起点 ----------------

def test_write_resets_established_to_current_quarter(tmp_path):
    _write_baseline(tmp_path, {"a8": 5},
                    {"established": "2020-01-01", "reduction_pct": 10})
    lw.write_full_scan_baseline(tmp_path, {"a8": 5})
    raw = json.loads((tmp_path / lw._FULL_BASELINE_REL).read_text(encoding="utf-8"))
    expected = lw._quarter_start(date.today()).isoformat()
    assert raw["_ratchet"]["established"] == expected
    assert raw["_ratchet"]["reduction_pct"] == 10


# ---------------- T8 仓库真实基线 ----------------

def test_shipped_baseline_has_ratchet_policy():
    raw = json.loads((ROOT / lw._FULL_BASELINE_REL).read_text(encoding="utf-8"))
    block = raw.get("_ratchet")
    assert isinstance(block, dict), "基线缺少 _ratchet 季度棘轮声明"
    assert block["reduction_pct"] == 10
    # 起点必须是某季度首日，否则季度算术失真
    d = date.fromisoformat(block["established"])
    assert lw._quarter_start(d) == d
