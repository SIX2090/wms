#!/usr/bin/env python3
"""tests/*.py 主套件按文件分片（CI-PERF-2026-09-24）。

## 为什么需要

WMS CI 的 `unit-tests` job 实测 ~180s（`pytest tests/ -n 4 --dist loadfile`），
在 verify 切成 4 片后它成了新的关键路径。180s 的构成（实测 durations）：

  - 单条最慢：34.28s（test_verify_wms_bugs_gate 的 setup，重且不可切）
  - 大量 2–4s 的迁移/建库类测试（**IO 密集**：每个测试自己 import app + 建库）

实测 `-n 16` 比 `-n 4` **更慢**（143s vs 123s）——说明本套件不是 CPU 密集，
单纯提高单机并发度无效。但把文件分到**不同的 GitHub runner**（每个 job 独占
一台 4 核 VM，互不抢 IO）是有效的：关键路径从 180s 降到「180/N + 启动开销」。

## 分片规则（与 scripts/run_verify_parallel.py 完全一致）

按 `sorted()` 后文件序号取模：`index % shards == shard`。
取模而非连续区间，是为了让每片都均匀混入耗时长短不一的文件 ——
若某片恰好全是慢文件，它就成了新的关键路径，切片收益被吃光。

## 用法

    # 取本片文件列表（供 pytest 消费），不执行
    python3 scripts/run_tests_sharded.py --list

    # 执行本片
    VERIFY_TEST_SHARDS=3 VERIFY_TEST_SHARD=0 python3 scripts/run_tests_sharded.py

    # 默认（不分片）时等价于 `pytest tests/ -n 4 --dist loadfile`
    # —— 即历史行为逐字节不变
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKERS = 4


def collect(shards: int, shard: int) -> list[str]:
    """返回本片文件列表（相对仓库根的路径）。

    只收 `tests/test_*.py`——`tests/verify_*.py` 由 run_verify_parallel.py 负责，
    两者不重叠（CI 里也是两个独立 job）。
    """
    all_files = sorted(
        os.path.relpath(p, REPO_ROOT)
        for p in glob.glob(str(REPO_ROOT / 'tests' / 'test_*.py'))
    )
    if shards <= 1:
        return all_files
    return [f for i, f in enumerate(all_files) if i % shards == shard]


def main() -> int:
    shards = int(os.environ.get('VERIFY_TEST_SHARDS') or 1)
    shard = int(os.environ.get('VERIFY_TEST_SHARD') or 0)
    workers = int(os.environ.get('VERIFY_TEST_WORKERS') or 0) or DEFAULT_WORKERS

    if shards > 1 and not (0 <= shard < shards):
        print(f'[error] VERIFY_TEST_SHARD={shard} 越界（VERIFY_TEST_SHARDS={shards}）')
        return 1

    files = collect(shards, shard)
    if '--list' in sys.argv:
        print('\n'.join(files))
        return 0

    if not files:
        # 空片也算通过：分片数多于文件数时（正常不会发生）不能误判失败
        print(f'[warn] 分片 {shard}/{shards} 无文件，跳过')
        return 0

    all_count = len(collect(1, 0))
    print(
        f'主套件分片 {shard + 1}/{shards}：本片 {len(files)} 个文件'
        f'（全量 {all_count}），pytest-xdist -n {workers} --dist loadfile',
        flush=True,
    )

    # 保持与原 unit-tests step 完全相同的 pytest 参数：-q -p no:pylama
    # -n 4 --dist loadfile。切片只改变"喂给 pytest 的文件集合"，
    # 不改变执行方式与隔离模型。
    cmd = [
        sys.executable, '-m', 'pytest', *files,
        '-q', '-p', 'no:pylama',
        '-n', str(workers), '--dist', 'loadfile',
    ]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


if __name__ == '__main__':
    sys.exit(main())
