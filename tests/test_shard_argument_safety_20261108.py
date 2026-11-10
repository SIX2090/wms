"""Offline validation of shard arguments; never starts a test or accesses WMS."""
import os
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SHARDED = runpy.run_path(str(ROOT / 'scripts/run_tests_sharded.py'))
VERIFY = runpy.run_path(str(ROOT / 'scripts/run_verify_parallel.py'))


def forbidden(*_args, **_kwargs):
    raise AssertionError('database, network and subprocess access is forbidden')


class ShardArgumentSafety(unittest.TestCase):
    def setUp(self):
        for guarded in (patch.object(socket.socket, 'connect', forbidden),
                        patch.object(socket.socket, 'connect_ex', forbidden),
                        patch.object(socket, 'getaddrinfo', forbidden),
                        patch.object(sqlite3, 'connect', forbidden),
                        patch.object(subprocess, 'call', forbidden),
                        patch.object(subprocess, 'run', forbidden)):
            guarded.start()
            self.addCleanup(guarded.stop)

    def test_invalid_unit_shards_rejected_before_collection(self):
        cases = [
            {'VERIFY_TEST_SHARDS': '0'}, {'VERIFY_TEST_SHARDS': '-1'},
            {'VERIFY_TEST_SHARDS': '1', 'VERIFY_TEST_SHARD': '1'},
            {'VERIFY_TEST_SHARDS': '3', 'VERIFY_TEST_SHARD': '-1'},
            {'VERIFY_TEST_SHARDS': '3', 'VERIFY_TEST_SHARD': '3'},
            {'VERIFY_TEST_SHARDS': 'not-a-number'},
            {'VERIFY_TEST_WORKERS': '-1'}, {'VERIFY_TEST_WORKERS': 'invalid'},
        ]
        for env in cases:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                 patch.object(sys, 'argv', ['run_tests_sharded.py', '--list']), \
                 patch.dict(SHARDED['main'].__globals__, {'collect': forbidden}), \
                 redirect_stdout(StringIO()):
                self.assertEqual(SHARDED['main'](), 1)

    def test_invalid_verify_shards_rejected_before_collection(self):
        cases = [
            {'VERIFY_SHARDS': '0'}, {'VERIFY_SHARDS': '-1'},
            {'VERIFY_SHARDS': '1', 'VERIFY_SHARD': '1'},
            {'VERIFY_SHARDS': '3', 'VERIFY_SHARD': '-1'},
            {'VERIFY_SHARDS': '3', 'VERIFY_SHARD': '3'},
            {'VERIFY_SHARDS': 'not-a-number'},
            {'VERIFY_WORKERS': '-1'}, {'VERIFY_WORKERS': 'invalid'},
        ]
        for env in cases:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                 patch.object(VERIFY['main'].__globals__['glob'], 'glob', forbidden), \
                 redirect_stdout(StringIO()):
                self.assertEqual(VERIFY['main'](), 1)

    def test_unit_shards_are_disjoint_and_complete(self):
        files = [str(ROOT / 'tests' / f'test_synthetic_{i}.py') for i in range(11)]
        with patch.object(SHARDED['collect'].__globals__['glob'], 'glob', return_value=files):
            whole = SHARDED['collect'](1, 0)
            shards = [SHARDED['collect'](3, n) for n in range(3)]
        self.assertEqual(sorted(item for shard in shards for item in shard), sorted(whole))
        self.assertEqual(sum(map(len, shards)), len(set(whole)))
        self.assertTrue(all(shards))

    def test_direct_collect_rejects_invalid_shards(self):
        cases = [(0, 0), (-1, 0), (1, 1), (3, -1), (3, 3)]
        with patch.object(SHARDED['collect'].__globals__['glob'], 'glob', forbidden):
            for shards, shard in cases:
                with self.subTest(shards=shards, shard=shard):
                    with self.assertRaises(ValueError):
                        SHARDED['collect'](shards, shard)

    def test_valid_unit_list_returns_the_requested_shard(self):
        files = [str(ROOT / 'tests' / f'test_synthetic_{i}.py') for i in range(5)]
        output = StringIO()
        with patch.dict(os.environ, {'VERIFY_TEST_SHARDS': '2', 'VERIFY_TEST_SHARD': '1'}, clear=True), \
             patch.object(sys, 'argv', ['run_tests_sharded.py', '--list']), \
             patch.object(SHARDED['main'].__globals__['glob'], 'glob', return_value=files), \
             redirect_stdout(output):
            self.assertEqual(SHARDED['main'](), 0)
        expected = [os.path.relpath(files[i], ROOT) for i in (1, 3)]
        self.assertEqual(output.getvalue().splitlines(), expected)

    def test_zero_workers_remains_automatic(self):
        cases = [
            (SHARDED['main'], {'VERIFY_TEST_WORKERS': '0'},
             {'collect': lambda *_: ['tests/test_synthetic.py']}),
            (VERIFY['main'], {'VERIFY_WORKERS': '0'}, None),
        ]
        for main, env, overrides in cases:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                 patch.object(sys, 'argv', ['synthetic-runner']), \
                 patch.object(main.__globals__['glob'], 'glob',
                              return_value=[str(ROOT / 'tests/verify_synthetic.py')]), \
                 patch.dict(main.__globals__, overrides or {}), \
                 redirect_stdout(StringIO()) as output:
                self.assertEqual(main(), 1)
                self.assertIn('数据库、备份与网络隔离尚未证明', output.getvalue())

    def test_empty_unit_list_remains_failure(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, 'argv', ['run_tests_sharded.py', '--list']), \
             patch.dict(SHARDED['main'].__globals__, {'collect': lambda *_: []}), \
             redirect_stdout(StringIO()):
            self.assertEqual(SHARDED['main'](), 1)

    def test_verify_shards_are_disjoint_and_complete(self):
        files = [str(ROOT / 'tests' / f'verify_synthetic_{i}.py') for i in range(11)]
        selections = []
        for shard in range(3):
            env = {'VERIFY_SHARDS': '3', 'VERIFY_SHARD': str(shard)}
            captured = {}

            def trace(frame, event, _arg):
                if event == 'return' and frame.f_code is VERIFY['main'].__code__:
                    captured['targets'] = list(frame.f_locals['targets'])
                return trace

            with patch.dict(os.environ, env, clear=True), \
                 patch.object(VERIFY['main'].__globals__['glob'], 'glob', return_value=files), \
                 patch.dict(VERIFY['main'].__globals__, {'KNOWN_FAILURES': []}), \
                 redirect_stdout(StringIO()):
                previous = sys.gettrace()
                try:
                    sys.settrace(trace)
                    self.assertEqual(VERIFY['main'](), 1)
                finally:
                    sys.settrace(previous)
            selections.append(captured['targets'])
        expected = {os.path.relpath(path, ROOT) for path in files}
        flat = [item for selection in selections for item in selection]
        self.assertTrue(all(selections))
        self.assertEqual(set(flat), expected)
        self.assertEqual(len(flat), len(expected))

    def test_empty_verify_list_remains_failure(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(VERIFY['main'].__globals__['glob'], 'glob', return_value=[]), \
             redirect_stdout(StringIO()):
            self.assertEqual(VERIFY['main'](), 1)

    def test_valid_unit_and_verify_execution_remains_blocked(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, 'argv', ['run_tests_sharded.py']), \
             patch.dict(SHARDED['main'].__globals__, {'collect': lambda *_: ['tests/test_synthetic.py']}), \
             redirect_stdout(StringIO()):
            self.assertEqual(SHARDED['main'](), 1)
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(VERIFY['main'].__globals__['glob'], 'glob',
                          return_value=[str(ROOT / 'tests/verify_synthetic.py')]), \
             redirect_stdout(StringIO()):
            self.assertEqual(VERIFY['main'](), 1)
        # BUG-2026-11-10-010：同 worker 其它用例会在模块导入期 os.chdir 到 app/，
        # 相对路径 'tests/verify_synthetic.py' 便会 FileNotFoundError。这里用仓库绝对路径，
        # 断言仍是「运行时隔离未证明时必须拒绝执行」。
        self.assertNotEqual(VERIFY['_run_one'](str(ROOT / 'tests' / 'verify_synthetic.py'))[1], 0)


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ShardArgumentSafety)
    if suite.countTestCases() != 10:
        raise SystemExit('synthetic test list is incomplete or empty')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
