"""Synthetic Git index tests; never access WMS data, network or its index."""
import importlib.util
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LINT_PATH = ROOT / 'scripts/lint_wms_rules.py'
SPEC = importlib.util.spec_from_file_location('synthetic_lint_staged_raw', LINT_PATH)
lint = importlib.util.module_from_spec(SPEC)
with mock.patch.dict(sys.modules, {SPEC.name: lint}):
    SPEC.loader.exec_module(lint)


def deny(*_args, **_kwargs):
    raise AssertionError('network and databases are forbidden')


class RawGitPaths(unittest.TestCase):
    def setUp(self):
        for guard in (mock.patch.object(socket.socket, 'connect', deny),
                      mock.patch.object(socket.socket, 'connect_ex', deny),
                      mock.patch.object(socket, 'getaddrinfo', deny),
                      mock.patch.object(sqlite3, 'connect', deny)):
            guard.start()
            self.addCleanup(guard.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='wms-git-path-')
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH') if key in os.environ}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='file')
        self.git('init', '-b', 'main')

    def git(self, *args, input=None):
        if not args or args[0] not in {'init', 'add', 'commit', 'diff', 'status', 'hash-object', 'update-index'}:
            raise AssertionError('unsupported Git command')
        if self.repo != Path(self.temp.name).resolve():
            raise AssertionError('synthetic repository identity changed')
        cmd = ['git', '-c', 'core.hooksPath=' + str(self.repo / 'no-hooks'),
               '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', *args]
        result = subprocess.run(cmd, cwd=self.repo, env=self.env, input=input, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, 'synthetic Git failed')
        return result.stdout

    def write(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding='utf-8')
        return path

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-m', 'synthetic baseline')

    def run_a13(self):
        return subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(LINT_PATH),
                               '--staged', '--rule', 'a13', '--repo-root', str(self.repo)],
                              cwd=self.repo, env=self.env, capture_output=True, timeout=20)

    def test_ambiguous_space_path_is_checked_from_index(self):
        path = self.write('docs/ledger/bugs/中文 b/entry.md',
                          '### BUG-2026-11-08-100: initial\n- 生效确认：待确认\n')
        self.commit()
        path.write_text(path.read_text(encoding='utf-8') +
                        '\n### BUG-2026-11-08-101: missing proof\n- 状态：已修复\n', encoding='utf-8')
        self.git('add', '-A')
        # The worktree is now different from the index: only the latter matters.
        path.write_text(path.read_text(encoding='utf-8') + '- 生效确认：待确认\n', encoding='utf-8')
        result = self.run_a13()
        self.assertEqual(result.returncode, 1)
        self.assertIn('生效确认'.encode(), result.stdout)

    def test_clean_index_not_affected_by_unstaged_violation(self):
        path = self.write('docs/ledger/bugs/测试 b/entry.md',
                          '### BUG-2026-11-08-100: initial\n- 生效确认：待确认\n')
        self.commit()
        path.write_text(path.read_text(encoding='utf-8') +
                        '\n### BUG-2026-11-08-101: good\n- 生效确认：待确认\n', encoding='utf-8')
        self.git('add', '-A')
        path.write_text(path.read_text(encoding='utf-8') +
                        '\n### BUG-2026-11-08-102: unstaged only\n', encoding='utf-8')
        self.assertEqual(self.run_a13().returncode, 0)

    def test_raw_records_pair_renames_deletions_and_modified_unicode(self):
        original = self.write('docs/ledger/bugs/旧 b/source.md', ''.join('line %s\n' % n for n in range(30)))
        self.write('docs/ledger/bugs/删除.md', 'old\n')
        changed = self.write('docs/ledger/bugs/特殊 [x] b/路径.md', 'old\n')
        self.commit()
        renamed = self.repo / 'docs/ledger/bugs/新 b/destination.md'
        renamed.parent.mkdir(parents=True)
        original.rename(renamed)
        with renamed.open('a', encoding='utf-8') as handle:
            handle.write('new\n')
        (self.repo / 'docs/ledger/bugs/删除.md').unlink()
        changed.write_text('old\nnew\n', encoding='utf-8')
        self.git('add', '-A')
        raw = self.git('diff', '--cached', '--raw', '-z', '--patch', '--unified=0',
                       '--find-renames', '--no-color', '--no-ext-diff', '--no-textconv')
        records, lines = lint._parse_staged_raw_patch(raw)
        statuses = {target: status for status, _, target in records}
        self.assertTrue(statuses['docs/ledger/bugs/新 b/destination.md'].startswith('R'))
        self.assertEqual(statuses['docs/ledger/bugs/删除.md'], 'D')
        self.assertEqual(statuses['docs/ledger/bugs/特殊 [x] b/路径.md'], 'M')
        self.assertEqual(lines['docs/ledger/bugs/新 b/destination.md'], {31})
        self.assertEqual(lines['docs/ledger/bugs/删除.md'], set())
        self.assertEqual(lines['docs/ledger/bugs/特殊 [x] b/路径.md'], {2})

    def test_raw_parser_preserves_trailing_space_and_control_characters(self):
        path1 = 'docs/ledger/bugs/a b/name.md '
        path2 = 'docs/ledger/bugs/中\t文\nname.md'
        head = b':100644 100644 abc123 def456 M\0'
        raw = (head + path1.encode() + b'\0' + head + path2.encode() + b'\0\0'
               + b'diff --git ambiguous\n@@ -1 +1,2 @@\n old\n+new\n'
               + b'diff --git ambiguous\n@@ -1 +1,2 @@\n old\n+other\n')
        records, lines = lint._parse_staged_raw_patch(raw)
        self.assertEqual([target for _, _, target in records], [path1, path2])
        self.assertEqual(lines, {path1: {2}, path2: {2}})

    def test_missing_patch_or_incomplete_raw_fails_closed(self):
        head = b':100644 100644 abc123 def456 M\0synthetic.txt\0'
        for raw in (head, head + b'\0', head + b'\0diff --git a/x b/x\n'
                    + b'diff --git a/y b/y\n', b'\0'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                lint._parse_staged_raw_patch(raw)

    def test_hunk_content_and_no_newline_marker_keep_line_numbers(self):
        patch = ('@@ -1 +1,2 @@\n-old\n\\ No newline at end of file\n'
                 '+++literal-content\n+next\n\\ No newline at end of file\n')
        self.assertEqual(lint._parse_added_lines_for_file(patch), {1, 2})

    def test_type_change_is_rejected_by_lint_and_actual_hook(self):
        bash = shutil.which('bash')
        git = shutil.which('git')
        if not bash and git:
            candidate = Path(git).resolve().parent.parent / 'bin' / 'bash.exe'
            if candidate.is_file():
                bash = str(candidate)
        self.assertIsNotNone(bash, 'Git Bash is required for the hook check')
        self.write('app/routes/synthetic.py', 'value = 1\n')
        (self.repo / 'scripts').mkdir(exist_ok=True)
        (self.repo / '.githooks').mkdir(exist_ok=True)
        shutil.copy2(LINT_PATH, self.repo / 'scripts/lint_wms_rules.py')
        shutil.copy2(ROOT / '.githooks/pre-commit', self.repo / '.githooks/pre-commit')
        self.commit()
        object_id = self.git('hash-object', '-w', '--stdin', input=b'synthetic-target').decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '120000', object_id, 'app/routes/synthetic.py')
        self.assertIn(b'T\tapp/routes/synthetic.py', self.git('diff', '--cached', '--name-status'))
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(LINT_PATH),
                                 '--staged', '--rule', 'a6', '--repo-root', str(self.repo)],
                                cwd=self.repo, env=self.env, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0, 'type change must not bypass staged lint')
        result = subprocess.run([bash, str(self.repo / '.githooks/pre-commit')], cwd=self.repo,
                                env=self.env, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, 'type change must not bypass the actual hook')

    def test_unmerged_index_is_rejected_before_rule_scan(self):
        bash = shutil.which('bash')
        git = shutil.which('git')
        if not bash and git:
            candidate = Path(git).resolve().parent.parent / 'bin' / 'bash.exe'
            if candidate.is_file():
                bash = str(candidate)
        self.assertIsNotNone(bash, 'Git Bash is required for the hook check')
        self.write('app/routes/synthetic.py', 'value = 1\n')
        (self.repo / 'scripts').mkdir(exist_ok=True)
        (self.repo / '.githooks').mkdir(exist_ok=True)
        shutil.copy2(LINT_PATH, self.repo / 'scripts/lint_wms_rules.py')
        shutil.copy2(ROOT / '.githooks/pre-commit', self.repo / '.githooks/pre-commit')
        self.commit()
        object_id = self.git('hash-object', '-w', '--stdin', input=b'synthetic-conflict\n').decode().strip()
        path = 'app/routes/synthetic.py'
        records = (f'0 {"0" * len(object_id)}\t{path}\n'
                   + ''.join(f'100644 {object_id} {stage}\t{path}\n' for stage in (1, 2, 3)))
        self.git('update-index', '--index-info', input=records.encode())
        self.assertIn(b'U\tapp/routes/synthetic.py', self.git('diff', '--cached', '--name-status'))
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(LINT_PATH),
                                 '--staged', '--rule', 'a6', '--repo-root', str(self.repo)],
                                cwd=self.repo, env=self.env, capture_output=True, timeout=20)
        self.assertNotEqual(result.returncode, 0, 'unmerged index must not pass staged lint')
        result = subprocess.run([bash, str(self.repo / '.githooks/pre-commit')], cwd=self.repo,
                                env=self.env, capture_output=True, timeout=30)
        self.assertNotEqual(result.returncode, 0, 'unmerged index must not bypass the actual hook')


if __name__ == '__main__':
    unittest.main()
