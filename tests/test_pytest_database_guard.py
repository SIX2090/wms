"""The pytest entry point must reject inherited database targets before app import.

The probe replaces app and pytest with stubs and forbids database, network and
subprocess access, so it is safe to run standalone with the standard library.
"""

import builtins
import os
from pathlib import Path
import runpy
import socket
import sqlite3
import subprocess
import sys
import types
import unittest
from unittest import mock
from scripts import verify_db_guard as runtime_guard


CONFTEST = Path(__file__).resolve().parent / "conftest.py"
MEMORY_URI = "sqlite:///:memory:"


class PytestDatabaseGuardTests(unittest.TestCase):
    def _probe(self, database_url, variable="DATABASE_URL", preloaded=None, grant=True):
        fake_app = types.ModuleType("app")
        fake_pytest = types.ModuleType("pytest")

        def fixture(function=None, **_kwargs):
            return function if function is not None else lambda wrapped: wrapped

        fake_pytest.fixture = fixture
        imports = []
        original_import = builtins.__import__

        def tracked_import(name, *args, **kwargs):
            if name == "app":
                imports.append(name)
                return fake_app
            return original_import(name, *args, **kwargs)

        env = {} if database_url is None else {variable: database_url}
        native_validator = runtime_guard.require_isolated_test_runtime
        if not grant:
            env.update(FLASK_ENV='testing', WMS_TEST_RUNTIME_HANDLE='1')
        with mock.patch.object(runtime_guard, 'require_isolated_test_runtime',
                               side_effect=None if grant else native_validator) as proof, \
                mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.dict(sys.modules, {"pytest": fake_pytest}), \
                mock.patch.object(sys, "path", list(sys.path)), \
                mock.patch.object(builtins, "__import__", side_effect=tracked_import), \
                mock.patch.object(sqlite3, "connect", side_effect=AssertionError("database access")), \
                mock.patch.object(socket.socket, "connect", side_effect=AssertionError("network access")), \
                mock.patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess")):
            sys.modules.pop("app", None)
            sys.modules.pop("app.app", None)
            sys.modules.pop("config", None)
            if preloaded:
                sys.modules[preloaded] = fake_app
            try:
                runpy.run_path(str(CONFTEST), run_name="__database_guard_probe__")
            except (RuntimeError, SystemExit) as exc:
                expected = int(not preloaded and database_url in (None, '', MEMORY_URI))
                self.assertEqual(proof.call_count, expected)
                return imports, os.environ.get(variable), str(exc)
            proof.assert_called_once_with()
            return imports, os.environ.get(variable), None

    def test_memory_target_and_forged_proof_do_not_allow_app_import(self):
        imports, _uri, error = self._probe(MEMORY_URI, grant=False)
        self.assertEqual(imports, [])
        self.assertIsNotNone(error)

    def test_missing_empty_and_explicit_memory_are_safe(self):
        for value in (None, "", MEMORY_URI):
            with self.subTest(value=value):
                imports, actual, error = self._probe(value)
                self.assertIsNone(error)
                self.assertEqual(actual, MEMORY_URI)
                self.assertEqual(imports, ["app"])

    def test_other_targets_are_rejected_before_app_and_redacted(self):
        targets = {
            "relative_file": "sqlite:///synthetic-test.db",
            "path_alias": "sqlite:///../synthetic-test.db",
            "sqlite_uri": "sqlite:///file:fake?mode=memory&uri=true",
            "driver_alias": "sqlite+pysqlite:///:memory:",
            "noncanonical_memory": "sqlite:///:memory:?x=1",
            "empty_sqlite": "sqlite://",
            "whitespace": "  ",
            "other_backend": "postgresql://fake:fixture-secret@invalid.example/db",
        }
        messages = []
        for label, value in targets.items():
            with self.subTest(case=label):
                imports, _actual, error = self._probe(value)
                self.assertIsNotNone(error)
                self.assertEqual(imports, [])
                self.assertNotIn("fixture-secret", error)
                messages.append(error)
        self.assertEqual(len(set(messages)), 1, "拒绝信息不得包含输入目标")

    def test_preloaded_app_or_config_is_rejected_instead_of_reusing_unknown_configuration(self):
        for name in ("app", "app.app", "config"):
            with self.subTest(module=name):
                imports, _actual, error = self._probe(MEMORY_URI, preloaded=name)
                self.assertIsNotNone(error)
                self.assertEqual(imports, [])

    def test_legacy_database_uri_is_also_guarded(self):
        for value in (None, "", MEMORY_URI):
            with self.subTest(case="safe", value=value):
                imports, actual, error = self._probe(value, "WMS_DATABASE_URI")
                self.assertIsNone(error)
                self.assertEqual(actual, MEMORY_URI)
                self.assertEqual(imports, ["app"])
        for value in ("sqlite:///synthetic.db", "postgresql://fake:fixture-secret@invalid.example/db"):
            with self.subTest(case="unsafe"):
                imports, _actual, error = self._probe(value, "WMS_DATABASE_URI")
                self.assertIsNotNone(error)
                self.assertEqual(imports, [])
                self.assertNotIn("fixture-secret", error)


if __name__ == "__main__":
    unittest.main()
