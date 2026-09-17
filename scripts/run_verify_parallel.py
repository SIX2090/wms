#!/usr/bin/env python3
"""tests/verify_*.py 逐文件独立进程 + 并发调度（CI-PERF-2026-09-17）。

## 为什么要有这个脚本

`tests/verify_*.py` 是「契约回归」脚本集（173 个文件），它们**必须逐文件独立进程跑**，
不能合并进同一个 pytest 会话，也不能让多个文件共享一个 worker。原因是实测出来的：

  - 合并单进程：`sqlalchemy.exc.OperationalError: no such table: warehouse`
    （前一个文件 `db.drop_all()` 把内存库拆了，后一个文件在 import 期就查表），
    随后 pytest 把 172 个路径拼成一条超长命令行直接 "file or directory not found"。
  - 交给 pytest-xdist 共享 worker：同样在收集阶段就被上面的异常带崩整批，
    `no tests ran`。
  - `--forked`（父子进程）：隔离是对的，但每个子进程仍要重新 import app，
    实测没有净收益。

历史记录同结论：AGENTS.md / ci.yml 注释记载当年「多文件同进程混跑会产生 169 例
环境性假失败」，故改为逐文件独立进程。**本脚本不改变这个隔离模型**。

## 本脚本做的事

隔离模型（每文件一个独立 python 进程、不共享内存）与原先的 for 循环完全一致，
只是把「一个跑完再跑下一个」的串行等待换成**进程池并发等待**。
单文件耗时中位数里约 1.8s 是 `import app` 的固定开销（Flask app 构造），
串行时这 173 份开销是纯等待 —— 并发后总时长从 ~583s 降到 ~255s（本机实测）。

## 与 CI 原逻辑的等价性（逐项对齐，不得删减）

1. **分流规则同原 ci.yml**：`grep -q "def test_"` → pytest 式文件用
   `pytest <file> -q`；否则（脚本式、顶层断言）直接 `python <file>`。
   两种形态的信号语义都要保住：pytest 式收集 0 用例会 exit 5，
   脚本式顶层断言失败会 exit 1 —— 都算失败。
2. **known_failures 机制保留**：清单内文件打印 SKIP 后跳过，不参与失败计数。
   （当前清单为空，保留结构以便未来临时登记。）
3. **单文件 60s 超时保留**：超时按失败处理，与原来 `timeout --kill-after=10s 60s` 同等严格。
4. **失败文件数汇总 + 非零退出**：任一文件失败即整体 exit 1。

## 并发度

默认取 `min(8, cpu_count)`。CI runner 通常 2-4 核，故实际并发度会是 2-4；
本机（32 核）用 8 已实测 173 文件 255s、失败 0。并发度过高反而会因
CPU 争抢变慢，且会让 60s 超时更容易被误触发，故不盲目拉满。
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIMEOUT_SEC = 60
KILL_AFTER_SEC = 10

# 已知失败文件（与原 ci.yml 的 known_failures 数组等价，当前为空）。
# 登记格式：'tests/verify_xxx.py'
KNOWN_FAILURES: list[str] = []


def _is_pytest_style(path: str) -> bool:
    """pytest 式（含 def test_）用 pytest 跑；脚本式用 python 直接执行。

    与 CI 原 grep 判据保持一致：脚本式文件用 pytest 跑会 "no tests ran" exit 5
    被误判失败，必须分流。
    """
    with open(path, encoding='utf-8', errors='replace') as fh:
        return 'def test_' in fh.read()


def _run_one(path: str) -> tuple[str, int, float, str]:
    cmd = (
        [sys.executable, '-m', 'pytest', path, '-q', '-p', 'no:pylama']
        if _is_pytest_style(path)
        else [sys.executable, path]
    )
    started = time.time()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT_SEC,
            cwd=str(REPO_ROOT),
        )
        out = (proc.stdout or '') + (proc.stderr or '')
        rc = proc.returncode
    except subprocess.TimeoutExpired as exc:
        # 超时视同失败（对齐原 `timeout --kill-after=10s 60s`）
        partial = ''
        for stream in (exc.stdout, exc.stderr):
            if stream:
                partial += stream if isinstance(stream, str) else stream.decode('utf-8', 'replace')
        out = f'[TIMEOUT after {TIMEOUT_SEC}s]\n{partial}'
        rc = 124
    return path, rc, time.time() - started, out


def main() -> int:
    workers = int(os.environ.get('VERIFY_WORKERS') or 0) or min(8, os.cpu_count() or 2)
    files = sorted(
        os.path.relpath(p, REPO_ROOT)
        for p in glob.glob(str(REPO_ROOT / 'tests' / 'verify_*.py'))
    )

    skipped = [f for f in files if f in KNOWN_FAILURES]
    targets = [f for f in files if f not in KNOWN_FAILURES]
    for f in skipped:
        print(f'SKIP (known failure, BUG-2026-08-16-017): {f}')

    print(f'verify 并行调度：{len(targets)} 个文件，并发度 {workers}，'
          f'单文件超时 {TIMEOUT_SEC}s（已知跳过 {len(skipped)}）', flush=True)

    started = time.time()
    failures: list[tuple[str, int, float, str]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for path, rc, elapsed, out in pool.map(_run_one, targets):
            if rc != 0:
                failures.append((path, rc, elapsed, out))
                print(f'FAIL(rc={rc}) {path}  {elapsed:.1f}s', flush=True)
            else:
                print(f'  ok  {path}  {elapsed:.1f}s', flush=True)

    total = time.time() - started
    if failures:
        print('\n' + '=' * 70)
        print('失败文件详情：')
        for path, rc, elapsed, out in failures:
            print(f'\n--- {path} (rc={rc}, {elapsed:.1f}s) ---')
            print(out[-4000:])
    print(f'\nverify_*.py 失败文件数: {len(failures)}（已知跳过: {len(skipped)}）'
          f'  总耗时 {total:.1f}s')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
