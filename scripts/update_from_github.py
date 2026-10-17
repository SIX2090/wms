"""可靠的一键代码更新；不迁移/恢复数据库，不修改共享Python依赖。"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request

# Repair task: AUDIT-FULL-20261016-001-F04
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import service_control


class UpdateError(RuntimeError):
    pass


def run_command(args, root, env):
    return subprocess.run(args, cwd=root, env=env, capture_output=True, timeout=180)


@contextmanager
def update_lock(root):
    """OS锁自动释放，锁文件残留不代表占用；只支持普通main仓库。"""
    git_dir = root / '.git'
    if not git_dir.is_dir():
        raise UpdateError('仅支持普通Git仓库；不会在未知目录执行更新')
    handle = open(git_dir / 'wms-update.lock', 'a+b')
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise UpdateError('另一个更新器正在运行，请勿重复更新') from exc
        yield
    finally:
        handle.close()


class Services:
    def __init__(self, app_dir, port, login_path="/login"):
        self.app_dir, self.port = app_dir, port
        self.login_path = login_path if login_path.startswith("/") else "/" + login_path

    def current_pid(self):
        snapshot = service_control.process_snapshot(self.port)
        owners = set(snapshot['listeners'])
        if not owners:
            return None
        matches = [p for p in snapshot['processes'] if p['pid'] in owners
                   and service_control.is_target_process(p, self.app_dir)]
        if len(matches) != 1 or owners != {matches[0]['pid']}:
            raise UpdateError('监听进程身份不明确；请人工确认旧实例，不会自动停止其他程序')
        if os.path.normcase(os.path.realpath(matches[0]['executable'])) != os.path.normcase(os.path.realpath(sys.executable)):
            raise UpdateError('更新器与运行服务使用不同Python环境，服务未停止；请使用原运行环境更新')
        return matches[0]['pid']

    def stop(self):
        service_control.stop_verified_server(self.app_dir, self.port)

    def healthy(self, previous_pid=None):
        pid = self.current_pid()
        if pid is None or pid == previous_pid:
            return None
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.port}{self.login_path}', timeout=5) as response:
                if response.status == 200 and self.current_pid() == pid:
                    return pid
        except OSError:
            pass
        return None


class Updater:
    def __init__(self, root, *, runner=run_command, services=None, env=None):
        self.root = Path(root).resolve()
        self.app_dir = self.root / 'app'
        self.env = dict(os.environ)
        if env is not None:
            self.env.update(env)
        self.port = int(self.env.get('WMS_PORT') or 8080)
        if not 1 <= self.port <= 65535:
            raise UpdateError('端口必须在1至65535之间')
        self.env.update(PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
                        GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never',
                        WMS_NO_DB_TOUCH='1', WMS_SKIP_AUTO_UPDATE='1', WMS_PORT=str(self.port),
                        PIP_DISABLE_PIP_VERSION_CHECK='1')
        self.runner = runner
        self.services = services if services is not None else Services(self.app_dir, self.port, self.env.get('WMS_LOGIN_PATH') or '/login')
        self.report = {'status': 'failed', 'stop_attempted': False, 'stop_confirmed': False}

    def command(self, args, message):
        result = self.runner(args, self.root, self.env)
        if result.returncode:
            # 不转印Git远程URL/认证错误原文，避免凭证出现在操作员日志。
            raise UpdateError(message)
        return result.stdout

    def git(self, *args):
        return self.command(['git', *args], 'Git步骤失败：' + args[0])

    def head(self):
        return self.git('rev-parse', 'HEAD').decode('ascii').strip()

    def dependencies_unchanged(self, target):
        old = (self.app_dir / 'requirements.txt').read_bytes()
        if self.git('show', target + ':app/requirements.txt').replace(b'\r\n', b'\n') != old.replace(b'\r\n', b'\n'):
            raise UpdateError('新版本依赖发生变化，服务未停止；请在维护窗口独立升级运行环境')
        self.command([sys.executable, '-m', 'pip', 'check'], '当前运行环境依赖不一致，服务未停止')
        with tempfile.TemporaryDirectory(prefix='wms-dependency-check-') as folder:
            report = Path(folder) / 'plan.json'
            self.command([sys.executable, '-m', 'pip', 'install', '--dry-run', '--no-index',
                          '--no-deps', '--report', str(report), '-r', str(self.app_dir / 'requirements.txt')],
                         '无法确认现有依赖满足要求，服务未停止；需要支持dry-run/report的pip')
            if json.loads(report.read_text(encoding='utf-8')).get('install') != []:
                raise UpdateError('更新需要安装依赖，服务未停止；请独立维护运行环境')

    def backup(self):
        spec = importlib.util.spec_from_file_location('wms_update_online_backup', self.root / 'scripts/online_backup.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        backup_dir = self.root / 'backups'
        backup_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        self.report['backups'] = []
        for label, path in [('app', self.app_dir / 'instance/inventory.db'),
                            ('root', self.root / 'instance/inventory.db')]:
            if path.exists():
                target = backup_dir / f'before_github_update_{stamp}_{label}_inventory.db'
                if module.main([str(path), str(target)]):
                    raise UpdateError('一致性备份失败，服务未停止')
                self.report['backups'].append(str(target))

    def start(self, previous_pid):
        self.command([sys.executable, str(self.app_dir / 'restart.py')], '启动脚本失败')
        pid = self.services.healthy(previous_pid)
        if not pid:
            raise UpdateError('新进程身份或健康检查未通过')
        return pid

    def execute(self):
        old = target = None
        previous_pid = None
        stopped = False
        with update_lock(self.root):
            try:
                if self.git('branch', '--show-current').strip() != b'main':
                    raise UpdateError('只允许更新main分支')
                if self.git('status', '--porcelain', '-z'):
                    raise UpdateError('本地有未提交文件，已拒绝覆盖；请先保留并处理这些改动')
                old = self.head()
                self.report['old_sha'] = old
                # 所有网络/可行性检查在停服前；merge使用固定SHA，不再次联网pull。
                self.git('fetch', 'origin', 'main')
                target = self.git('rev-parse', 'FETCH_HEAD').decode('ascii').strip()
                self.report['target_sha'] = target
                self.git('merge-base', '--is-ancestor', old, target)
                if old == target:
                    self.report.update(status='unchanged', message='已是最新版本，未重启服务')
                    return 0
                self.dependencies_unchanged(target)
                previous_pid = self.services.current_pid()
                self.report['old_pid'] = previous_pid
                self.backup()
                flag = self.app_dir / 'WMS_NO_DB_TOUCH.flag'
                if not flag.exists():
                    flag.write_text('Update safety: no automatic database migration.\n', encoding='utf-8')
                if self.head() != old or self.git('status', '--porcelain', '-z'):
                    raise UpdateError('预检期间本地代码发生变化，服务未停止')
                stopped = True  # stop可能部分成功后报错，仍需检查恢复原服务。
                self.report['stop_attempted'] = True
                self.services.stop()
                self.report['stop_confirmed'] = True
                if self.head() != old or self.git('branch', '--show-current').strip() != b'main':
                    raise UpdateError('停止期间代码版本发生变化，拒绝覆盖')
                self.git('merge', '--ff-only', '--no-edit', target)
                if self.head() != target:
                    raise UpdateError('更新后代码版本与下载版本不一致')
                pid = self.start(previous_pid)
                if self.head() != target:
                    raise UpdateError('启动期间代码版本发生变化，不能确认更新成功')
                self.report.update(status='success', new_pid=pid, message='代码更新及新进程健康检查通过')
                return 0
            except (UpdateError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                self.report['message'] = str(exc)
                if stopped:
                    self.recover(old, target, previous_pid)
                return 1

    def recover(self, old, target, previous_pid):
        """只回退Git代码；从未改共享依赖，不自动恢复/替换业务数据库。"""
        try:
            current = self.head()
            if self.git('branch', '--show-current').strip() != b'main' or current not in {old, target}:
                raise UpdateError('代码被其他操作改变，拒绝自动回退')
            running = self.services.current_pid()
            if (current == old and running == previous_pid and running is not None
                    and self.services.healthy() == running):
                self.report['recovery'] = '原代码与原进程仍在运行，未重复重启'
                return
            if running is not None:
                self.services.stop()
            if current != old:
                self.git('reset', '--keep', old)
            if self.head() != old:
                raise UpdateError('旧版本回退未确认')
            self.report['rollback_sha'] = old
            if previous_pid is not None:
                self.report['recovered_pid'] = self.start(previous_pid)
                self.report['recovery'] = '已恢复旧代码及健康服务；本次更新仍为失败'
            else:
                self.report['recovery'] = '已恢复旧代码；原服务未运行，未自行启动旧服务'
        except (UpdateError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.report['recovery'] = '自动恢复未完成，需要人工处理：' + str(exc)


def main(argv=None):
    parser = argparse.ArgumentParser(description='先预检再停机的WMS一键代码更新')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args(argv)
    updater = None
    try:
        updater = Updater(args.root)
        result = updater.execute()
    except (UpdateError, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        sys.stderr.write('更新失败：' + str(exc) + '\n')
        return 1
    sys.stdout.write(json.dumps(updater.report, ensure_ascii=False, indent=2) + '\n')
    if result:
        sys.stderr.write('更新未完成；请查看上方失败及恢复结果。不会显示更新成功。\n')
    return result


if __name__ == '__main__':
    sys.exit(main())
