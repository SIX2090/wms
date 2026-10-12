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
        """拆分零丢失：任务 ID / BUG-ID 集合守恒（对 git HEAD 的两份主文件比对）。"""
        import re
        task_re = re.compile(r'\|\s*([A-Z]+(?:-[A-Z0-9]+)+)\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|')
        bug_re = re.compile(r'(?:BUG|LABEL-FIX)-\d{4}-\d{2}-\d{2}-\d{3}')

        def collect(*texts):
            t = set()
            b = set()
            for text in texts:
                t |= set(task_re.findall(text))
                b |= set(bug_re.findall(text))
            return t, b

        old_t, old_b = collect(
            subprocess.run(['git', 'show', 'HEAD:WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md'],
                           capture_output=True, encoding='utf-8', cwd=str(ROOT)).stdout,
            subprocess.run(['git', 'show', 'HEAD:WMS_BUG_BASELINE.md'],
                           capture_output=True, encoding='utf-8', cwd=str(ROOT)).stdout,
        )
        texts = [(ROOT / n).read_text(encoding='utf-8')
                 for n in ('WMS_BUG_BASELINE.md', 'WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md')]
        texts += [p.read_text(encoding='utf-8') for p in LEDGER.rglob('*.md')]
        new_t, new_b = collect(*texts)
        # HEAD 会随提交前进：只验证「不低于拆分时基线」（新登记只增不减）
        assert len(new_b) >= BUG_IDS_BASELINE == len(old_b)
        assert len(new_t) >= AI_TASK_IDS_BASELINE == len(old_t)
        assert not (old_b - new_b), f'BUG-ID 丢失: {sorted(old_b - new_b)[:5]}'
        assert not (old_t - new_t), f'任务 ID 丢失: {sorted(old_t - new_t)[:5]}'


class TestMonthlyReviewEquivalence:
    def test_status_distribution_matches_pre_split(self):
        """monthly_bug_review 状态判定与拆分前逐项一致（拼接顺序回归锁）。"""
        sys.path.insert(0, str(ROOT / 'scripts'))
        from monthly_bug_review import _load_baseline_text, build_status_index
        from collections import Counter
        dist = Counter(build_status_index(_load_baseline_text()).values())
        assert dict(dist) == STATUS_DIST_BASELINE, dict(dist)
