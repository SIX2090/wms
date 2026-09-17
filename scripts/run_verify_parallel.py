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

默认取 `min(4, cpu_count)`。CI runner 通常 2-4 核，故实际并发度 2-4。
**不用 min(8, ...)**：每个 verify 进程都要完整导入 Flask app 并建内存库，
是重内存 + 重 IO 的任务，不是纯 CPU 密集；在 4 核 runner 上开到 8 会因内存与
磁盘争抢反而更慢，也让单文件 60s 超时更容易被误触发。
需要更激进/更保守时用环境变量 `VERIFY_WORKERS` 覆盖（CI 里未设置即走默认）。
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
    workers = int(os.environ.get('VERIFY_WORKERS') or 0) or min(4, os.cpu_count() or 2)
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
        _write_step_summary(failures, len(targets), total)
    print(f'\nverify_*.py 失败文件数: {len(failures)}（已知跳过: {len(skipped)}）'
          f'  总耗时 {total:.1f}s')
    return 1 if failures else 0


def _write_step_summary(failures, total_files: int, total_secs: float) -> None:
    """把失败详情写进 GITHUB_STEP_SUMMARY 与工作区文件。

    为什么要这一步（AI-CI-GREEN-003）：GitHub 的 job 日志走
    `productionresultssa*.blob.core.windows.net`，在某些网络环境下该域名不可达
    （DNS 被解析到保留地址、TLS 直接 EOF），导致"CI 红了但看不到红在哪"。
    step summary 是纯文本 API 资源，可用 `GET /actions/jobs/<id>/logs` 之外的方式读取，
    且会直接渲染在 job 页面上，是**唯一稳定可达**的失败详情通道。
    同时落一份到工作区文件，便于用 upload-artifact 取走。
    """
    lines = ['# verify_*.py 失败详情', '',
             f'- 检查文件数：{total_files}',
             f'- 失败文件数：{len(failures)}',
             f'- 总耗时：{total_secs:.1f}s', '']
    for path, rc, elapsed, out in failures:
        lines += [f'## {path}', '',
                  f'- 退出码：{rc}',
                  f'- 耗时：{elapsed:.1f}s', '',
                  '```', out[-3000:], '```', '']
    body = '\n'.join(lines)

    summary_path = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary_path:
        try:
            with open(summary_path, 'a', encoding='utf-8') as fh:
                fh.write(body + '\n')
        except OSError as exc:  # noqa: BLE001
            print(f'[warn] 写 GITHUB_STEP_SUMMARY 失败: {exc}')

    # 第三通道：workflow command 注解。
    # 为什么还需要它：step summary 只在 job 页面渲染、artifact 走 blob 域名（本沙箱
    # 实测两个通道分别在「check-run output 为空」与「DNS 落保留地址」上折戟），
    # 而 `::error::` 注解能通过 `GET /check-runs/<job_id>/annotations` 稳定读到——
    # AI-CI-GREEN-003 排查时实测该接口可返回 annotations_count 与逐条 message。
    # 因此在无日志、无 artifact 的极端网络下，注解是**唯一还能读出失败文件名**的通道。
    for path, rc, elapsed, out in failures:
        first_lines = [ln.strip() for ln in out.strip().splitlines() if ln.strip()]
        detail = ' | '.join(first_lines[-3:])[:400] if first_lines else '(无输出)'
        # 单行、不含换行，避免 GitHub 截断注解
        print(f'::error file={path},title=verify 失败 rc={rc} '
              f'({elapsed:.1f}s)::[{path}] {detail}', flush=True)

    try:
        out_file = REPO_ROOT / 'verify_failures_summary.md'
        out_file.write_text(body, encoding='utf-8')
        print(f'[info] 失败详情已写入 {out_file}（便于作为 artifact 取走）')
    except OSError as exc:  # noqa: BLE001
        print(f'[warn] 写工作区摘要文件失败: {exc}')


if __name__ == '__main__':
    sys.exit(main())
