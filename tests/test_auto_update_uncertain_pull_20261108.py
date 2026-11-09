"""Synthetic Git-only reproduction: no application, database, backup or network."""
import importlib.util
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('network and databases are forbidden')


def load_update():
    spec = importlib.util.spec_from_file_location('synthetic_auto_update', ROOT / 'app/auto_update.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UncertainPullTest(unittest.TestCase):
    def setUp(self):
        for guarded in (patch.object(socket.socket, 'connect', deny),
                        patch.object(socket.socket, 'connect_ex', deny),
                        patch.object(socket, 'getaddrinfo', deny),
                        patch.object(sqlite3, 'connect', deny)):
            guarded.start()
            self.addCleanup(guarded.stop)
        self.tmp = tempfile.TemporaryDirectory(prefix='wms-synthetic-pull-')
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name).resolve()
        self.git_env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH') if key in os.environ}
        self.git_env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                            GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='file')
        self.git('init', '-b', 'main')
        (self.repo / 'synthetic.txt').write_text('baseline\n', encoding='utf-8')
        (self.repo / 'unrelated.txt').write_text('baseline unrelated\n', encoding='utf-8')
        self.git('add', 'synthetic.txt', 'unrelated.txt')
        self.git('commit', '-m', 'synthetic baseline')
        self.before_head = self.git('rev-parse', 'HEAD')[1]
        (self.repo / 'synthetic.txt').write_text('candidate local work\n', encoding='utf-8')
        self.update = load_update()
        self.calls = []
        self.messages = []

    def git(self, *args):
        if args[0] not in {'init', 'add', 'commit', 'branch', 'status', 'stash', 'rev-parse'}:
            raise AssertionError('unsupported synthetic Git command')
        assert self.repo == Path(self.tmp.name).resolve() and (self.repo / '.git').parent == self.repo
        command = ['git', '-c', 'core.hooksPath=' + str(self.repo / 'no-hooks'),
                   '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid', *args]
        process = subprocess.run(command, cwd=self.repo, env=self.git_env,
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', stdin=subprocess.DEVNULL, timeout=20)
        return process.returncode, process.stdout.strip(), process.stderr.strip()

    def exercise(self, *, clean=False, result_code=1, advance=False, parallel=False, unknown_head=False, late_dirty=False, late_status_error=False):
        if clean:
            self.assertEqual(self.git('add','synthetic.txt')[0],0)
            self.assertEqual(self.git('commit','-m','synthetic clean local state')[0],0)
        before_head=self.git('rev-parse','HEAD')[1]
        before_stash=self.git('stash','list','--format=%H%x09%gs')[1]
        before_files={p.name:p.read_bytes() for p in self.repo.glob('*.txt')}
        state = {'backed_up': False}
        def backup_action():
            state['backed_up'] = True
            if late_dirty:(self.repo/'unrelated.txt').write_text('parallel work\n',encoding='utf-8')
            return True
        def fake_git(*args):
            self.calls.append(args)
            if args[0]=='fetch':return 0,'',''
            if args[0]=='status' and state['backed_up'] and late_status_error:return 1,'','synthetic status error'
            if args[0]=='stash':raise AssertionError('automatic update must never stash or restore')
            if args[0]=='pull':
                if advance:self.assertEqual(self.git('commit','--allow-empty','-m','synthetic advanced HEAD')[0],0)
                if parallel:(self.repo/'unrelated.txt').write_text('parallel work\n',encoding='utf-8')
                return result_code,'synthetic update' if result_code==0 else '', 'synthetic failure'
            return self.git(*args)
        def resolve(ref):
            if ref=='HEAD' and unknown_head:return None
            rc,value,_=self.git('rev-parse','HEAD');return value if rc==0 else None
        with patch.object(self.update,'ROOT_DIR',self.repo),patch.object(self.update,'run_git',side_effect=fake_git), \
             patch.object(self.update,'resolve_sha',side_effect=resolve),patch.object(self.update,'find_git',return_value='synthetic'), \
             patch.object(self.update,'find_python',return_value=None),patch.object(self.update,'backup_database',side_effect=backup_action) as backup, \
             patch.object(self.update,'count_commits',side_effect=lambda ref:(True,int(ref.startswith('HEAD..')),'')), \
             patch.object(self.update,'log',side_effect=self.messages.append),patch.object(self.update,'log_pulled_commits'), \
             patch.object(self.update,'REMOTE','origin'),patch.object(self.update,'BRANCH','main'),patch.object(self.update,'GIT_PIN',''), \
             patch.dict(os.environ,{'WMS_AUTO_UPDATE_DIRTY':'stash'}):
            self.assertEqual(self.update.main(),0)
            self.assertEqual(backup.call_count,int(clean))
        self.assertFalse(any(call[0]=='stash' for call in self.calls))
        should_pull = clean and not late_dirty and not late_status_error
        self.assertEqual(sum(call[0]=='pull' for call in self.calls),int(should_pull))
        self.assertEqual(self.git('stash','list','--format=%H%x09%gs')[1],before_stash)
        expected=dict(before_files)
        if clean and ((should_pull and parallel) or late_dirty):expected['unrelated.txt']='parallel work\n'.encode('utf-8').replace(b'\n',os.linesep.encode())
        self.assertEqual({p.name:p.read_bytes() for p in self.repo.glob('*.txt')},expected)
        if should_pull and advance:self.assertNotEqual(self.git('rev-parse','HEAD')[1],before_head)
        else:self.assertEqual(self.git('rev-parse','HEAD')[1],before_head)
        if not clean:self.assertTrue(any('未提交改动' in message for message in self.messages));self.assertTrue(any('跳过' in message for message in self.messages))

    def test_clean_timeout_never_restores(self):self.exercise(clean=True,result_code=124)
    def test_clean_timeout_after_head_change_never_restores(self):self.exercise(clean=True,result_code=124,advance=True)
    def test_clean_failure_after_head_change_never_restores(self):self.exercise(clean=True,advance=True)
    def test_clean_unknown_head_failure_never_restores(self):self.exercise(clean=True,unknown_head=True)
    def test_clean_failed_pull_leaves_parallel_work_untouched(self):self.exercise(clean=True,parallel=True)
    def test_clean_ordinary_failed_pull_leaves_files_and_stashes_untouched(self):self.exercise(clean=True)
    def test_clean_success_can_advance_head_without_stash(self):self.exercise(clean=True,result_code=0,advance=True)
    def test_dirty_cannot_enter_final_check_restore_boundary(self):self.exercise(advance=True)
    def test_dirty_cannot_enter_initial_stash_boundary(self):self.exercise(result_code=0,parallel=True)
    def test_dirty_unknown_head_keeps_all_original_work(self):self.exercise(unknown_head=True)
    def test_edit_during_backup_skips_pull_and_preserves_new_work(self):self.exercise(clean=True,late_dirty=True)
    def test_status_failure_after_backup_skips_pull(self):self.exercise(clean=True,late_status_error=True)

if __name__ == '__main__':unittest.main(verbosity=2)
