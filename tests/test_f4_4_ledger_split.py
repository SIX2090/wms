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
