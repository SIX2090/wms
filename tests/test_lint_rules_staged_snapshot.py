"""Index-only rule checks in new synthetic Git repositories."""
import os
import contextlib
import io
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


LINTER = Path(__file__).resolve().parents[1] / "scripts" / "lint_wms_rules.py"


class StagedRulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wms-lint-rules-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.upper().startswith("GIT_")
                    and k.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        template = self.root / "empty-template"
        template.mkdir()
        self.git("init", "-q", "--template", str(template))
        self.git("commit", "-q", "--allow-empty", "-m", "synthetic baseline")

    def git(self, *args):
        return subprocess.run(
            ["git", "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid", *args],
            cwd=self.root, env=self.env, text=True, encoding="utf-8", capture_output=True, check=True)

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def lint(self, rule, *args):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", str(LINTER), "--repo-root", str(self.root),
             "--rule", rule, *args], cwd=self.root, env=self.env, text=True, encoding="utf-8",
            capture_output=True)

    def test_staged_violations_ignore_unstaged_repairs(self):
        samples = (
            ("a1", "app/templates/表单 名.html", '<form method="post"></form>\n'),
            ("a2", "app/route.py", "@app.post('/danger')\ndef route():\n    pass\n"),
            ("a3", "app/static/js/log.js", "console.log(1);\n"),
            ("a4", "app/static/js/debug.js", "debugger;\n"),
            ("a5", "app/static/js/eval.js", "eval('1');\n"),
            ("a6", "app/output.py", "print('x')\n"),
            ("a7", "app/sql.py", "text(f'SELECT * FROM x WHERE id={x}')\n"),
            ("a8", "app/route2.py", "@app.route('/danger', methods=['POST'])\ndef handler():\n    pass\n"),
            ("a9", "app/operation.py", "def fresh_operation():\n    return 1\n"),
            ("a10", "app/app.py", "@app.route('/danger')\ndef handler():\n    pass\n"),
            ("a11", "app/stock.py", "if material.stock < 1:\n    pass\n"),
            ("a14", "scripts/worker.py", "import app\n"),
        )
        for rule, name, bad in samples:
            with self.subTest(rule=rule):
                path = self.write(name, bad)
                self.git("add", "--", name)
                path.write_text("# unstaged repair\n", encoding="utf-8")
                result = self.lint(rule, "--staged")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.git("commit", "-q", "-m", "synthetic sample")

    def test_staged_good_ignores_unstaged_violation_and_deleted_worktree(self):
        name = "app/static/js/check.js"
        path = self.write(name, "// staged clean\n")
        self.git("add", "--", name)
        path.write_text("console.log(1);\n", encoding="utf-8")
        result = self.lint("a3", "--staged")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        path.write_text("console.log(1);\n", encoding="utf-8")
        self.git("add", "--", name)
        path.unlink()
        result = self.lint("a3", "--staged")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_a9_uses_only_index_tests_including_committed_and_staged_deletion(self):
        source = "app/operation.py"
        test = "tests/test_unique.py"
        self.write(source, "def unique_action():\n    return 1\n")
        self.git("add", "--", source)
        self.write(test, "def test_unique_action():\n    pass\n")
        self.assertEqual(self.lint("a9", "--staged").returncode, 1)
        self.git("add", "--", test)
        self.assertEqual(self.lint("a9", "--staged").returncode, 0)
        self.git("commit", "-q", "-m", "add synthetic test and source")
        self.write(source, "def unique_action():\n    return 1\n\ndef another_action():\n    return 2\n")
        self.write(test, "def test_another_action():\n    pass\n")
        self.git("add", "--", source)
        self.assertEqual(self.lint("a9", "--staged").returncode, 1)
        self.git("add", "--", test)
        self.assertEqual(self.lint("a9", "--staged").returncode, 0)
        self.git("commit", "-q", "-m", "add second synthetic action")
        self.write(source, "def unique_action():\n    return 1\n\ndef another_action():\n    return 2\n\ndef third_action():\n    return 3\n")
        self.write(test, "def test_third_action():\n    pass\n")
        self.git("add", "--", source, test)
        self.assertEqual(self.lint("a9", "--staged").returncode, 0)
        self.git("rm", "--cached", "--", test)
        self.assertEqual(self.lint("a9", "--staged").returncode, 1)

    def test_nonstaged_full_scan_keeps_worktree_semantics(self):
        name = "app/static/js/check.js"
        path = self.write(name, "// staged clean\n")
        self.git("add", "--", name)
        path.write_text("console.log(1);\n", encoding="utf-8")
        result = self.lint("a3", "--full")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_new_scope_renames_check_existing_content(self):
        cases = (
            ("a8", "archive/source-a8.py", "app/中文 路由.py", "@app.route('/x', methods=['POST'])\ndef handler():\n    pass\n"),
            ("a9", "archive/source-a9.py", "app/中文 函数.py", "def new_operation():\n    return 1\n"),
            ("a10", "app/old-app.py", "app/app.py", "@app.route('/x')\ndef handler():\n    pass\n"),
            ("a11", "archive/source-a11.py", "app/中文 库存.py", "if material.stock < 1:\n    pass\n"),
            ("a14", "archive/source-a14.py", "scripts/中文 工具.py", "import app\n"),
        )
        for rule, source, target, contents in cases:
            with self.subTest(rule=rule):
                self.write(source, contents)
                self.git("add", "--", source)
                self.git("commit", "-q", "-m", "add synthetic source")
                (self.root / target).parent.mkdir(parents=True, exist_ok=True)
                self.git("mv", "--", source, target)
                self.assertIn("R100", self.git("diff", "--cached", "--name-status", "--find-renames").stdout)
                result = self.lint(rule, "--staged")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.git("commit", "-q", "-m", "finish synthetic rename")

    def test_batch_reads_git_once_and_rejects_object_failure(self):
        self.write("app/operation.py", "def unique_operation():\n    return 1\n")
        for number in range(20):
            self.write(f"tests/test_sample_{number}.py", f"def test_sample_{number}():\n    pass\n")
        self.git("add", "--", "app", "tests")
        namespace = runpy.run_path(str(LINTER))
        real_run = subprocess.run
        calls = []

        def counted(command, *args, **kwargs):
            calls.append(list(command))
            return real_run(command, *args, **kwargs)

        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(subprocess, "run", side_effect=counted), contextlib.redirect_stdout(io.StringIO()):
            code = namespace["main"](["--repo-root", str(self.root), "--staged", "--rule", "a9"])
        self.assertEqual(code, 1)
        self.assertEqual(sum("ls-files" in call for call in calls), 1)
        self.assertEqual(sum("cat-file" in call for call in calls), 1)
        self.assertFalse(any("show" in call for call in calls))

        def failed_blob(command, *args, **kwargs):
            if "cat-file" in command:
                return subprocess.CompletedProcess(command, 1, b"", b"synthetic failure")
            return real_run(command, *args, **kwargs)

        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(subprocess, "run", side_effect=failed_blob):
            with self.assertRaisesRegex(RuntimeError, "暂存快照"):
                namespace["main"](["--repo-root", str(self.root), "--staged", "--rule", "a9"])


if __name__ == "__main__":
    unittest.main()
