"""Run the real hook and linter only in new synthetic Git repositories."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def find_bash():
    bash = shutil.which("bash")
    if bash:
        return bash
    git = shutil.which("git")
    if git:
        candidate = Path(git).resolve().parent.parent / "bin" / "bash.exe"
        if candidate.is_file():
            return str(candidate)
    return None


class PreCommitRelevantPathsTests(unittest.TestCase):
    def setUp(self):
        self.bash = find_bash()
        if not self.bash or not shutil.which("git"):
            self.skipTest("Git 和 Bash 是钩子测试的必要条件")
        self.temp = tempfile.TemporaryDirectory(prefix="wms-hook-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.upper().startswith("GIT_")
                    and key.upper() not in {"PYTHONPATH", "PYTHONHOME"}}
        self.env["PYTHONIOENCODING"] = "utf-8"
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull
        template = self.repo / "empty-template"
        template.mkdir()
        self.git("init", "-q", "--template", str(template))
        (self.repo / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/lint_wms_rules.py", self.repo / "scripts/lint_wms_rules.py")
        shutil.copy2(ROOT / "scripts/lint_no_raw_post_fetch.py",
                     self.repo / "scripts/lint_no_raw_post_fetch.py")
        shutil.copy2(ROOT / "scripts/fetch_ast.py", self.repo / "scripts/fetch_ast.py")
        shutil.copytree(ROOT / "vendor", self.repo / "vendor", ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        self.hook = self.repo / "pre-commit"
        shutil.copy2(ROOT / ".githooks/pre-commit", self.hook)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], env=self.env,
                              check=True, capture_output=True, text=True, encoding="utf-8")

    def run_hook(self, filename, contents):
        path = self.repo / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        self.git("add", "--", filename)
        return subprocess.run([self.bash, str(self.hook)], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def rename_and_run_hook(self, source, destination, contents):
        path = self.repo / source
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
        self.git("add", "--", source)
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "core.hooksPath=empty-template", "commit", "-qm", "synthetic base")
        (self.repo / destination).parent.mkdir(parents=True, exist_ok=True)
        self.git("mv", "--", source, destination)
        return subprocess.run([self.bash, str(self.hook)], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_tests_only_rejects_a12_violation(self):
        result = self.run_hook("tests/test_synthetic.py", "ctx.push()\n")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a12", result.stdout.lower())

    def test_ledger_only_rejects_missing_confirmation(self):
        for filename in ("WMS_BUG_BASELINE.md", "docs/ledger/bugs/entries-fixture.md"):
            with self.subTest(file=filename):
                result = self.run_hook(filename, "### BUG-2026-11-08-999: synthetic\n- 根因：模拟\n")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("a13", result.stdout.lower())
                self.git("reset", "--", filename)

    def test_valid_ledger_and_ordinary_docs_keep_expected_routing(self):
        result = self.run_hook("docs/ledger/bugs/entries-fixture.md",
                               "### BUG-2026-11-08-999: synthetic\n- 生效确认：待人工确认\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WMS", result.stdout)
        self.git("reset", "--", "docs/ledger/bugs/entries-fixture.md")
        result = self.run_hook("docs/audit/fixture.md", "# synthetic\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("WMS 多规则", result.stdout)

    def test_renamed_test_cannot_bypass_a12(self):
        result = self.rename_and_run_hook("archive/synthetic.py", "tests/test_synthetic.py", "ctx.push()\n")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a12", result.stdout.lower())

    def test_renamed_ledger_cannot_bypass_a13(self):
        result = self.rename_and_run_hook("archive/synthetic.md", "docs/ledger/bugs/entries-fixture.md",
                                          "### BUG-2026-11-08-999: synthetic\n- 根因：模拟\n")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a13", result.stdout.lower())

    def test_unicode_and_space_test_path_cannot_bypass_a12(self):
        result = self.run_hook("tests/测试 样例.py", "ctx.push()\n")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a12", result.stdout.lower())

    def test_unicode_and_space_ledger_path_cannot_bypass_a13(self):
        result = self.run_hook("docs/ledger/bugs/测试 台账.md",
                               "### BUG-2026-11-08-999: synthetic\n- 根因：模拟\n")
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a13", result.stdout.lower())

    def test_existing_code_paths_still_invoke_checks(self):
        for filename, content in (("app/synthetic.py", "x = 1\n"),
                                  ("scripts/synthetic.py", "x = 1\n"),
                                  ("app/static/js/脚本 one.js", "const x = 1;\n")):
            with self.subTest(file=filename):
                result = self.run_hook(filename, content)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("[pre-commit] WMS", result.stdout)
                if filename.endswith(".js"):
                    self.assertIn("fetch", result.stdout)


if __name__ == "__main__":
    unittest.main()
