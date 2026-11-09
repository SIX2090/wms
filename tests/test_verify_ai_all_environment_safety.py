"""Dispatcher environment checks; subprocesses and database access are mocked."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from scripts import verify_ai_all


class TestVerifyAiAllEnvironmentSafety(TestCase):
    def test_rejects_untrusted_database_without_starting_child_or_exposing_value(self):
        unsafe_urls = (
            "postgresql://synthetic-user:synthetic-secret@example.invalid/db",
            "sqlite:///synthetic-existing.db",
            "sqlite:///file:synthetic?mode=memory&cache=shared",
            "sqlite:///:memory:?cache=shared",
        )
        for key in ("DATABASE_URL", "WMS_DATABASE_URI"):
            for url in unsafe_urls:
                with self.subTest(key=key, url=url), patch.dict(os.environ, {key: url}, clear=True), \
                        patch.object(verify_ai_all.subprocess, "run") as child:
                    output = StringIO()
                    with redirect_stdout(output):
                        result = verify_ai_all.run_script("verify_ai_ledger_consistency.py")
                    self.assertEqual(child.call_count, 0)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn(url, output.getvalue())
                    self.assertNotIn("synthetic-secret", output.getvalue())

    def test_child_uses_testing_memory_and_per_script_temporary_file(self):
        seen_paths = []

        def fake_run(*args, **kwargs):
            env = kwargs["env"]
            self.assertEqual(env["FLASK_ENV"], "testing")
            self.assertEqual(env["DATABASE_URL"], "sqlite:///:memory:")
            self.assertEqual(env["AI_LEDGER_ENFORCE"], "strict")
            path = Path(env["WMS_DATABASE_URI"].removeprefix("sqlite:///"))
            self.assertEqual(path.name, "inventory-test.db")
            self.assertTrue(path.parent.is_dir())
            seen_paths.append(path)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:",
                                    "FLASK_ENV": "testing",
                                    "AI_LEDGER_ENFORCE": "gradual"}, clear=True), \
                patch.object(verify_ai_all.subprocess, "run", side_effect=fake_run), \
                redirect_stdout(StringIO()):
            for _ in range(2):
                result = verify_ai_all.run_script("verify_ai_ledger_consistency.py")
                self.assertEqual(result.returncode, 0)
        self.assertNotEqual(seen_paths[0], seen_paths[1])
        self.assertTrue(all(not path.parent.exists() for path in seen_paths))

    def test_explicit_non_testing_environment_is_rejected(self):
        with patch.dict(os.environ, {"DATABASE_URL": "sqlite:///:memory:",
                                    "FLASK_ENV": "production"}, clear=True), \
                patch.object(verify_ai_all.subprocess, "run") as child, \
                redirect_stdout(StringIO()):
            result = verify_ai_all.run_script("verify_ai_ledger_consistency.py")
            self.assertEqual(child.call_count, 0)
            self.assertNotEqual(result.returncode, 0)

    def test_unset_or_empty_database_url_is_forced_to_memory(self):
        for value in (None, ""):
            with self.subTest(value=value), patch.dict(os.environ, {}, clear=True):
                if value is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = value
                env = verify_ai_all._verification_environment(Path("synthetic.db"))
                self.assertEqual(env["DATABASE_URL"], "sqlite:///:memory:")
                self.assertEqual(env["FLASK_ENV"], "testing")

    def test_child_python_import_path_does_not_inherit_untrusted_overrides(self):
        inherited = {"DATABASE_URL": "sqlite:///:memory:",
                     "PYTHONPATH": "synthetic-untrusted-path",
                     "PYTHONHOME": "synthetic-untrusted-home",
                     "PYTHONNOUSERSITE": "0",
                     "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "0"}
        with patch.dict(os.environ, inherited, clear=True):
            env = verify_ai_all._verification_environment(Path("synthetic.db"))
        self.assertFalse("PYTHONHOME" in env)
        self.assertEqual(env["PYTHONPATH"], str(verify_ai_all.ROOT / "app"))
        self.assertNotIn("synthetic-untrusted-path", env["PYTHONPATH"])
        self.assertEqual(env["PYTHONNOUSERSITE"], "1")
        self.assertEqual(env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")

    def test_inherited_pytest_plugins_and_options_are_rejected(self):
        for key, value in (("PYTEST_PLUGINS", "synthetic_plugin"),
                           ("PYTEST_ADDOPTS", "--noconftest")):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}, clear=True), \
                    self.assertRaises(ValueError):
                verify_ai_all._verification_environment(Path("synthetic.db"))

    def test_empty_script_list_is_not_success(self):
        with patch.object(verify_ai_all, "scripts_for_level", return_value=()), \
                patch.object(sys, "argv", ["verify_ai_all.py"]), \
                patch.object(verify_ai_all.subprocess, "run") as child, \
                redirect_stdout(StringIO()):
            self.assertNotEqual(verify_ai_all.main(), 0)
            child.assert_not_called()
