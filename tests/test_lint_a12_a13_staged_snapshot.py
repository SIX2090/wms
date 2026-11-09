"""A12/A13 inspect the Git index, using only disposable synthetic repositories."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


LINTER = Path(__file__).resolve().parents[1] / "scripts" / "lint_wms_rules.py"
BAD_LEDGER = "### BUG-2026-11-08-999: synthetic\n- 根因：模拟\n"
GOOD_LEDGER = BAD_LEDGER + "- 生效确认：待人工确认\n"


class StagedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wms-staged-synthetic-")
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
            cwd=self.root, env=self.env, text=True, encoding="utf-8",
            capture_output=True, check=True,
        )

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def lint(self, rule, env=None):
        return subprocess.run(
            [sys.executable, "-I", "-B", "-X", "utf8", str(LINTER), "--repo-root", str(self.root),
             "--staged", "--rule", rule], cwd=self.root, env=env or self.env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )

    def test_staged_bad_worktree_fixed_still_fails(self):
        for rule, name, bad, good in (
            ("a12", "tests/test_synthetic.py", "ctx.push()\n", "# fixed\n"),
            ("a13", "docs/ledger/bugs/entries-fixture.md", BAD_LEDGER, GOOD_LEDGER),
        ):
            with self.subTest(rule=rule):
                path = self.write(name, bad)
                self.git("add", "--", name)
                path.write_text(good, encoding="utf-8")
                result = self.lint(rule)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_staged_good_worktree_bad_still_passes(self):
        for rule, name, bad, good in (
            ("a12", "tests/test_synthetic.py", "ctx.push()\n", "# fixed\n"),
            ("a13", "docs/ledger/bugs/entries-fixture.md", BAD_LEDGER, GOOD_LEDGER),
        ):
            with self.subTest(rule=rule):
                path = self.write(name, good)
                self.git("add", "--", name)
                path.write_text(bad, encoding="utf-8")
                result = self.lint(rule)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_removed_worktree_file_still_checked(self):
        for rule, name, bad in (
            ("a12", "tests/test_missing.py", "ctx.push()\n"),
            ("a13", "docs/ledger/bugs/entries-missing.md", BAD_LEDGER),
        ):
            with self.subTest(rule=rule):
                path = self.write(name, bad)
                self.git("add", "--", name)
                path.unlink()
                result = self.lint(rule)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_rename_into_scope_with_unicode_and_spaces(self):
        cases = (
            ("a12", "archive/test old.py", "tests/test 中文 名.py", "ctx.push()\n"),
            ("a13", "archive/old ledger.md", "docs/ledger/bugs/条目 空格.md", BAD_LEDGER),
        )
        for rule, source, target, contents in cases:
            with self.subTest(rule=rule):
                self.write(source, contents)
                self.git("add", "--", source)
                self.git("commit", "-q", "-m", "add synthetic source")
                (self.root / target).parent.mkdir(parents=True, exist_ok=True)
                self.git("mv", "--", source, target)
                status = self.git("diff", "--cached", "--name-status", "--find-renames").stdout
                self.assertIn("R100", status)
                result = self.lint(rule)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.git("commit", "-q", "-m", "finish synthetic case")

    def test_same_scope_rename_keeps_historical_entries(self):
        source = "docs/ledger/bugs/old.md"
        target = "docs/ledger/bugs/历史 档案.md"
        self.write(source, BAD_LEDGER)
        self.git("add", "--", source)
        self.git("commit", "-q", "-m", "historical synthetic entry")
        self.git("mv", "--", source, target)
        result = self.lint("a13")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_same_scope_rename_checks_new_entry(self):
        source = "docs/ledger/bugs/old.md"
        target = "docs/ledger/bugs/历史 档案.md"
        self.write(source, "# synthetic\n" + ("historical text\n" * 30))
        self.git("add", "--", source)
        self.git("commit", "-q", "-m", "historical synthetic entries")
        self.git("mv", "--", source, target)
        with (self.root / target).open("a", encoding="utf-8") as stream:
            stream.write(BAD_LEDGER)
        self.git("add", "--", target)
        status = self.git("diff", "--cached", "--name-status", "--find-renames").stdout
        self.assertIn("R", status)
        result = self.lint("a13")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_git_failure_rejects_staged_scan(self):
        env = self.env.copy()
        env["PATH"] = str(self.root / "missing-executables")
        result = self.lint("a12", env)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("无法读取暂存文件列表", result.stderr)


if __name__ == "__main__":
    unittest.main()
