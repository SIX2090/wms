"""Exercise fetch lint against a synthetic Git index, never a WMS runtime."""
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class FetchStagedSnapshotTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("Git is required")
        self.temp = tempfile.TemporaryDirectory(prefix="wms-fetch-index-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.upper().startswith("GIT_") and k.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, PYTHONIOENCODING="utf-8")
        template = self.root / "empty-template"
        template.mkdir()
        self.git("init", "-q", "--template", str(template))
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/lint_no_raw_post_fetch.py", self.root / "scripts/lint_no_raw_post_fetch.py")
        shutil.copy2(ROOT / "scripts/fetch_ast.py", self.root / "scripts/fetch_ast.py")
        shutil.copytree(ROOT / "vendor", self.root / "vendor", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], env=self.env, check=True,
                              capture_output=True, text=True, encoding="utf-8")

    def put(self, path, text, stage=True):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        if stage:
            self.git("add", "--", path)
        return target

    def lint(self, *args):
        return subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(self.root / "scripts/lint_no_raw_post_fetch.py"),
                               "--repo-root", str(self.root), *args], env=self.env, cwd=self.root,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_staged_violation_and_clean_worktree(self):
        self.put("app/static/js/测试 one.js", "fetch('/fake', {method: 'POST'});\n")
        self.put("app/static/js/测试 one.js", "const safe = 1;\n", stage=False)
        self.assertEqual(self.lint("--staged").returncode, 1)
        self.assertEqual(self.lint().returncode, 0)

    def test_clean_index_and_worktree_violation(self):
        self.put("app/static/js/example.js", "const safe = 1;\n")
        self.put("app/static/js/example.js", "fetch('/fake', {method: 'POST'});\n", stage=False)
        self.assertEqual(self.lint("--staged").returncode, 0)
        self.assertEqual(self.lint().returncode, 1)

    def test_deleted_worktree_still_checks_index(self):
        target = self.put("app/static/js/example.js", "fetch('/fake', {method: 'PUT'});\n")
        target.unlink()
        self.assertEqual(self.lint("--staged").returncode, 1)

    def test_renamed_js_checks_destination_snapshot(self):
        self.put("archive/旧 name.js", "fetch('/fake', {method: 'POST'});\n")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "base")
        (self.root / "app/static/js").mkdir(parents=True)
        self.git("mv", "--", "archive/旧 name.js", "app/static/js/新 name.js")
        self.assertEqual(self.lint("--staged").returncode, 1)

    def test_templates_warn_and_strict(self):
        self.put("app/templates/nested/测试 模板.html", "<script>fetch('/fake', {method: 'POST'});</script>\n")
        warn = self.lint("--staged")
        strict = self.lint("--staged", "--templates-strict")
        self.assertEqual(warn.returncode, 0)
        self.assertIn("app/templates/", warn.stdout)
        self.assertEqual(strict.returncode, 1)
        self.assertIn("app/templates/", strict.stdout)
        self.assertEqual(self.lint().returncode, 0)
        self.assertEqual(self.lint("--templates-strict").returncode, 1)

    def test_git_failure_does_not_pass(self):
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-X", "utf8", str(self.root / "scripts/lint_no_raw_post_fetch.py"),
                                 "--repo-root", str(self.root / "missing"), "--staged"], env=self.env,
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_index_blob_fails_closed(self):
        lint = runpy.run_path(str(self.root / "scripts/lint_no_raw_post_fetch.py"))
        oid = b"a" * 40
        listing = b"100644 " + oid + b" 0\tapp/static/js/example.js\0"
        def fake_git(command, **_kwargs):
            if "ls-files" in command:
                return subprocess.CompletedProcess(command, 0, stdout=listing)
            raise subprocess.CalledProcessError(1, command)
        with patch.object(subprocess, "run", side_effect=fake_git):
            with self.assertRaises(RuntimeError):
                lint["scan_staged"](self.root)

    def test_precommit_uses_staged_content(self):
        bash = shutil.which("bash")
        if not bash:
            git = shutil.which("git")
            candidate = Path(git).resolve().parent.parent / "bin/bash.exe"
            bash = str(candidate) if candidate.is_file() else None
        if not bash:
            self.skipTest("Bash is required for the hook")
        shutil.copy2(ROOT / "scripts/lint_wms_rules.py", self.root / "scripts/lint_wms_rules.py")
        hook = self.root / "pre-commit"
        shutil.copy2(ROOT / ".githooks/pre-commit", hook)
        self.put("app/static/js/example.js", "fetch('/fake', {method: 'POST'});\n")
        self.put("app/static/js/example.js", "const safe = 1;\n", stage=False)
        result = subprocess.run([bash, str(hook)], env=self.env, cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("fetch", result.stdout.lower())

    def test_nested_business_post_rejected_in_index_and_full_scan(self):
        self.put("app/static/js/pages/nested.js", "fetch('/synthetic', {method: 'POST'});\n")
        staged, full = self.lint("--staged"), self.lint()
        self.assertEqual(staged.returncode, 1)
        self.assertEqual(full.returncode, 1)
        self.assertIn("pages/nested.js", staged.stdout)
        self.assertIn("pages/nested.js", full.stdout)

    def test_nested_app_js_does_not_inherit_root_whitelist(self):
        self.put("app/static/js/pages/app.js", "fetch('/synthetic', {method: 'POST'});\n")
        self.assertEqual(self.lint("--staged").returncode, 1)
        self.assertEqual(self.lint().returncode, 1)

    def test_nested_chinese_path_is_reported(self):
        path = "app/static/js/页面/明细.js"
        self.put(path, "fetch('/synthetic', {method: 'POST'});\n")
        result = self.lint("--staged")
        self.assertEqual(result.returncode, 1)
        self.assertIn(path, result.stdout)

    def test_nested_arguments_and_url_literals_are_scanned(self):
        self.put("app/static/js/pages/request.js",
                 "fetch(makeUrl('https://synthetic.invalid/a'), {method: 'POST'});\n")
        self.assertEqual(self.lint("--staged").returncode, 1)
        self.assertEqual(self.lint().returncode, 1)

    def test_fetch_example_in_string_is_not_executable(self):
        self.put("app/static/js/pages/example.js",
                 'const example = "fetch(\'/synthetic\', {method: \'POST\'})";\n')
        self.assertEqual(self.lint("--staged").returncode, 0)
        self.assertEqual(self.lint().returncode, 0)

    def test_template_nested_call_uses_existing_warn_strict_policy(self):
        self.put("app/templates/nested/example.html",
                 "<script>fetch(makeUrl('https://synthetic.invalid'), {method:'POST'});</script>\n")
        self.assertEqual(self.lint("--staged").returncode, 0)
        self.assertEqual(self.lint("--staged", "--templates-strict").returncode, 1)

    def test_approved_root_app_js_and_safe_nested_calls_remain_allowed(self):
        self.put("app/static/js/app.js", "fetch('/synthetic', {method: 'POST'});\n")
        self.put("app/static/js/pages/safe.js", "WMS.api.post('/synthetic', {});\nfetch('/synthetic');\n")
        self.assertEqual(self.lint("--staged").returncode, 0)
        self.assertEqual(self.lint().returncode, 0)

    def test_precommit_rejects_nested_nonget_fetch(self):
        bash = shutil.which("bash")
        if not bash:
            git = shutil.which("git")
            candidate = Path(git).resolve().parent.parent / "bin/bash.exe"
            bash = str(candidate) if candidate.is_file() else None
        self.assertIsNotNone(bash, "Git Bash is required for the hook check")
        shutil.copy2(ROOT / "scripts/lint_wms_rules.py", self.root / "scripts/lint_wms_rules.py")
        hook = self.root / "pre-commit"
        shutil.copy2(ROOT / ".githooks/pre-commit", hook)
        self.put("app/static/js/pages/nested.js", "fetch('/synthetic', {method: 'POST'});\n")
        result = subprocess.run([bash, str(hook)], env=self.env, cwd=self.root,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("pages/nested.js", result.stdout)


if __name__ == "__main__":
    unittest.main()
