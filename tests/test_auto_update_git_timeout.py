"""Bound startup Git operations without contacting remotes or changing a repo."""
import subprocess
import sys
from types import SimpleNamespace

import auto_update as update


def test_run_git_bounds_time_and_disables_input(monkeypatch):
    calls = []
    monkeypatch.setattr(update, 'find_git', lambda: 'git')
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout=' result\n', stderr='')
    monkeypatch.setattr(update.subprocess, 'run', run)
    assert update.run_git('fetch', 'origin', 'main') == (0, 'result', '')
    command, options = calls[0]
    assert command == ['git', 'fetch', 'origin', 'main']
    assert 0 < options['timeout'] <= 120
    assert options['stdin'] == subprocess.DEVNULL
    assert options['env']['GIT_TERMINAL_PROMPT'] == '0'
    assert options['env']['GCM_INTERACTIVE'] == '0'


def test_timeout_returns_124_and_main_skips_update(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(update, "ROOT_DIR", tmp_path)
    monkeypatch.setattr(update, 'find_git', lambda: 'git')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs.get('timeout', 0))
    monkeypatch.setattr(update.subprocess, 'run', timeout)
    code, out, error = update.run_git('fetch', 'origin')
    assert code == 124 and out == ''
    assert '超时' in error
    messages = []
    monkeypatch.setattr(update, 'log', messages.append)
    monkeypatch.setattr(update, 'run_git', lambda *args: (124, '', 'Git 超时'))
    assert update.main() == 0
    assert any('超时' in message for message in messages)


def test_find_git_timeout_is_bounded_for_every_probe(monkeypatch):
    calls = []
    monkeypatch.setattr(update, '_GIT_EXE', None)
    def timeout(command, **kwargs):
        calls.append(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs.get('timeout', 0))
    monkeypatch.setattr(update.subprocess, 'run', timeout)
    assert update.find_git() is None
    assert calls
    assert all(0 < call['timeout'] <= 15 and call['stdin'] == subprocess.DEVNULL for call in calls)


def test_real_stalled_subprocess_is_terminated(monkeypatch, tmp_path):
    empty_input = tmp_path / "owned-empty-input"
    with empty_input.open("xb"):
        pass
    real_run = subprocess.run
    monkeypatch.setattr(update, 'find_git', lambda: 'git')
    def stalled(command, **kwargs):
        # The production runner supplies the timeout; shorten it only for this test.
        assert kwargs['timeout'] > 0
        kwargs['timeout'] = 0.2
        assert kwargs['stdin'] == subprocess.DEVNULL
        # LPAC denies the global NUL device; an owned empty file gives identical EOF.
        with empty_input.open('rb') as stream:
            kwargs['stdin'] = stream
            return real_run([sys.executable, '-I', '-S', '-B', '-c', 'import time; time.sleep(60)'], **kwargs)
    monkeypatch.setattr(update.subprocess, 'run', stalled)
    assert update.run_git('fetch', 'origin')[0] == 124
