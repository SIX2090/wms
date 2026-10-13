# -*- coding: utf-8 -*-
"""lint staged 取数批量化 + BUG 台账分片读取的回归守护。

## 覆盖的问题

1. **台账分片读取**（F4.4 遗留）：`tests/verify_bug_2026_10_04_00{1,2,3}` 与
   `tests/test_bug_2026_10_05_002` 的 A13「台账登记」断言曾只读
   `WMS_BUG_BASELINE.md` 主文件，而新条目落在 `docs/ledger/bugs/` 分片，
   导致 CI 上 verify-shard-1/2/3 各误报一片「未登记进 WMS_BUG_BASELINE.md」。
   本测试锁死 `tests.ledger_reader` 在三种场景（主文件 / 分片 / 不存在）
   都能给出正确结果。

2. **staged 取数批量化**（性能）：旧 `get_staged_added_lines` 每文件 fork 2 次
   git，全仓 600+ 次子进程使 `lint --rule a11` 耗时 46s，进而把
   `verify_inventory_truth_contract.py`（T10 会 fork 一次该 lint）推到 52s，
   逼近 60s 单文件超时线 → CI 上 rc=124。改为全仓批量取数后降到 1.2s。
   本测试用「子进程 fork 次数」做可观测断言，防止将来退回逐文件取数。

3. **中文路径**（正确性）：批量实现自己解析 `diff --git` 头，必须正确处理
   git 在 `core.quotePath=true` 下的八进制转义。回归症状是「中文文件名被静默
   漏判」——不报违规，看起来一切正常，实际规则对该文件完全失效。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / "scripts" / "lint_wms_rules.py"
sys.path.insert(0, str(ROOT / "scripts"))

import lint_wms_rules as lint  # noqa: E402


# ---------------------------------------------------------------------------
# 1. ledger_reader：台账分片读取
# ---------------------------------------------------------------------------
class TestLedgerReader:
    def test_main_file_content_included(self):
        """主文件（活头部）必须在拼接结果里——含规模统计等消费者依赖的段落。"""
        from tests.ledger_reader import read_bug_baseline

        content = read_bug_baseline()
        assert "WMS BUG 基线" in content, "主文件内容缺失"

    def test_shard_entry_found(self):
        """落在 docs/ledger/bugs/ 分片里的条目必须能被读到（F4.4 后的实际形态）。"""
        from tests.ledger_reader import bug_section_text, read_bug_baseline

        content = read_bug_baseline()
        # BUG-2026-10-04-001 实测只在 entries-2026-10.md 分片，主文件没有
        section = bug_section_text(content, "BUG-2026-10-04-001")
        assert "生效确认" in section, "分片条目的「生效确认」字段应可见"

    def test_main_file_entry_still_found(self):
        """主文件里的老条目同样不能丢（拆分前的存量 ID）。"""
        from tests.ledger_reader import bug_section_text, read_bug_baseline

        content = read_bug_baseline()
        assert "BUG-2026-09-14-031" in content
        bug_section_text(content, "BUG-2026-09-14-031")

    def test_sections_do_not_swallow_neighbours(self):
        """小节切分必须止于下一个 ## ——否则相邻小节被吞并，「生效确认」会张冠李戴。

        反向验证的价值：若实现改成贪婪匹配到 ``\\Z``，本用例必然失败——
        因为那样取到的 section 会包含后续所有条目。
        """
        from tests.ledger_reader import find_bug_section, read_bug_baseline

        content = read_bug_baseline()
        m = find_bug_section(content, "BUG-2026-10-04-001")
        assert m, "应能定位条目"
        section = m.group(0)
        # 一个条目小节里不应出现另一个条目的标题行
        others = re.findall(r"^##[^\n]*BUG-\d{4}-\d{2}-\d{3}", section, re.M)
        assert len(others) <= 1, f"小节吞并了相邻条目：{others[:3]}"

    def test_unknown_id_fails_loudly(self):
        """未登记的 ID 必须抛错并给出排查命令，不能静默返回空串。"""
        from tests.ledger_reader import bug_section_text, read_bug_baseline

        content = read_bug_baseline()
        with pytest.raises(AssertionError, match="query_ledger.py"):
            bug_section_text(content, "BUG-1970-01-001-NOT-EXIST")


# ---------------------------------------------------------------------------
# 2. staged 取数批量化
# ---------------------------------------------------------------------------
class TestStagedIndexBatching:
    def test_subprocess_count_is_constant(self, tmp_path, monkeypatch):
        """问 N 个文件的 staged 行，git fork 次数必须是常数（2），不是 2N。

        这是性能回归的**直接**判据：把 ``subprocess.run`` 换成计数替身，
        逐文件实现会立刻表现为 fork 次数随文件数线性增长。
        """
        calls: list[list[str]] = []
        real_run = subprocess.run

        def counting_run(cmd, *a, **kw):
            calls.append(list(cmd))
            if "diff" in " ".join(cmd):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *a, **kw)

        monkeypatch.setattr(lint.subprocess, "run", counting_run)
        lint.clear_staged_index_cache()

        lint.get_staged_added_lines(tmp_path, tmp_path / "a.py")
        lint.get_staged_added_lines(tmp_path, tmp_path / "b.py")
        lint.get_staged_added_lines(tmp_path, tmp_path / "c.py")
        lint.get_staged_added_lines(tmp_path, tmp_path / "d.py")

        diff_calls = [c for c in calls if "diff" in " ".join(c)]
        assert len(diff_calls) <= 2, (
            f"取数应批量化（至多 2 次 git diff），实际 {len(diff_calls)} 次"
        )
        lint.clear_staged_index_cache()

    def test_pathspec_absent_means_full_repo(self, tmp_path, monkeypatch):
        """批量取数必须**不带** -- pathspec，否则只拿到第一个文件的数据。"""
        seen: list[list[str]] = []
        real_run = subprocess.run

        def spy_run(cmd, *a, **kw):
            seen.append(list(cmd))
            if "diff" in " ".join(cmd):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *a, **kw)

        monkeypatch.setattr(lint.subprocess, "run", spy_run)
        lint.clear_staged_index_cache()
        lint.get_staged_added_lines(tmp_path, tmp_path / "only.py")
        lint.clear_staged_index_cache()

        for cmd in seen:
            if "diff" in " ".join(cmd):
                assert "--" not in cmd, f"批量取数不应带 pathspec：{cmd}"


class TestGitPathUnquoting:
    @pytest.mark.parametrize("raw,expected", [
        ("app/utils.py", "app/utils.py"),
        ('"说明.txt"', "说明.txt"),
        # 带 a/ 前缀时本函数**不**剥前缀（职责分离：前缀由 _strip_side_prefix 处理），
        # 只负责把八进制字节还原成 UTF-8 文本
        (r"a/\350\257\264\346\230\216.txt", "a/说明.txt"),
        ('"a/说明.txt"', "a/说明.txt"),
        ("docs/中文/文件 name.md", "docs/中文/文件 name.md"),
        (r"a/b\303\251.txt", "a/bé.txt"),
    ])
    def test_unquote_handles_forms(self, raw, expected):
        """八进制转义与明文两种形态都必须还原正确（含带空格路径）。

        覆盖「引号包住整段 a/path」与「引号已被正则剥掉」两种入参形态——
        两者在批量实现里都会出现，只处理一种会让其中一条路径静默失效。
        """
        assert lint._unquote_git_path(raw) == expected

    def test_diff_header_three_forms(self):
        """diff --git 头有三种形态都要匹配并取到正确路径。"""
        cases = {
            r'diff --git a/app/utils.py b/app/utils.py': "app/utils.py",
            r'diff --git "a/\350\257\264\346\230\216.txt" "b/\350\257\264\346\230\216.txt"': "说明.txt",
            'diff --git "a/x y.txt" "b/x y.txt"': "x y.txt",
        }
        for header, expected in cases.items():
            m = lint._DIFF_HEADER.match(header)
            assert m, f"未匹配：{header}"
            raw = m.group("qpath_a") or m.group("qpath_b") or m.group("path") or ""
            assert lint._strip_side_prefix(lint._unquote_git_path(raw)) == expected


class TestStagedParsingEquivalence:
    """与逐文件旧实现逐行对照（重构等价性）。

    批量与逐文件是两条独立代码路径，任何一处hunk 解析写错都会让「staged 模式」
    与「--full 模式」对同一文件给出不同判定——那类不一致极难排查，故必须锁死。
    """

    def _old_impl(self, file_path: Path):
        """改造前的逐文件实现（从 git 历史原样复制）。"""
        rel = str(file_path.relative_to(ROOT)).replace("\\", "/")
        r_a = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A", "--", rel],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        if rel in (r_a.stdout or "").split():
            text = file_path.read_text(encoding="utf-8", errors="replace")
            return set(range(1, text.count("\n") + 2))
        r = subprocess.run(
            ["git", "diff", "--cached", "--unified=0", "--", rel],
            cwd=str(ROOT), capture_output=True, text=True, check=False,
        )
        return lint._parse_added_lines_for_file(r.stdout or "")

    def test_matches_old_impl_on_real_repo(self):
        """对真实仓库取一批代表文件，新旧实现结果必须完全一致。

        只在**有 staged 变更**时才有实际判别力（无 staged 时两边都是空集，
        恒等）；因此另外用合成的 diff 文本直接测解析函数本身。
        """
        targets = [
            ROOT / "scripts" / "lint_wms_rules.py",
            ROOT / "app" / "app.py",
            ROOT / "app" / "utils.py",
            ROOT / "AGENTS.md",
            ROOT / "说明.txt",  # 中文路径
            ROOT / "docs" / "ledger" / "bugs" / "INDEX.md",
        ]
        lint.clear_staged_index_cache()
        mismatches = []
        for p in targets:
            if not p.exists():
                continue
            if self._old_impl(p) != lint.get_staged_added_lines(ROOT, p):
                mismatches.append(p.name)
        lint.clear_staged_index_cache()
        assert not mismatches, f"批量与逐文件实现结果不一致：{mismatches}"

    def test_parse_synthetic_hunks(self):
        """合成 diff 文本直接验证 hunk 解析（不依赖暂存区状态，始终有效）。"""
        diff = (
            "diff --git a/app/x.py b/app/x.py\n"
            "--- a/app/x.py\n"
            "+++ b/app/x.py\n"
            "@@ -10,2 +10,3 @@ def f():\n"
            " ctx\n"
            "+added\n"
            "+added2\n"
            "-removed\n"
        )
        assert lint._parse_added_lines_for_file(diff) == {11, 12}

    def test_split_by_file_isolates_entries(self):
        """多文件混排时每文件的行号不能串味。"""
        diff = (
            "diff --git a/a.py b/a.py\n"
            "@@ -1,0 +2,1 @@\n"
            "+x\n"
            "diff --git a/b.py b/b.py\n"
            "@@ -5,0 +6,1 @@\n"
            "+y\n"
        )
        got = lint._split_diff_by_file(diff)
        assert got == {"a.py": {2}, "b.py": {6}}


# ---------------------------------------------------------------------------
# 3. 端到端：lint 结果不变 + 耗时回归
# ---------------------------------------------------------------------------
class TestLintBehaviourUnchanged:
    def test_a11_zero_violations(self):
        """A11 全量扫描仍须 0 违规（取数改造不得改变判定结果）。"""
        r = subprocess.run(
            [sys.executable, str(LINT), "--rule", "a11", "--full-a11"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        )
        out = (r.stdout or "") + (r.stderr or "")
        assert r.returncode == 0, out[-500:]
        assert "总计 0 处违规" in out, out[-300:]

    @pytest.mark.skipif(
        os.environ.get("WMS_SKIP_PERF_ASSERT") == "1",
        reason="性能断言在慢速磁盘/CI 冷缓存下可能误报",
    )
    def test_single_rule_lint_under_timeout_budget(self):
        """单规则 lint 必须远低于 verify 的 60s 单文件超时线。

        改造前为 46s，加上 verify 契约测试自身的 IO 就逼近 60s；
        现在约 1s，留出约 60 倍余量。阈值取 20s——既守住回归，
        又不因 CI runner 偶发慢而误报（真回退到逐文件取数会直接 >40s）。
        """
        import time

        start = time.monotonic()
        r = subprocess.run(
            [sys.executable, str(LINT), "--rule", "a11"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300,
        )
        elapsed = time.monotonic() - start
        assert r.returncode == 0
        assert elapsed < 20, (
            f"lint --rule a11 耗时 {elapsed:.1f}s，逼近 60s 超时线"
            f"（疑似退回逐文件 staged 取数）"
        )