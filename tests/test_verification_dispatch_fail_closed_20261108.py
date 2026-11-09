"""Offline tests for suspended dispatch; no WMS import, DB, network or children."""
import os
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SHARDED = runpy.run_path(str(ROOT / 'scripts' / 'run_tests_sharded.py'))
VERIFY = runpy.run_path(str(ROOT / 'scripts' / 'run_verify_parallel.py'))
MESSAGE = '数据库、备份与网络隔离尚未证明'


def refuse(*_args, **_kwargs):
    raise AssertionError('forbidden external action')


class DispatcherFailClosed(unittest.TestCase):
    def setUp(self):
        for target in (mock.patch.object(socket.socket, 'connect', refuse),
                       mock.patch.object(socket.socket, 'connect_ex', refuse),
                       mock.patch.object(socket, 'getaddrinfo', refuse),
                       mock.patch.object(sqlite3, 'connect', refuse),
                       mock.patch.object(subprocess, 'Popen', refuse),
                       mock.patch.object(subprocess, 'run', refuse),
                       mock.patch.object(subprocess, 'call', refuse)):
            target.start()
            self.addCleanup(target.stop)

    def test_sharded_list_remains_read_only_and_nonempty(self):
        main = SHARDED['main']
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(sys, 'argv', ['run_tests_sharded.py', '--list']), \
                mock.patch.dict(main.__globals__, {'collect': lambda *_: ['tests/test_synthetic.py']}), \
                redirect_stdout(StringIO()) as output:
            self.assertEqual(main(), 0)
        self.assertIn('tests/test_synthetic.py', output.getvalue())

    def test_sharded_refuses_execution_even_with_memory_environment(self):
        main = SHARDED['main']
        env = {'DATABASE_URL': 'sqlite:///:memory:', 'WMS_DATABASE_URI': 'sqlite:///:memory:'}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, 'argv', ['run_tests_sharded.py']), \
                mock.patch.dict(main.__globals__, {'collect': lambda *_: ['tests/test_synthetic.py']}), \
                redirect_stdout(StringIO()) as output:
            self.assertNotEqual(main(), 0)
        self.assertIn(MESSAGE, output.getvalue())

    def test_verify_main_refuses_before_pool(self):
        main = VERIFY['main']
        env = {'DATABASE_URL': 'sqlite:///:memory:', 'WMS_DATABASE_URI': 'sqlite:///:memory:'}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(main.__globals__['glob'], 'glob', return_value=['tests/verify_synthetic.py']), \
                mock.patch.dict(main.__globals__, {'ThreadPoolExecutor': refuse}), \
                redirect_stdout(StringIO()) as output:
            self.assertNotEqual(main(), 0)
        self.assertIn(MESSAGE, output.getvalue())

    def test_verify_direct_helper_refuses_before_file_or_child(self):
        run = VERIFY['_run_one']
        with mock.patch.dict(os.environ, {'FLASK_ENV': 'testing'}, clear=True), \
                mock.patch.dict(run.__globals__, {'_is_pytest_style': refuse}):
            path, rc, elapsed, output = run('tests/verify_synthetic.py')
        self.assertEqual(path, 'tests/verify_synthetic.py')
        self.assertNotEqual(rc, 0)
        self.assertEqual(elapsed, 0.0)
        self.assertIn(MESSAGE, output)

    def test_empty_lists_remain_failure(self):
        main = SHARDED['main']
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(sys, 'argv', ['run_tests_sharded.py', '--list']), \
                mock.patch.dict(main.__globals__, {'collect': lambda *_: []}), \
                redirect_stdout(StringIO()):
            self.assertNotEqual(main(), 0)


if __name__ == '__main__':
    unittest.main()
