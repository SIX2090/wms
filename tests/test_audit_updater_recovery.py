"""Repair task: AUDIT-FULL-20261016-001-F04；Git仅用临时main仓库，服务与pip均模拟。"""
from contextlib import closing
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import venv
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audit_updater', ROOT / 'scripts/update_from_github.py')
u = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(u)


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, capture_output=True, check=True, timeout=30)
    return result.stdout.decode('utf-8').strip()


def init(root, bare=False):
    root.mkdir()
    git(root, 'init', '--bare' if bare else '--quiet', '-b', 'main')
    git(root, 'config', 'user.name', 'WMS isolated test')
    git(root, 'config', 'user.email', 'test@localhost')
    git(root, 'config', 'commit.gpgsign', 'false')
    git(root, 'config', 'core.hooksPath', str(root.parent / 'empty-test-hooks'))


def commit(root, text):
    git(root, 'add', '.')
    git(root, 'commit', '-qm', text)
    return git(root, 'rev-parse', 'HEAD')


@pytest.fixture
def repo(tmp_path):
    origin, seed, work = [tmp_path / n for n in ['origin.git', 'seed', 'work']]
    init(origin, True)
    init(seed)
    (seed / 'app').mkdir()
    (seed / 'scripts').mkdir()
    (seed / 'app/requirements.txt').write_bytes(b'')
    (seed / 'app/restart.py').write_text('raise SystemExit(1)\n', encoding='utf-8')
    shutil.copyfile(ROOT / 'scripts/online_backup.py', seed / 'scripts/online_backup.py')
    (seed / '.gitignore').write_text('app/instance/\ninstance/\nbackups/\n*.flag\n*.marker\n__pycache__/\n', encoding='utf-8')
    (seed / 'README.txt').write_text('old\n', encoding='utf-8')
    old = commit(seed, 'old')
    git(seed, 'remote', 'add', 'origin', str(origin))
    git(seed, 'push', '-q', 'origin', 'main')
    git(tmp_path, 'clone', '-q', str(origin), str(work))
    git(work, 'config', 'user.name', 'WMS isolated test')
    git(work, 'config', 'user.email', 'test@localhost')
    git(work, 'config', 'commit.gpgsign', 'false')
    git(work, 'config', 'core.hooksPath', str(tmp_path / 'empty-test-hooks'))
    (seed / 'README.txt').write_text('new\n', encoding='utf-8')
    target = commit(seed, 'new')
    git(seed, 'push', '-q', 'origin', 'main')
    instance = work / 'app/instance'
    instance.mkdir()
    database = instance / 'inventory.db'
    with closing(sqlite3.connect(database)) as conn:
        conn.execute('CREATE TABLE business (value TEXT)')
        conn.execute("INSERT INTO business VALUES ('keep')")
        conn.commit()
    return SimpleNamespace(root=work, seed=seed, old=old, target=target, database=database)


class FakeServices:
    def __init__(self, events, pid=10):
        self.events, self.pid, self.next_pid = events, pid, 20
        self.stop_failure = None
        self.unhealthy = False

    def current_pid(self):
        return self.pid

    def stop(self):
        self.events.append('stop')
        if self.stop_failure == 'before':
            self.stop_failure = None
            raise u.UpdateError('stop refused')
        self.pid = None
        if self.stop_failure == 'after':
            self.stop_failure = None
            raise u.UpdateError('stop partial failure')

    def healthy(self, previous_pid=None):
        return self.pid if not self.unhealthy and self.pid != previous_pid else None


class Runner:
    def __init__(self, repo, services, events):
        self.repo, self.services, self.events = repo, services, events
        self.failure = None
        self.install_plan = []
        self.on_new_start = None

    def __call__(self, args, root, env):
        if args[0] == 'git':
            stage = args[1]
            self.events.append('git:' + stage)
            if self.failure == stage:
                return SimpleNamespace(returncode=1, stdout=b'', stderr=b'private-token-not-to-print')
            return subprocess.run(args, cwd=root, env=env, capture_output=True, timeout=30)
        if '-m' in args:
            assert args[args.index('-m') + 1] == 'pip'
            if 'check' in args:
                stage = 'dependency-check'
            else:
                assert '--dry-run' in args, '测试禁止真实安装依赖'
                stage = 'dependency-plan'
                Path(args[args.index('--report') + 1]).write_text(json.dumps({'install': self.install_plan}))
            self.events.append(stage)
            return SimpleNamespace(returncode=1 if self.failure == stage else 0, stdout=b'')
        assert Path(args[1]).name == 'restart.py'
        current = git(root, 'rev-parse', 'HEAD')
        stage = 'start-old' if current == self.repo.old else 'start-new'
        self.events.append(stage)
        if stage == 'start-new' and self.on_new_start:
            self.on_new_start()
        if self.failure in {stage, 'both-starts'}:
            return SimpleNamespace(returncode=1, stdout=b'')
        self.services.next_pid += 1
        self.services.pid = self.services.next_pid
        return SimpleNamespace(returncode=0, stdout=b'')


def make(repo, pid=10):
    events = []
    services = FakeServices(events, pid)
    runner = Runner(repo, services, events)
    updater = u.Updater(repo.root, runner=runner, services=services, env={'WMS_PORT': '18080'})
    return updater, services, runner, events


def assert_data_preserved(repo, before):
    assert repo.database.read_bytes() == before
    with closing(sqlite3.connect(repo.database)) as conn:
        assert conn.execute('SELECT value FROM business').fetchone() == ('keep',)


@pytest.mark.parametrize('failure', ['fetch', 'merge-base', 'dependency-check', 'dependency-plan'])
def test_preflight_failures_keep_old_service_and_code(repo, failure):
    updater, service, runner, events = make(repo)
    runner.failure = failure
    before = repo.database.read_bytes()
    assert updater.execute() == 1
    assert service.pid == 10 and 'stop' not in events
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert 'private-token' not in json.dumps(updater.report)
    assert_data_preserved(repo, before)


def test_dirty_local_code_is_never_discarded(repo):
    updater, service, runner, events = make(repo)
    (repo.root / 'README.txt').write_text('operator edit')
    assert updater.execute() == 1
    assert 'git:fetch' not in events and 'stop' not in events
    assert (repo.root / 'README.txt').read_text() == 'operator edit'


def test_dependency_changes_refuse_before_stop(repo):
    (repo.seed / 'app/requirements.txt').write_text('new-dependency>=1\n')
    commit(repo.seed, 'dependency change')
    git(repo.seed, 'push', '-q', 'origin', 'main')
    updater, service, runner, events = make(repo)
    assert updater.execute() == 1
    assert 'stop' not in events and 'dependency-plan' not in events
    assert service.pid == 10


def test_nonempty_dependency_plan_never_installs_or_stops(repo):
    updater, service, runner, events = make(repo)
    runner.install_plan = [{'metadata': {'name': 'missing'}}]
    assert updater.execute() == 1
    assert service.pid == 10 and 'stop' not in events


def test_backup_failure_keeps_running_service(repo, monkeypatch):
    updater, service, runner, events = make(repo)
    monkeypatch.setattr(updater, 'backup', lambda: (_ for _ in ()).throw(u.UpdateError('backup failed')))
    assert updater.execute() == 1
    assert service.pid == 10 and 'stop' not in events


def test_success_uses_fixed_downloaded_sha_and_new_healthy_pid(repo):
    updater, service, runner, events = make(repo)
    before = repo.database.read_bytes()
    assert updater.execute() == 0, updater.report
    assert events.index('git:fetch') < events.index('dependency-plan') < events.index('stop') < events.index('git:merge')
    assert 'git:pull' not in events and events.count('git:fetch') == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.target
    assert updater.report['status'] == 'success'
    assert updater.report['new_pid'] != 10
    backup = Path(updater.report['backups'][0])
    with closing(sqlite3.connect(backup)) as conn:
        assert conn.execute('SELECT value FROM business').fetchone() == ('keep',)
    assert_data_preserved(repo, before)


@pytest.mark.parametrize('failure', ['merge', 'start-new'])
def test_post_stop_failure_recovers_old_code_and_service(repo, failure):
    updater, service, runner, events = make(repo)
    runner.failure = failure
    before = repo.database.read_bytes()
    assert updater.execute() == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert service.pid is not None and service.pid != 10
    assert 'start-old' in events
    assert updater.report['status'] == 'failed'
    assert updater.report['rollback_sha'] == repo.old
    assert_data_preserved(repo, before)


@pytest.mark.parametrize('failure', ['before', 'after'])
def test_stop_failure_preserves_or_recovers_original_service(repo, failure):
    updater, service, runner, events = make(repo)
    service.stop_failure = failure
    assert updater.execute() == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert service.pid is not None
    assert ('start-old' in events) == (failure == 'after')


def test_new_http_failure_cannot_be_reported_success(repo):
    updater, service, runner, events = make(repo)
    def unhealthy():
        service.unhealthy = True
    runner.on_new_start = unhealthy
    assert updater.execute() == 1
    assert updater.report['status'] == 'failed'
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert 'start-old' in events
    assert '自动恢复未完成' in updater.report['recovery']


def test_recovery_failure_is_explicit_and_nonzero(repo):
    updater, service, runner, events = make(repo)
    runner.failure = 'both-starts'
    assert updater.execute() == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert '自动恢复未完成' in updater.report['recovery']


def test_originally_stopped_service_is_not_started_on_failed_update(repo):
    updater, service, runner, events = make(repo, pid=None)
    runner.failure = 'start-new'
    assert updater.execute() == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old
    assert service.pid is None and 'start-old' not in events


def test_user_edit_during_start_failure_blocks_destructive_rollback(repo):
    updater, service, runner, events = make(repo)
    runner.failure = 'start-new'
    runner.on_new_start = lambda: (repo.root / 'README.txt').write_text('new operator edit')
    assert updater.execute() == 1
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.target
    assert (repo.root / 'README.txt').read_text() == 'new operator edit'
    assert '自动恢复未完成' in updater.report['recovery']


def test_updater_lock_prevents_concurrent_update(repo):
    updater, service, runner, events = make(repo)
    with u.update_lock(repo.root):
        with pytest.raises(u.UpdateError, match='另一个更新器'):
            updater.execute()
    assert events == []
    with u.update_lock(repo.root):
        pass  # OS释放后残留锁文件不阻止下次运行。


def test_same_version_does_not_restart_or_install(repo):
    updater, service, runner, events = make(repo)
    original = runner.__call__
    def same(args, root, env):
        if args == ['git', 'rev-parse', 'FETCH_HEAD']:
            return SimpleNamespace(returncode=0, stdout=repo.old.encode('ascii'))
        return original(args, root, env)
    updater.runner = same
    assert updater.execute() == 0
    assert updater.report['status'] == 'unchanged'
    assert service.pid == 10 and 'stop' not in events and 'dependency-plan' not in events


def test_foreign_listener_blocks_before_stop(repo, monkeypatch):
    updater, service, runner, events = make(repo)
    monkeypatch.setattr(service, 'current_pid', lambda: (_ for _ in ()).throw(u.UpdateError('unknown process')))
    assert updater.execute() == 1
    assert 'stop' not in events and git(repo.root, 'rev-parse', 'HEAD') == repo.old


def test_new_unhealthy_old_healthy_recovers_old_service(repo, monkeypatch):
    updater, service, runner, events = make(repo)
    def healthy(previous_pid=None):
        if git(repo.root, 'rev-parse', 'HEAD') == repo.target:
            return None
        return service.pid if service.pid != previous_pid else None
    monkeypatch.setattr(service, 'healthy', healthy)
    assert updater.execute() == 1
    assert updater.report['recovered_pid'] == service.pid
    assert git(repo.root, 'rev-parse', 'HEAD') == repo.old


def test_local_commit_during_backup_is_preserved_before_stop(repo, monkeypatch):
    updater, service, runner, events = make(repo)
    original = updater.backup
    def concurrent():
        original()
        (repo.root / 'operator.txt').write_text('keep local commit')
        commit(repo.root, 'operator concurrent commit')
    monkeypatch.setattr(updater, 'backup', concurrent)
    assert updater.execute() == 1
    assert service.pid == 10 and 'stop' not in events
    assert git(repo.root, 'rev-parse', 'HEAD') != repo.old
    assert (repo.root / 'operator.txt').read_text() == 'keep local commit'


def test_dependency_line_endings_are_not_a_dependency_upgrade(repo):
    content = b'# fixture requirements\n'
    (repo.root / 'app/requirements.txt').write_bytes(content.replace(b'\n', b'\r\n'))
    updater, service, runner, events = make(repo)
    old_git = updater.git
    def requirement_bytes(*args):
        if args[0] == 'show':
            return content
        return old_git(*args)
    updater.git = requirement_bytes
    updater.dependencies_unchanged(repo.target)
    assert 'dependency-plan' in events and 'stop' not in events


def test_required_windows_environment_is_retained(repo):
    updater, service, runner, events = make(repo)
    for key, value in dict(os.environ).items():
        if key.upper() in {'PATH', 'SYSTEMROOT'}:
            assert updater.env[key] == value
    assert updater.env['WMS_PORT'] == '18080'


@pytest.mark.parametrize('owners,matched', [([], False), ([40], False), ([10, 40], True)])
def test_service_adapter_refuses_foreign_or_mixed_listeners(tmp_path, monkeypatch, owners, matched):
    service = u.Services(tmp_path, 18080)
    monkeypatch.setattr(u.service_control, 'process_snapshot', lambda port: {
        'listeners': owners, 'processes': [{'pid': 10}] if matched else []})
    monkeypatch.setattr(u.service_control, 'is_target_process', lambda *args: True)
    if not owners:
        assert service.current_pid() is None
    else:
        with pytest.raises(u.UpdateError):
            service.current_pid()


@pytest.mark.parametrize('path', ['/login', 'custom/login'])
def test_service_adapter_health_checks_same_pid_after_http(tmp_path, monkeypatch, path):
    service = u.Services(tmp_path, 18080, path)
    monkeypatch.setattr(service, 'current_pid', lambda: 20)
    response = MagicMock()
    response.__enter__.return_value.status = 200
    request = MagicMock(return_value=response)
    monkeypatch.setattr(u.urllib.request, 'urlopen', request)
    assert service.healthy(previous_pid=10) == 20
    request.assert_called_once_with('http://127.0.0.1:18080/' + path.lstrip('/'), timeout=5)
    request.reset_mock()
    assert service.healthy(previous_pid=20) is None
    request.assert_not_called()
    monkeypatch.setattr(service, 'current_pid', MagicMock(side_effect=[20, 30]))
    assert service.healthy(previous_pid=10) is None


def test_service_adapter_preserves_shared_strict_stop(tmp_path, monkeypatch):
    service = u.Services(tmp_path, 18080)
    stop = MagicMock()
    monkeypatch.setattr(u.service_control, 'stop_verified_server', stop)
    service.stop()
    stop.assert_called_once_with(tmp_path, 18080)


@pytest.mark.parametrize('same', [True, False])
def test_service_adapter_keeps_original_python_environment(tmp_path, monkeypatch, same):
    service = u.Services(tmp_path, 18080)
    monkeypatch.setattr(u.service_control, 'process_snapshot', lambda port: {
        'listeners': [10], 'processes': [{'pid': 10, 'executable': sys.executable if same else str(tmp_path / 'other/python.exe')}]})
    monkeypatch.setattr(u.service_control, 'is_target_process', lambda *args: True)
    if same:
        assert service.current_pid() == 10
    else:
        with pytest.raises(u.UpdateError, match='不同Python环境'):
            service.current_pid()


def test_wrapper_propagates_exact_controller_result():
    source = (ROOT / 'update_from_github.bat').read_text(encoding='utf-8')
    assert 'scripts\\update_from_github.py' in source
    assert 'set "UPDATE_RESULT=%ERRORLEVEL%"' in source
    assert source.rstrip().endswith('exit /b %UPDATE_RESULT%')
    assert '[OK] WMS update finished' not in source


@pytest.mark.skipif(os.name != 'nt', reason='Windows cmd batch end-to-end')
@pytest.mark.parametrize('failure', ['fetch', 'startup'])
def test_windows_batch_faults_preserve_service_or_report_start_failure(tmp_path, failure):
    # All files and Git origin are temporary. The old stop entry only writes a
    # marker; the new verifier sees an unused port and cannot stop any process.
    work, origin = tmp_path / 'work', tmp_path / 'origin.git'
    init(work)
    init(origin, True)
    (work / 'app').mkdir()
    (work / 'scripts').mkdir()
    for name in ['scripts/update_from_github.py', 'scripts/online_backup.py',
                 'app/service_control.py', 'update_from_github.bat']:
        shutil.copyfile(ROOT / name, work / name)
    (work / 'app/requirements.txt').write_bytes(b'')
    (work / 'app/restart.py').write_text(
        "from pathlib import Path\nPath(__file__).with_name('start.marker').write_text('attempted')\nraise SystemExit(1)\n",
        encoding='utf-8')
    (work / 'stop_wms_offline.bat').write_bytes(
        b'@echo off\r\necho stopped>"%~dp0stop.marker"\r\nexit /b 0\r\n')
    (work / '.gitignore').write_text('__pycache__/\nbackups/\n*.flag\n*.marker\n', encoding='utf-8')
    (work / 'README.txt').write_text('old\n', encoding='utf-8')
    old = commit(work, 'old fixture')
    git(work, 'remote', 'add', 'origin', str(origin))
    git(work, 'push', '-q', 'origin', 'main')
    (work / 'README.txt').write_text('new\n', encoding='utf-8')
    commit(work, 'target fixture')
    git(work, 'push', '-q', 'origin', 'main')
    git(work, 'reset', '--keep', old)
    if failure == 'fetch':
        git(work, 'remote', 'set-url', 'origin', str(tmp_path / 'nonexistent.git'))
    environment = tmp_path / 'venv'
    venv.EnvBuilder(with_pip=True).create(environment)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, LOCALAPPDATA=str(tmp_path / 'empty-app-data'),
               PATH=str(environment / 'Scripts') + os.pathsep + os.environ['PATH'],
               WMS_PORT=str(port), PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               PIP_DISABLE_PIP_VERSION_CHECK='1', PIP_NO_INDEX='1',
               GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    result = subprocess.run(['cmd.exe', '/d', '/c', str(work / 'update_from_github.bat'), '--noninteractive'],
                            cwd=work, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    assert result.returncode != 0, result.stdout.decode('utf-8', errors='replace')
    assert git(work, 'rev-parse', 'HEAD') == old
    assert not (work / 'stop.marker').exists(), '下载失败前不应停止服务；新控制器不调用旧停止脚本'
    if failure == 'startup':
        assert (work / 'app/start.marker').exists(), result.stdout.decode('utf-8', errors='replace')
        assert b'"status": "failed"' in result.stdout
    assert b'[OK] WMS update finished' not in result.stdout
