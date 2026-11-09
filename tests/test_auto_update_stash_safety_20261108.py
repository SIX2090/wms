"""Auto-update stash behavior in temporary synthetic Git repos; no database/network.

Run directly: python -I -B tests/test_auto_update_stash_safety_20261108.py
"""
import importlib.util
import os
from pathlib import Path
import socket
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch


def _forbidden(*_args, **_kwargs):
    raise AssertionError('database/network access is forbidden')


SPEC = importlib.util.spec_from_file_location(
    'auto_update_synthetic', Path(__file__).resolve().parents[1] / 'app' / 'auto_update.py')
update = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(update)


class SyntheticGit:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP') if key in os.environ}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT='0',
                        GIT_ALLOW_PROTOCOL='file')
        git_executable = shutil.which('git')
        assert git_executable, 'synthetic Git fixture needs Git'
        self.prefix = [git_executable, '-c', 'core.hooksPath=' + str(self.root / 'no-hooks'),
                       '-c', 'core.autocrlf=false', '-c', 'user.name=Synthetic',
                       '-c', 'user.email=synthetic@example.invalid']

    def call(self, *args):
        allowed = {'init', 'add', 'commit', 'status', 'stash', 'rev-parse', 'diff', 'branch'}
        if not args or args[0] not in allowed:
            raise AssertionError('unsupported synthetic Git command')
        assert self.root.exists() and self.root.resolve() == self.root
        result = subprocess.run(self.prefix + list(args), cwd=str(self.root), env=self.env,
                                capture_output=True, text=True, encoding='utf-8', errors='replace',
                                stdin=subprocess.DEVNULL, timeout=20)
        return result.returncode, result.stdout.strip(), result.stderr.strip()

    def checked(self, *args):
        rc, out, err = self.call(*args)
        if rc:
            raise AssertionError((args, rc, out, err))
        return out


class AutoUpdateStashSafety(unittest.TestCase):
    def setUp(self):
        for target in (patch.object(socket.socket, 'connect', _forbidden),
                       patch.object(socket.socket, 'connect_ex', _forbidden),
                       patch.object(socket, 'getaddrinfo', _forbidden),
                       patch.object(sqlite3, 'connect', _forbidden)):
            target.start()
            self.addCleanup(target.stop)
        self.temp = tempfile.TemporaryDirectory(prefix='wms-synthetic-git-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git = SyntheticGit(self.root)
        self.git.checked('init', '-b', 'main')
        (self.root / 'tracked.txt').write_text('base\n', encoding='utf-8')
        (self.root / 'other.txt').write_text('base\n', encoding='utf-8')
        self.git.checked('add', 'tracked.txt', 'other.txt')
        self.git.checked('commit', '-m', 'synthetic base')
        (self.root / 'other.txt').write_text('preexisting stash\n', encoding='utf-8')
        self.git.checked('stash', 'push', '-m', 'preexisting')
        self.old_stash = self.git.checked('rev-parse', 'refs/stash')
        (self.root / 'tracked.txt').write_text('staged\n', encoding='utf-8')
        self.git.checked('add', 'tracked.txt')
        (self.root / 'tracked.txt').write_text('staged\nunstaged\n', encoding='utf-8')
        (self.root / 'untracked.txt').write_text('keep\n', encoding='utf-8')
        self.before = self.git.checked('status', '--porcelain', '--untracked-files=normal')
        self.messages = []

    def test_stash_tracked_changes(self):
        # The compatibility helper remains separately testable; main never calls it.
        with patch.object(update, 'run_git', side_effect=self.git.call):
            ok, _message, stash_sha = update.stash_tracked_changes()
        self.assertTrue(ok)
        self.assertEqual(stash_sha, self.git.checked('rev-parse', 'refs/stash'))
        self.assertNotEqual(stash_sha, self.old_stash)
        self.assertIn(self.old_stash, self.git.checked('stash', 'list', '--format=%H'))

    def run_dirty(self, mode=None, parallel=False, backup_ok=True):
        calls = []
        def git(*args):
            calls.append(args)
            if args[0] == 'fetch': return 0, '', ''
            if args[0] in ('pull', 'stash'):
                raise AssertionError('dirty automatic update must never enter a mutating Git phase')
            result = self.git.call(*args)
            if parallel and args == ('status', '--porcelain', '--untracked-files=no'):
                (self.root/'other.txt').write_text('parallel edit\n',encoding='utf-8')
            return result
        env = {} if mode is None else {'WMS_AUTO_UPDATE_DIRTY': mode}
        with patch.object(update,'ROOT_DIR',self.root), patch.object(update,'run_git',side_effect=git), \
             patch.object(update,'find_git',return_value='synthetic'), \
             patch.object(update,'backup_database',return_value=backup_ok) as backup, \
             patch.object(update,'count_commits',side_effect=lambda ref:(True,int(ref.startswith('HEAD..')),'')), \
             patch.object(update,'resolve_sha',return_value='f'*40), patch.object(update,'find_python',return_value=None), \
             patch.object(update,'log',side_effect=self.messages.append), patch.object(update,'REMOTE','origin'), \
             patch.object(update,'BRANCH','main'),patch.object(update,'GIT_PIN',''),patch.dict(os.environ,env,clear=True):
            self.assertEqual(update.main(),0)
            self.assertFalse(backup.called)
        self.assertFalse(any(call[0] in ('pull','stash') for call in calls))
        self.assertEqual((self.root/'tracked.txt').read_text(encoding='utf-8'),'staged\nunstaged\n')
        self.assertEqual((self.root/'untracked.txt').read_text(encoding='utf-8'),'keep\n')
        self.assertEqual((self.root/'other.txt').read_text(encoding='utf-8'),'parallel edit\n' if parallel else 'base\n')
        diff=self.git.checked('diff','--cached','--','tracked.txt')
        self.assertIn('+staged',diff);self.assertNotIn('+unstaged',diff)
        self.assertEqual(self.git.checked('stash','list','--format=%H'),self.old_stash)
        self.assertTrue(any('未提交改动' in msg for msg in self.messages));self.assertTrue(any('跳过' in msg for msg in self.messages))

    def test_dirty_all_legacy_settings_preserve_staged_unstaged_untracked_and_stash(self):
        for mode in (None,'stash','skip','unknown'):
            with self.subTest(mode=mode):self.run_dirty(mode)
        self.assertEqual(self.git.checked('status','--porcelain','--untracked-files=normal'),self.before)

    def test_parallel_edit_after_status_stays_in_worktree(self):
        self.run_dirty('stash',parallel=True)

    def test_staged_new_file_is_not_swallowed_by_stash_or_pull(self):
        (self.root/'new-file.txt').write_text('local staged file\n',encoding='utf-8')
        self.git.checked('add','new-file.txt')
        self.run_dirty('stash')
        self.assertEqual((self.root/'new-file.txt').read_text(encoding='utf-8'),'local staged file\n')
        self.assertIn('A  new-file.txt',self.git.checked('status','--porcelain'))

    def test_failed_backup_cannot_move_dirty_worktree(self):
        self.run_dirty('stash',backup_ok=False)
        self.assertEqual(self.git.checked('status','--porcelain','--untracked-files=normal'),self.before)

    def legacy_failure(self,phase):
        def git(*args):
            if args[:2]==('stash','push') and phase in ('push_before','push_after'):
                if phase=='push_after':self.git.checked(*args)
                return 124,'','synthetic timeout'
            if args[:2]==('stash','list'):
                if phase=='list_error':return 1,'','synthetic list error'
                if phase=='malformed':return 0,'invalid entry',''
                if phase=='duplicate':
                    rc,out,err=self.git.call(*args);return rc,out+'\n'+out,err
            return self.git.call(*args)
        with patch.object(update,'run_git',side_effect=git):ok,message,ident=update.stash_tracked_changes()
        self.assertFalse(ok);self.assertIsNone(ident)
        self.assertIn(self.old_stash,self.git.checked('stash','list','--format=%H'))
        self.assertEqual((self.root/'untracked.txt').read_text(encoding='utf-8'),'keep\n')
        self.assertIn('本次',message)
        if phase=='push_before':
            self.assertEqual(self.git.checked('status','--porcelain','--untracked-files=normal'),self.before)
            self.assertEqual(self.git.checked('rev-parse','refs/stash'),self.old_stash)
        else:self.assertIn('WMS auto-update backup',self.git.checked('stash','list','--format=%gs'))

    def test_compatibility_helper_push_failure_before_creation(self):self.legacy_failure('push_before')
    def test_compatibility_helper_push_timeout_after_creation(self):self.legacy_failure('push_after')
    def test_compatibility_helper_list_failure(self):self.legacy_failure('list_error')
    def test_compatibility_helper_malformed_listing(self):self.legacy_failure('malformed')
    def test_compatibility_helper_ambiguous_listing(self):self.legacy_failure('duplicate')

if __name__ == '__main__':unittest.main(verbosity=2)
