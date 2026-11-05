#!/usr/bin/env python3
"""Finite WMS child-process retries; stdlib only, no database or network access.

The WMS child must retain its own existing database runtime lease. A surviving
child after a supervisor crash must therefore refuse a second WMS instance.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from runtime_guard import acquire_database_lease


def _write_state(path, record):
    descriptor, name = tempfile.mkstemp(prefix='.supervisor-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            json.dump(record, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def _windows_action(path):
    if os.name != 'nt':
        raise ValueError('原生计划任务动作仅支持Windows')
    if path.stat().st_size > 65536:
        raise ValueError('计划任务动作文件过大')
    action = json.loads(path.read_text(encoding='utf-8-sig'))
    execute, arguments = action.get('execute'), action.get('arguments')
    directory = action.get('directory') or None
    if (not isinstance(execute, str) or not execute or not isinstance(arguments, str) or
            (directory is not None and not isinstance(directory, str))):
        raise ValueError('计划任务动作文件无效')
    # Preserve the registered Windows command line exactly, including CMD quoting.
    # No new shell or argument splitting is introduced.
    return subprocess.list2cmdline([execute]) + (' ' + arguments if arguments else ''), directory


def run_supervised(command, state_directory, *, max_restarts=3, restart_delay=60, reset_budget=False, cwd=None):
    """One monitor, bounded retries, and a persistent exhausted-state interlock."""
    directory = Path(state_directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    # This is an OS file lease in the monitor directory, never the business DB lock.
    try:
        lease = acquire_database_lease(directory / 'supervisor')
    except RuntimeError as error:
        raise RuntimeError('服务监护已在运行，拒绝重复启动') from error
    child = None
    path = directory / 'supervisor-status.json'
    try:
        record = {}
        if path.exists() and not reset_budget:
            if path.stat().st_size > 8192:
                raise ValueError('监护状态文件无效，请核对后人工重置')
            record = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(record, dict) or record.get('phase') not in
                    {'starting', 'running', 'waiting', 'stopped', 'exhausted'} or
                    type(record.get('restarts')) is not int or record['restarts'] < 0):
                raise ValueError('监护状态文件无效，请核对后人工重置')
            if record['phase'] == 'exhausted':
                raise RuntimeError('自动重试已耗尽；请检查服务故障后人工重置，定时触发不会重置预算')
        restarts = record.get('restarts', 0)
        if record.get('phase') in {'running', 'starting'}:
            restarts += 1
        while True:
            if restarts > max_restarts:
                _write_state(path, {'phase': 'exhausted', 'restarts': restarts,
                                    'last_exit_code': record.get('last_exit_code')})
                return 1
            record = {'phase': 'starting', 'restarts': restarts, 'last_exit_code': None}
            _write_state(path, record)
            began = time.monotonic()
            try:
                child = subprocess.Popen(command, cwd=cwd, shell=False)
            except OSError:
                code = 127
            else:
                record.update(phase='running', child_pid=child.pid)
                _write_state(path, record)
                code = child.wait()
                child = None
            if code == 0:
                _write_state(path, {'phase': 'stopped', 'restarts': 0, 'last_exit_code': 0})
                return 0
            if time.monotonic() - began >= 300:
                restarts = 0
            if restarts >= max_restarts:
                _write_state(path, {'phase': 'exhausted', 'restarts': restarts, 'last_exit_code': code})
                return code if 0 < code < 256 else 1
            restarts += 1
            record = {'phase': 'waiting', 'restarts': restarts, 'last_exit_code': code}
            _write_state(path, record)
            time.sleep(restart_delay)
    except KeyboardInterrupt:
        _write_state(path, {'phase': 'stopped', 'restarts': 0, 'last_exit_code': 130})
        return 130
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)
        lease.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description='WMS单实例监护；故障有限重试，耗尽后人工检查')
    parser.add_argument('--state-directory', type=Path, required=True)
    parser.add_argument('--max-restarts', type=int, default=3)
    parser.add_argument('--restart-delay', type=float, default=60)
    parser.add_argument('--reset-budget', action='store_true')
    parser.add_argument('--windows-action-file', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if (not 0 <= args.max_restarts <= 10 or not math.isfinite(args.restart_delay) or
            not 0 <= args.restart_delay <= 3600 or bool(command) == bool(args.windows_action_file)):
        parser.error('请提供一个启动命令，重试0至10次，间隔0至3600秒')
    def stop_requested(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_requested)
    try:
        cwd = None
        if args.windows_action_file:
            command, cwd = _windows_action(args.windows_action_file)
        return run_supervised(command, args.state_directory, max_restarts=args.max_restarts,
                              restart_delay=args.restart_delay, reset_budget=args.reset_budget, cwd=cwd)
    except (OSError, ValueError, RuntimeError) as error:
        print(f'服务监护未完成：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
