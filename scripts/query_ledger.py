#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""台账分片查询工具（F4.4）。

巨型台账（WMS_BUG_BASELINE.md / WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md）的历史
记录已按月拆分至 docs/ledger/（详见 docs/ledger/README.md）。本工具实现验收：
**任一任务详情 ≤2 次文件读取可得**（读 1 次统一索引定位分片 + 读 1 次分片）。

用法：
    python scripts/query_ledger.py --task BUG-2026-10-05-001   # 精确 ID
    python scripts/query_ledger.py --task F4.2                 # 任务编号
    python scripts/query_ledger.py --task SM-P6                # 唯一前缀
    python scripts/query_ledger.py --list                      # 列出全部分片

匹配规则：先精确匹配；无精确命中再做前缀匹配（唯一则直出，多个则列候选）。
条目形态：表格行（首列 = ID）或 Markdown 小节（标题首词 = ID）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER_DIR = ROOT / 'docs' / 'ledger'
UNIFIED_INDEX = LEDGER_DIR / 'INDEX.md'

INDEX_ROW_RE = re.compile(r'^\|\s*([^|]+?)\s*\|\s*(ai|bugs)\s*\|\s*([^|]+?)\s*\|\s*$')
SECTION_HEAD_RE = re.compile(r'^#{2,4}\s+')


def load_index() -> list[tuple[str, str, str]]:
    """读统一索引：[(条目ID, 类别, 分片文件名)]。"""
    if not UNIFIED_INDEX.exists():
        print(f'错误：索引不存在 {UNIFIED_INDEX.relative_to(ROOT)}', file=sys.stderr)
        print('请先运行迁移/重建（见 docs/ledger/README.md）', file=sys.stderr)
        return []
    rows = []
    for line in UNIFIED_INDEX.read_text(encoding='utf-8').splitlines():
        m = INDEX_ROW_RE.match(line)
        if m:
            rows.append((m.group(1), m.group(2), m.group(3)))
    return rows


def list_shards() -> int:
    shards = sorted(
        (p.relative_to(LEDGER_DIR).as_posix(), p.stat().st_size)
        for p in LEDGER_DIR.rglob('*.md') if p.name != 'INDEX.md'
    )
    if not shards:
        print('docs/ledger/ 下没有分片')
        return 1
    print(f'{"分片":58s} {"大小":>8s}')
    for rel, size in shards:
        print(f'{rel:58s} {size / 1024:6.1f}KB')
    print(f'共 {len(shards)} 个分片')
    return 0


def match_rows(rows, task):
    """返回 (精确命中列表, 前缀命中列表)。"""
    exact = [r for r in rows if r[0] == task]
    prefix = [r for r in rows if r[0].startswith(task)] if task not in ('',) else []
    return exact, prefix


def extract_entry(shard_path: Path, task: str) -> str | None:
    """从分片提取条目内容：优先表格行（首列==task），否则小节（标题首词==task 或标题含 task）。"""
    lines = shard_path.read_text(encoding='utf-8').splitlines()

    # 1) 表格行
    for i, line in enumerate(lines):
        if line.startswith('|'):
            cols = [c.strip() for c in line.split('|')]
            if len(cols) >= 2 and cols[1] == task:
                return f'{shard_path.relative_to(ROOT)}:{i + 1}\n{line}'

    # 2) 小节（标题行到下一个同级或更高级标题）
    for i, line in enumerate(lines):
        if not SECTION_HEAD_RE.match(line):
            continue
        title = re.sub(r'^#{2,4}\s+', '', line)
        token = re.split(r'[\s:：（——“"]', title, maxsplit=1)[0].strip()
        if token == task or task in title.split('（')[0]:
            end = len(lines)
            lvl = len(line) - len(line.lstrip('#'))
            for j in range(i + 1, len(lines)):
                l2 = lines[j]
                if SECTION_HEAD_RE.match(l2) and (len(l2) - len(l2.lstrip('#'))) <= lvl:
                    end = j
                    break
            body = '\n'.join(lines[i:end]).rstrip()
            return f'{shard_path.relative_to(ROOT)}:{i + 1}\n{body}'
    return None


def query(task: str) -> int:
    rows = load_index()
    if not rows:
        return 1
    exact, prefix = match_rows(rows, task)
    hits = exact or prefix
    if not hits:
        print(f'未找到条目：{task}')
        print('用 --list 查看分片，或检查 ID（如 BUG-2026-10-05-001 / F4.2 / AI-R01）。')
        return 1
    if len(hits) > 1 and not exact:
        print(f'前缀「{task}」命中 {len(hits)} 个条目，请精确化：')
        for tid, cat, shard in hits[:20]:
            print(f'  {tid:45s} -> {cat}/{shard}')
        if len(hits) > 20:
            print(f'  …（共 {len(hits)} 个）')
        return 2
    for tid, cat, shard in hits[:5]:
        shard_path = LEDGER_DIR / cat / shard
        if not shard_path.exists():
            print(f'错误：分片缺失 {shard_path.relative_to(ROOT)}', file=sys.stderr)
            return 1
        out = extract_entry(shard_path, tid)
        if out is None:
            print(f'错误：索引指向的分片中未找到条目 {tid}（{shard}），索引可能过期', file=sys.stderr)
            return 1
        loc, _, body = out.partition('\n')
        print(f'== {tid} ==')
        print(f'位置：{loc}')
        print(body)
        print()
    return 0


def rebuild_index() -> int:
    """重建统一索引 docs/ledger/INDEX.md（从 ai/ 与 bugs/ 的分片中提取条目）。"""
    if not LEDGER_DIR.exists():
        print(f'错误：{LEDGER_DIR.relative_to(ROOT)} 不存在', file=sys.stderr)
        return 1
    rows = []
    date_re = re.compile(r'(\d{4}-\d{2})')
    for cat in ('ai', 'bugs'):
        cat_dir = LEDGER_DIR / cat
        if not cat_dir.exists():
            continue
        for shard in sorted(cat_dir.glob('*.md')):
            if shard.name == 'INDEX.md':
                continue
            mo = date_re.search(shard.name)
            shard_month = mo.group(1) if mo else shard.stem
            for line in shard.read_text(encoding='utf-8').splitlines():
                if line.startswith('|'):
                    cols = [c.strip() for c in line.split('|')]
                    if len(cols) >= 2 and cols[1] and not set(cols[1]) <= {'-', ' '}:
                        tid = cols[1]
                        if tid in ('任务编号', '编号', '条目'):
                            continue
                        if re.match(r'\d{4}-\d{2}-\d{2}', tid) and not re.match(
                                r'(?:BUG|LABEL-FIX)-', tid):
                            continue  # 完成日期列等非 ID 首列
                        rows.append((tid, cat, shard.name))
                elif SECTION_HEAD_RE.match(line):
                    title = re.sub(r'^#{2,4}\s+', '', line)
                    title = re.sub(r'^附：', '', title)
                    token = re.split(r'[\s:：（——“"]', title, maxsplit=1)[0].strip()
                    if token and len(token) >= 2:
                        rows.append((token, cat, shard.name))
    # 去重（同 ID 多处出现保留首个）
    seen = set()
    uniq = []
    for tid, cat, shard in rows:
        key = (tid, cat)
        if key in seen:
            continue
        seen.add(key)
        uniq.append((tid, cat, shard))
    header = [
        '# 台账统一索引（自动生成，勿手改）', '',
        '> F4.4 拆分生成。查询：`python scripts/query_ledger.py --task <ID>`；',
        '> 重建：`python scripts/query_ledger.py --rebuild-index`。', '',
        '| 条目 | 类别 | 分片 |', '|---|---|---|',
    ]
    body = [f'| {tid} | {cat} | {shard} |' for tid, cat, shard in uniq]
    UNIFIED_INDEX.write_text('\n'.join(header + body) + '\n', encoding='utf-8', newline='\n')
    print(f'索引重建完成：{len(uniq)} 条 → {UNIFIED_INDEX.relative_to(ROOT)}')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='WMS 台账分片查询（F4.4）')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--task', help='条目 ID 或唯一前缀（BUG-2026-10-05-001 / F4.2 / AI-R01）')
    g.add_argument('--list', action='store_true', help='列出全部分片')
    g.add_argument('--rebuild-index', action='store_true', help='重建统一索引（登记新条目后运行）')
    args = ap.parse_args(argv)
    if args.list:
        return list_shards()
    if args.rebuild_index:
        return rebuild_index()
    return query(args.task)


if __name__ == '__main__':
    sys.exit(main())
