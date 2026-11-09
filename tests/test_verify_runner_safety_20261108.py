"""The verify dispatcher must never inherit an unknown database target.

This standalone regression uses mocks only: no app, database, network or child
process is started. Run with ``python -I -B tests/test_verify_runner_safety_20261108.py``.
"""
from pathlib import Path
import os
import runpy
import socket
import sqlite3
import sys
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def forbidden(*args, **kwargs):
    raise AssertionError('real database, network or subprocess is forbidden')


ROOT = Path(__file__).resolve().parent.parent
RUN_ONE = runpy.run_path(str(ROOT / 'scripts' / 'run_verify_parallel.py'))['_run_one']
MAIN = RUN_ONE.__globals__['main']
SHARDED_MAIN = runpy.run_path(str(ROOT / 'scripts' / 'run_tests_sharded.py'))['main']


class VerifyRunnerSafety(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(socket.socket, 'connect', forbidden),
                       patch.object(socket.socket, 'connect_ex', forbidden),
                       patch.object(socket, 'create_connection', forbidden),
                       patch.object(socket, 'getaddrinfo', forbidden),
                       patch.object(sqlite3, 'connect', forbidden)):
            target.start()
            self.addCleanup(target.stop)

    def invoke(self, environment):
        child = SimpleNamespace(returncode=0, stdout='verified', stderr='')
        with patch.dict(os.environ, environment, clear=True), \
             patch.dict(RUN_ONE.__globals__, {'_is_pytest_style': lambda _: True}), \
             patch('subprocess.run', return_value=child) as run:
            result = RUN_ONE('tests/verify_fake.py')
        return result, run

    def test_unknown_targets_fail_before_starting_a_child(self):
        for key in ('DATABASE_URL', 'WMS_DATABASE_URI'):
            with self.subTest(key=key):
                secret = 'sqlite:///synthetic-unknown-secret.db'
                result, run = self.invoke({key: secret})
                self.assertNotEqual(result[1], 0)
                self.assertNotIn(secret, result[3])
                run.assert_not_called()

    def test_injected_pytest_arguments_and_plugins_are_rejected(self):
        for key, value in (('PYTEST_ADDOPTS', '--noconftest'),
                           ('PYTEST_PLUGINS', 'synthetic_plugin'),
                           ('PYTHONPATH', 'synthetic-path'),
                           ('PYTHONHOME', 'synthetic-home')):
            with self.subTest(key=key):
                result, run = self.invoke({key: value})
                self.assertNotEqual(result[1], 0)
                run.assert_not_called()

    def test_non_testing_flask_environment_fails_before_starting_child(self):
        for value in ('production', 'development', 'synthetic-unknown', ' '):
            with self.subTest(value=value):
                result, run = self.invoke({'FLASK_ENV': value})
                self.assertNotEqual(result[1], 0)
                run.assert_not_called()

    def test_empty_or_testing_flask_environment_forces_testing(self):
        for value in (None, '', 'testing'):
            with self.subTest(value=value):
                environment = {} if value is None else {'FLASK_ENV': value}
                result, run = self.invoke(environment)
                self.assertEqual(result[1], 0)
                self.assertEqual(run.call_args.kwargs['env']['FLASK_ENV'], 'testing')

    def test_child_receives_explicit_memory_database(self):
        for value in (None, '', 'sqlite:///:memory:'):
            with self.subTest(value=value):
                environment = {} if value is None else {'DATABASE_URL': value}
                result, run = self.invoke(environment)
                self.assertEqual(result[1], 0)
                self.assertEqual(result[3], 'verified')
                child_env = run.call_args.kwargs['env']
                self.assertEqual(child_env['DATABASE_URL'], 'sqlite:///:memory:')
                self.assertEqual(child_env['WMS_DATABASE_URI'], 'sqlite:///:memory:')

    def test_pytest_plugins_are_explicitly_controlled(self):
        result, child = self.invoke({'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '0',
                                     'PYTHONNOUSERSITE': '0'})
        self.assertEqual(result[1], 0)
        self.assertEqual(child.call_args.kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'], '1')
        self.assertEqual(child.call_args.kwargs['env']['PYTHONNOUSERSITE'], '1')

        with patch.dict(os.environ, {'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '0',
                                     'PYTHONNOUSERSITE': '0'}, clear=True), \
             patch.object(sys, 'argv', ['run_tests_sharded.py']), \
             patch.dict(SHARDED_MAIN.__globals__, {'collect': lambda *_: ['tests/test_fake.py']}), \
             patch('subprocess.call', return_value=0) as sharded, redirect_stdout(StringIO()):
            self.assertEqual(SHARDED_MAIN(), 0)
            self.assertEqual(sharded.call_args.kwargs['env']['PYTEST_DISABLE_PLUGIN_AUTOLOAD'], '1')
            self.assertEqual(sharded.call_args.kwargs['env']['PYTHONNOUSERSITE'], '1')
            cmd = sharded.call_args.args[0]
            self.assertIn('xdist.plugin', cmd)
            self.assertIn('-p', cmd)

    def test_empty_test_list_is_failure(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(RUN_ONE.__globals__['glob'], 'glob', return_value=[]), \
             patch('subprocess.run', side_effect=forbidden), \
             redirect_stdout(StringIO()):
            self.assertNotEqual(MAIN(), 0)

    def test_collecting_safety_tests_does_not_change_process_guards(self):
        before = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo, sqlite3.connect)
        before_path = list(sys.path)
        for filename in ('test_auto_update_stash_safety_20261108.py',
                         'test_verify_runner_safety_20261108.py',
                         'test_smoke_socket_capability.py'):
            with self.subTest(filename=filename):
                runpy.run_path(str(ROOT / 'tests' / filename), run_name='collection_probe')
                after = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo, sqlite3.connect)
                self.assertEqual(after, before)
                self.assertEqual(sys.path, before_path)

    def test_sharded_runner_rejects_empty_and_unknown_targets(self):
        for environment, files in (({}, []),
                                   ({'DATABASE_URL': 'sqlite:///unknown.db'}, ['tests/test_fake.py']),
                                   ({'WMS_DATABASE_URI': 'sqlite:///unknown.db'}, ['tests/test_fake.py']),
                                   ({'PYTEST_ADDOPTS': '--noconftest'}, ['tests/test_fake.py']),
                                   ({'PYTEST_PLUGINS': 'synthetic_plugin'}, ['tests/test_fake.py']),
                                   ({'PYTHONPATH': 'synthetic-path'}, ['tests/test_fake.py']),
                                   ({'PYTHONHOME': 'synthetic-home'}, ['tests/test_fake.py'])):
            with self.subTest(environment=environment, files=files), \
                 patch.dict(os.environ, environment, clear=True), \
                 patch.object(sys, 'argv', ['run_tests_sharded.py']), \
                 patch.dict(SHARDED_MAIN.__globals__, {'collect': lambda *_: files}), \
                 patch('subprocess.call') as child, redirect_stdout(StringIO()):
                self.assertNotEqual(SHARDED_MAIN(), 0)
                child.assert_not_called()

    def test_sharded_runner_sets_child_database_targets(self):
        files = ['tests/test_fake.py']
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(sys, 'argv', ['run_tests_sharded.py']), \
             patch.dict(SHARDED_MAIN.__globals__, {'collect': lambda *_: files}), \
             patch('subprocess.call', return_value=0) as child, redirect_stdout(StringIO()):
            self.assertEqual(SHARDED_MAIN(), 0)
            env = child.call_args.kwargs['env']
            self.assertEqual(env['DATABASE_URL'], 'sqlite:///:memory:')
            self.assertEqual(env['WMS_DATABASE_URI'], 'sqlite:///:memory:')


if __name__ == '__main__':
    unittest.main()
