# -*- coding: utf-8 -*-
"""F4.4 台账拆分契约测试：巨型台账 → 「主文件（活头部）+ docs/ledger/ 按月分片 + INDEX」。

验收（修复计划 §5）：
1. 任一任务详情 ≤2 次文件读取可得 → query_ledger.py 走「INDEX 定位 + 分片提取」；
2. git diff 噪声下降 → 主文件不再承载历史记录（体积上限回归锁）；
3. 拆分零丢失 → 条目 ID 集合与拆分前（git HEAD 基线硬编码于本测试）守恒；
4. monthly_bug_review 的状态分布与拆分前逐项一致（315/141/19/1 回归锁）；
5. A13 门禁覆盖分片路径（详见 test_lint_wms_rules_a13_golden.py 的两个分片用例）。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'query_ledger.py'
LEDGER = ROOT / 'docs' / 'ledger'
BUG_SHARDS = LEDGER / 'bugs'
AI_SHARDS = LEDGER / 'ai'

# 拆分时（2026-10-13，HEAD=dbe79410）的守恒基线
AI_TASK_IDS_BASELINE = 83
BUG_IDS_BASELINE = 490
STATUS_DIST_BASELINE = {'fixed': 315, 'unknown': 141, 'deferred': 19, 'false_positive': 1}
# Explicitly verify new registrations while preserving the exact pre-split snapshot.
POST_SPLIT_BUGS = {'BUG-2026-10-14-001': 'fixed', 'BUG-2026-10-15-001': 'fixed',
                   'BUG-2026-10-16-001': 'fixed', 'BUG-2026-10-16-002': 'fixed', 'BUG-2026-10-16-003': 'fixed', 'BUG-2026-10-17-001': 'fixed', 'BUG-2026-10-17-002': 'fixed', 'BUG-2026-10-17-003': 'fixed', 'BUG-2026-10-17-004': 'fixed', 'BUG-2026-10-17-005': 'fixed', 'BUG-2026-10-17-006': 'fixed', 'BUG-2026-10-17-007': 'fixed', 'BUG-2026-10-17-008': 'fixed', 'BUG-2026-10-17-009': 'fixed', 'BUG-2026-10-17-010': 'fixed', 'BUG-2026-10-17-011': 'fixed', 'BUG-2026-10-17-012': 'fixed', 'BUG-2026-10-17-013': 'fixed', 'BUG-2026-10-17-014': 'fixed', 'BUG-2026-10-17-015': 'fixed',
                   'BUG-2026-10-20-001': 'fixed',
                   'BUG-2026-10-20-002': 'fixed',
                   'BUG-2026-10-20-003': 'fixed',
                   'BUG-2026-10-20-004': 'fixed',
                   'BUG-2026-10-20-005': 'fixed',
                   'BUG-2026-10-20-006': 'fixed',
                   'BUG-2026-10-20-007': 'fixed',
                   'BUG-2026-10-20-008': 'fixed',
                   'BUG-2026-10-20-009': 'fixed',
                   'BUG-2026-10-20-010': 'fixed',
                   'BUG-2026-10-21-001': 'open',
                   'BUG-2026-10-21-002': 'fixed',
                   'BUG-2026-10-21-003': 'fixed',
                   'BUG-2026-10-21-004': 'fixed',
                   'BUG-2026-10-21-005': 'fixed',
                   'BUG-2026-10-21-006': 'fixed',
                   'BUG-2026-10-21-007': 'fixed',
                   'BUG-2026-10-21-008': 'fixed',
                   'BUG-2026-10-21-009': 'fixed',
                   'BUG-2026-10-21-010': 'fixed',
                   'BUG-2026-10-21-011': 'fixed',
                   'BUG-2026-10-21-012': 'fixed',
                   'BUG-2026-10-21-013': 'fixed',
                   'BUG-2026-10-21-014': 'fixed',
                   'BUG-2026-10-21-015': 'fixed',
                   'BUG-2026-10-21-016': 'fixed',
                   'BUG-2026-10-21-017': 'fixed',
                   'BUG-2026-10-21-018': 'fixed',
                   'BUG-2026-10-22-001': 'fixed',
                   'BUG-2026-10-22-002': 'fixed',
                   'BUG-2026-10-22-003': 'fixed', 'BUG-2026-10-22-004': 'fixed', 'BUG-2026-10-22-005': 'fixed', 'BUG-2026-10-22-006': 'fixed', 'BUG-2026-10-22-007': 'fixed', 'BUG-2026-10-22-008': 'fixed', 'BUG-2026-10-22-010': 'fixed', 'BUG-2026-10-22-009': 'fixed', 'BUG-2026-10-22-011': 'fixed', 'BUG-2026-10-22-012': 'fixed'}
POST_SPLIT_BUGS['BUG-2026-10-22-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-22-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-23-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-24-021'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-08-014'] = 'fixed'  # monthly parser normalizes repair suffixes
POST_SPLIT_BUGS['BUG-2026-10-25-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-021'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-022'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-023'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-024'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-025'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-25-026'] = 'open'
POST_SPLIT_BUGS['BUG-2026-10-25-027'] = 'open'
POST_SPLIT_BUGS['BUG-2026-10-26-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-26-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-27-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-28-016'] = 'fixed'
# 2026-10-29: register this batch after the split; preserve the original status-distribution assertion.
POST_SPLIT_BUGS['BUG-2026-10-29-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-021'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-022'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-29-023'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-30-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-021'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-022'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-023'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-024'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-025'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-026'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-10-31-027'] = 'fixed'
MAIN_FILE_SIZE_LIMIT_KB = 400  # 两份主文件体积上限（拆分后约 232/263KB）


def _run(args, cwd=ROOT):
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    return subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        cwd=str(cwd), capture_output=True, text=True,
        encoding='utf-8', errors='replace', env=env, timeout=120,
    )


class TestQueryLedgerCli:
    def test_exact_table_row(self):
        """表格行条目：BUG-ID 精确命中，输出分片路径与行内容。"""
        r = _run(['--task', 'BUG-2026-10-05-001'])
        assert r.returncode == 0, r.stdout + r.stderr
        assert 'entries-2026-10.md' in r.stdout
        assert '出库单' in r.stdout  # 标题语义命中

    def test_exact_completion_row(self):
        """完成记录行：F 系任务编号精确命中。"""
        r = _run(['--task', 'F3.14'])
        assert r.returncode == 0, r.stdout + r.stderr
        assert 'completions-2026-10.md' in r.stdout
        assert 'vision' in r.stdout

    def test_section_entry(self):
        """小节条目：无日期历史小节也能命中（records-unknown）。"""
        r = _run(['--task', 'SM-P6-FIX-01'])
        assert r.returncode == 0, r.stdout + r.stderr
        assert 'records-unknown.md' in r.stdout

    def test_ambiguous_prefix_lists_candidates(self):
        """非唯一前缀 → 列候选、退出码 2（不猜）。"""
        r = _run(['--task', 'AI-R0'])
        assert r.returncode == 2, r.returncode
        assert 'AI-R0' in r.stdout  # 候选清单

    def test_unknown_task_fails_loud(self):
        r = _run(['--task', 'NO-SUCH-ID-XYZ'])
        assert r.returncode == 1
        assert '未找到' in r.stdout

    def test_list_shards(self):
        r = _run(['--list'])
        assert r.returncode == 0
        assert 'completions-2026-10.md' in r.stdout
        assert 'entries-2026-09.md' in r.stdout


class TestShardIntegrity:
    def test_unified_index_targets_exist(self):
        """统一索引的每一行都指向真实存在的分片（≤2 次读取的前提）。"""
        index = (LEDGER / 'INDEX.md').read_text(encoding='utf-8')
        rows = [l for l in index.splitlines() if l.startswith('| ') and not l.startswith('| 条目')]
        assert len(rows) > 600
        for line in rows:
            cols = [c.strip() for c in line.split('|')]
            tid, cat, shard = cols[1], cols[2], cols[3]
            assert (LEDGER / cat / shard).exists(), f'索引悬空: {tid} -> {cat}/{shard}'

    def test_main_files_no_longer_carry_history(self):
        """git diff 噪声目标：主文件体积低于上限。"""
        for name in ('WMS_BUG_BASELINE.md', 'WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md'):
            size = (ROOT / name).stat().st_size
            assert size < MAIN_FILE_SIZE_LIMIT_KB * 1024, f'{name} {size // 1024}KB 超限'

    def test_id_conservation(self):
        """拆分零丢失（棘轮）：当前全量 ID 数不低于拆分时基线。

        拆分时（2026-10-13）验证过与拆分前 git HEAD 逐 ID 守恒（83 任务 /
        490 BUG-ID）；此后 HEAD 随新提交推进，本断言固化为「只增不减」棘轮，
        新登记必然增加 ID，丢失会被基线拦下。
        """
        import re
        task_re = re.compile(r'\|\s*([A-Z]+(?:-[A-Z0-9]+)+)\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|')
        bug_re = re.compile(r'(?:BUG|LABEL-FIX)-\d{4}-\d{2}-\d{2}-\d{3}')

        texts = [(ROOT / n).read_text(encoding='utf-8')
                 for n in ('WMS_BUG_BASELINE.md', 'WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md')]
        texts += [p.read_text(encoding='utf-8') for p in LEDGER.rglob('*.md')]
        t, b = set(), set()
        for text in texts:
            t |= set(task_re.findall(text))
            b |= set(bug_re.findall(text))
        assert len(b) >= BUG_IDS_BASELINE, f'BUG-ID 低于基线 {BUG_IDS_BASELINE}: {len(b)}'
        assert len(t) >= AI_TASK_IDS_BASELINE, f'任务 ID 低于基线 {AI_TASK_IDS_BASELINE}: {len(t)}'


class TestMonthlyReviewEquivalence:
    def test_status_distribution_matches_pre_split(self):
        """monthly_bug_review 状态判定与拆分前逐项一致（拼接顺序回归锁）。"""
        sys.path.insert(0, str(ROOT / 'scripts'))
        from monthly_bug_review import _load_baseline_text, build_status_index
        from collections import Counter
        statuses = build_status_index(_load_baseline_text())
        for bug_id, expected_status in POST_SPLIT_BUGS.items():
            assert statuses.pop(bug_id) == expected_status
        dist = Counter(statuses.values())
        assert dict(dist) == STATUS_DIST_BASELINE, dict(dist)

# Reimplemented registrations are verified individually; historical snapshot unchanged.
POST_SPLIT_BUGS['BUG-2026-11-01-001'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-011'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-019'] = 'fixed'  # software fix; exact release CI is recorded separately
POST_SPLIT_BUGS['BUG-2026-11-01-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-021'] = 'fixed'  # history cleanup; deployment acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-01-022'] = 'fixed'  # merge consent; local candidate, not deployed
POST_SPLIT_BUGS['BUG-2026-11-01-023'] = 'fixed'  # failed print stale callback; local only
POST_SPLIT_BUGS['BUG-2026-11-01-024'] = 'fixed'  # browser report; deployment tracked separately
POST_SPLIT_BUGS['BUG-2026-11-01-025'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-026'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-027'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-028'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-01-029'] = 'fixed'  # sales duplicate-number feedback; release tracked separately
POST_SPLIT_BUGS['BUG-2026-11-01-030'] = 'fixed'  # download guide wrapping; real browser evidence in audit
POST_SPLIT_BUGS['BUG-2026-11-01-031'] = 'fixed'  # decimal entry rounding; exact release evidence in audit
POST_SPLIT_BUGS['BUG-2026-11-02-001'] = 'fixed'  # software fix; exact release CI tracked separately
POST_SPLIT_BUGS['BUG-2026-11-02-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-010'] = 'fixed'

POST_SPLIT_BUGS['BUG-2026-11-02-011'] = 'fixed'  # exact duplicate comparison; delivery tracked separately
POST_SPLIT_BUGS['BUG-2026-11-02-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-013'] = 'fixed'  # local software fix; exact release CI tracked separately
POST_SPLIT_BUGS['BUG-2026-11-02-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-02-016'] = 'fixed'  # startup dispatch software fix; real startup/release acceptance pending
POST_SPLIT_BUGS['BUG-2026-11-03-001'] = 'fixed'  # isolated browser report batch; release evidence tracked separately
POST_SPLIT_BUGS['BUG-2026-11-03-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-003'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-004'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-006'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-009'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-010'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-011'] = 'fixed'  # software fix; target CI/deployment tracked separately
POST_SPLIT_BUGS['BUG-2026-11-03-012'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-013'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-014'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-015'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-016'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-017'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-018'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-019'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-020'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-021'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-022'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-023'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-024'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-025'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-026'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-03-027'] = 'fixed'

POST_SPLIT_BUGS['BUG-2026-11-03-101'] = 'fixed'  # local software fix; CI/deployment tracked separately

POST_SPLIT_BUGS['BUG-2026-11-04-101'] = 'fixed'  # software fix; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-102'] = 'fixed'  # software fix; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-103'] = 'fixed'  # software fix; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-104'] = 'fixed'  # software fix; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-105'] = 'fixed'  # software fix; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-106'] = 'fixed'  # fail-closed secret storage; CI/deployment tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-201'] = 'fixed'  # category navigation; CI/deployment tracked separately

POST_SPLIT_BUGS['BUG-2026-11-04-107'] = 'fixed'  # index repair; delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-108'] = 'fixed'  # startup Git timeout; delivery separately tracked

POST_SPLIT_BUGS['BUG-2026-11-04-202'] = 'fixed'  # selected unused archive cleanup; CI/deployment tracked separately

POST_SPLIT_BUGS['BUG-2026-11-04-109'] = 'fixed'  # stale web edits; delivery separately tracked

POST_SPLIT_BUGS['BUG-2026-11-04-110'] = 'fixed'  # software fix; exact delivery separately tracked
POST_SPLIT_BUGS['BUG-2026-11-04-111'] = 'fixed'  # source URI; exact delivery separately tracked

POST_SPLIT_BUGS['BUG-2026-11-04-112'] = 'fixed'  # entry lifecycle;exact delivery separately tracked

POST_SPLIT_BUGS['BUG-2026-11-04-113'] = 'fixed'  # unused dependency; release acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-114'] = 'fixed'  # explicit first install; release acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-115'] = 'fixed'  # package UTF8 preservation; release acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-116'] = 'fixed'  # print navigation permissions; production activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-117'] = 'fixed'  # warehouse-scoped paste; delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-118'] = 'fixed'  # zero-stock filter residue; delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-119'] = 'fixed'  # runtime dependency gate; delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-04-120'] = 'fixed'  # remember-cookie security; delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-05-101'] = 'fixed'  # column settings naming; exact delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-05-102'] = 'fixed'  # blank unknown stock; exact delivery and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-05-001'] = 'fixed'  # independent daily backup; production activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-05-002'] = 'fixed'  # finite process recovery; production activation tracked separately

POST_SPLIT_BUGS['BUG-2026-11-05-003'] = 'fixed'  # signed edits; production separately tracked
POST_SPLIT_BUGS['BUG-2026-11-05-004'] = 'fixed'  # typed document JSON boundaries

POST_SPLIT_BUGS['BUG-2026-11-05-005'] = 'fixed'  # fresh transaction rows for derived totals
POST_SPLIT_BUGS['BUG-2026-11-05-006'] = 'fixed'  # product receipts omit the supplier source picker
POST_SPLIT_BUGS['BUG-2026-11-05-007'] = 'fixed'  # product header resolves the contract master project
POST_SPLIT_BUGS['BUG-2026-11-06-001'] = 'fixed'  # smoke isolation guard; exact CI acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-002'] = 'fixed'  # product detail fields and sorting; production acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-003'] = 'fixed'  # finished goods to sales draft; production acceptance tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-004'] = 'fixed'  # declared external material-script overlay is served by the production package
POST_SPLIT_BUGS['BUG-2026-11-06-005'] = 'fixed'  # document detail follow-up; production activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-006'] = 'fixed'  # document detail follow-up; production activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-007'] = 'fixed'  # document detail follow-up; production activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-06-008'] = 'fixed'  # document detail follow-up; production activation tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-009'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-010'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-011'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-012'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-013'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-014'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-015'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-016'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-06-017'] = 'fixed'  # menu/document correction; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-07-001'] = 'fixed'  # product master category; CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-07-002'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-07-003'] = 'fixed'  # empty entry cell hints; delivery and activation tracked separately

POST_SPLIT_BUGS['BUG-2026-11-07-004'] = 'fixed'  # local acceptance complete; delivery still requires exact-target CI
POST_SPLIT_BUGS['BUG-2026-11-07-005'] = 'fixed'  # print layout acceptance; CI and activation tracked separately
POST_SPLIT_BUGS['BUG-2026-11-07-006'] = 'fixed'  # namespace candidate verified locally; exact CI and deployment tracked separately

POST_SPLIT_BUGS['BUG-2026-11-07-007'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-07-008'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-07-009'] = 'fixed'  # local candidate verified; exact CI and production tracked separately
POST_SPLIT_BUGS['BUG-2026-11-08-001'] = 'fixed'  # B6 candidate; exact CI and production recorded separately
POST_SPLIT_BUGS['BUG-2026-11-08-002'] = 'fixed'  # B7 exact code CI accepted; production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-08-003'] = 'fixed'  # B8 candidate; exact delivery and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-08-004'] = 'fixed'  # B9 local acceptance; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-08-005'] = 'fixed'  # B10 local evidence; exact CI and production tracked separately

POST_SPLIT_BUGS['BUG-2026-11-08-006'] = 'fixed'  # N2 local candidate; exact CI/runtime release acceptance separate

POST_SPLIT_BUGS['BUG-2026-11-08-007'] = 'fixed'  # N3 candidate; exact CI tracked separately
POST_SPLIT_BUGS['BUG-2026-11-08-008'] = 'fixed'  # N3 same-batch receipt semantics
POST_SPLIT_BUGS['BUG-2026-11-08-009'] = 'fixed'  # N7 local list return regression; exact CI tracked separately
POST_SPLIT_BUGS['BUG-2026-11-09-002'] = 'fixed'  # Windows version conflict; exact release acceptance tracked separately

# 2026-11-10 补齐：拆分后新增（或由 unknown 判定为 fixed）但未登记的 30 条。
# 依据：以拆分时点 dbe79410 的文档状态为基准做差集，30 条全部为新增、丢失 0 条，
# 因此 STATUS_DIST_BASELINE 保持不变（不靠调基线数值来「变绿」）。
for _bug in (
    'BUG-2026-08-30-007', 'BUG-2026-10-26-005',
    'BUG-2026-11-08-010', 'BUG-2026-11-08-011', 'BUG-2026-11-08-012', 'BUG-2026-11-08-013',
    'BUG-2026-11-08-014', 'BUG-2026-11-08-015', 'BUG-2026-11-08-016', 'BUG-2026-11-08-017',
    'BUG-2026-11-08-018', 'BUG-2026-11-08-019', 'BUG-2026-11-08-020', 'BUG-2026-11-08-021',
    'BUG-2026-11-08-022', 'BUG-2026-11-08-023', 'BUG-2026-11-08-024', 'BUG-2026-11-08-025',
    'BUG-2026-11-08-026', 'BUG-2026-11-08-027',
    'BUG-2026-11-09-001', 'BUG-2026-11-09-003', 'BUG-2026-11-09-004', 'BUG-2026-11-09-005',
    'BUG-2026-11-09-006', 'BUG-2026-11-09-007',
    'BUG-2026-11-10-001', 'BUG-2026-11-10-002', 'BUG-2026-11-10-003', 'BUG-2026-11-10-004',
):
    POST_SPLIT_BUGS[_bug] = 'fixed'
del _bug

# 2026-11-10 微信修复批次：新增两条「已修复」登记，逐个核对后从分布中排除，
# STATUS_DIST_BASELINE 仍保持拆分前的 315/141/19/1（不靠调基线数值变绿）。
POST_SPLIT_BUGS['BUG-2026-11-10-005'] = 'fixed'
POST_SPLIT_BUGS['BUG-2026-11-10-006'] = 'fixed'
# 2026-11-11 企微明确拒绝归一化批次：新增 1 条「已修复」登记，逐个核对后从分布中排除。
POST_SPLIT_BUGS['BUG-2026-11-10-012'] = 'fixed'
# 2026-11-11 批量分享逐单异常隔离批次：新增 1 条「已修复」登记，历史分布基线不变。
POST_SPLIT_BUGS['BUG-2026-11-11-001'] = 'fixed'
