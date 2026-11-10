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

    # 默认不分片，仍使用 pytest-xdist -n 4 --dist loadfile；为隔离安全，
    # 禁用插件自动发现，并显式加载 xdist。
"""
from __future__ import annotations

import glob
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKERS = 4


def report_failures(report: Path) -> bool:
    """Publish actual pytest failures without requiring private log download."""
    try:
        cases = list(ET.parse(report).getroot().iter('testcase'))
        if not cases:
            raise ValueError('pytest report contains no collected tests')
    except (OSError, ET.ParseError, ValueError) as exc:
        print('[error] 无法核实 pytest 报告：' + str(exc), flush=True)
        return False
    failures = []
    for case in cases:
        for failure in list(case):
            if failure.tag in ('failure', 'error'):
                name = case.get('classname', '') + '::' + case.get('name', '')
                detail = (failure.text or failure.get('message', '')).strip()
                failures.append((name, detail))
    lines = [f'# Unit test failures: {len(failures)} / {len(cases)} cases', '']

    def annotate(title, text):
        # Workflow commands must escape untrusted assertion output.
        message = text.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(f'::error title={title}::' + message, flush=True)

    if failures:
        # GitHub keeps only the first 10 error annotations per step, and job logs
        # need admin rights; publish the complete failing-case list first.
        listing = '\n'.join(name for name, _ in failures)
        annotate(f'Unit failures {len(failures)}/{len(cases)}', listing[:60000])
    for name, detail in failures:
        lines.extend([name, '', '```text', detail, '```', ''])
        annotate('Unit test failure', name + '\n' + detail[:2500])
    report.with_suffix('.md').write_text('\n'.join(lines), encoding='utf-8')
    return not failures


def collect(shards: int, shard: int) -> list[str]:
    """返回本片文件列表（相对仓库根的路径）。

    只收 `tests/test_*.py`——`tests/verify_*.py` 由 run_verify_parallel.py 负责，
    两者不重叠（CI 里也是两个独立 job）。
    """
    if shards < 1 or not (0 <= shard < shards):
        raise ValueError('分片数量和序号无效')
    all_files = sorted(
        os.path.relpath(p, REPO_ROOT)
        for p in glob.glob(str(REPO_ROOT / 'tests' / 'test_*.py'))
    )
    if shards <= 1:
        return all_files
    return [f for i, f in enumerate(all_files) if i % shards == shard]


def main() -> int:
    try:
        shards = int(os.environ.get('VERIFY_TEST_SHARDS') or 1)
        shard = int(os.environ.get('VERIFY_TEST_SHARD') or 0)
        workers = int(os.environ.get('VERIFY_TEST_WORKERS') or 0) or DEFAULT_WORKERS
    except ValueError:
        print('[error] 分片数量、序号和工作进程数必须是整数')
        return 1

    if shards < 1 or not (0 <= shard < shards):
        print(f'[error] VERIFY_TEST_SHARD={shard} 越界（VERIFY_TEST_SHARDS={shards}）')
        return 1
    if workers < 1:
        print('[error] VERIFY_TEST_WORKERS 必须是正数或 0（自动）')
        return 1

    files = collect(shards, shard)
    if not files:
        print(f'[error] 分片 {shard}/{shards} 无测试文件，不能视为验证通过')
        return 1
    if '--list' in sys.argv:
        print('\n'.join(files))
        return 0

    try:
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.linux_test_runtime import require_subprocess_boundary
        require_subprocess_boundary()
    except SystemExit as exc:
        print('[error] 数据库、备份与网络隔离尚未证明：' + str(exc))
        return 1

    env = os.environ.copy()
    for key in ('DATABASE_URL', 'WMS_DATABASE_URI'):
        if env.get(key, '') not in ('', 'sqlite:///:memory:'):
            print(f'[error] 验证已阻止：{key} 不是已确认的内存数据库')
            return 1
    for key in ('PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTHONPATH', 'PYTHONHOME'):
        if env.get(key, ''):
            print(f'[error] 验证已阻止：请清除继承的 {key}')
            return 1
    env['DATABASE_URL'] = 'sqlite:///:memory:'
    env['WMS_DATABASE_URI'] = 'sqlite:///:memory:'
    env['WMS_SKIP_AUTO_UPDATE'] = '1'
    # 自动发现的插件可能在 conftest 之前导入应用；仅显式加载分片所需 xdist。
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    env['PYTHONNOUSERSITE'] = '1'

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
        '-q', '-p', 'no:pylama', '-p', 'xdist.plugin',
        '-n', str(workers), '--dist', 'loadfile',
    ]
    report = REPO_ROOT / 'output' / f'unit-shard-{shard}.xml'
    report.parent.mkdir(parents=True, exist_ok=True)
    # A failed collection must not accidentally publish an older run's XML.
    report.unlink(missing_ok=True)
    report.with_suffix('.md').unlink(missing_ok=True)
    result = subprocess.call([*cmd, '--junitxml', str(report)], cwd=str(REPO_ROOT), env=env)
    verified = report_failures(report)
    return result if result else (0 if verified else 1)


if __name__ == '__main__':
    sys.exit(main())
