"""Repair task: AUDIT-FULL-20261016-001-F07A; explicit service security modes."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

APP_DIR = Path(__file__).resolve().parent


def build_service_env(base_env):
    """Preserve operator settings; never silently accept plaintext service cookies."""
    env = dict(base_env)
    mode = env.get('WMS_DEPLOYMENT_MODE', '').strip().lower()
    secure = env.get('SESSION_COOKIE_SECURE', '').strip().lower() in {'1', 'true', 'yes'}
    insecure = env.get('WMS_ALLOW_INSECURE_COOKIE', '').strip().lower() in {'1', 'true', 'yes'}
    if not mode:
        mode = 'https' if secure else ('trusted-http' if insecure else '')
    if mode == 'https':
        if 'SESSION_COOKIE_SECURE' in env and not secure:
            raise ValueError('HTTPS模式与显式 SESSION_COOKIE_SECURE 配置冲突，请先核对配置。')
        env.setdefault('SESSION_COOKIE_SECURE', 'true')
    elif mode == 'trusted-http':
        if secure:
            raise ValueError('可信HTTP模式与 Secure Cookie 配置冲突，请选择HTTPS模式。')
        if 'WMS_ALLOW_INSECURE_COOKIE' in env and not insecure:
            raise ValueError('已显式禁止HTTP Cookie，启动器不会覆盖此选择。')
        env.setdefault('WMS_ALLOW_INSECURE_COOKIE', '1')
    else:
        raise ValueError('请明确 WMS_DEPLOYMENT_MODE=https 或 trusted-http；不会默认放行HTTP Cookie。')
    port = int(env.get('WMS_PORT') or 8080)
    if not 1 <= port <= 65535:
        raise ValueError('WMS_PORT必须在1至65535之间。')
    env.update(FLASK_ENV='production', PYTHONUTF8='1', PYTHONIOENCODING='utf-8',
               WMS_DEPLOYMENT_MODE=mode, WMS_PORT=str(port), WMS_NO_DB_TOUCH='1',
               WMS_SKIP_AUTO_UPDATE='1')
    env['WMS_HOST'] = env.get('WMS_HOST') or '127.0.0.1'
    env['PYTHONPATH'] = str(APP_DIR) + os.pathsep + env.get('PYTHONPATH', '')
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description='显式配置HTTPS或可信HTTP的WMS服务启动器')
    parser.add_argument('--check', action='store_true', help='只检查配置，不启动应用或访问数据库')
    parser.add_argument('--check-idle', action='store_true', help='检查配置及端口空闲，不启动应用')
    parser.add_argument('--check-database', action='store_true', help='只读验证已初始化的SQLite业务库')
    parser.add_argument('--health', action='store_true', help='核对本目录监听进程身份及登录页')
    parser.add_argument('--batch-config', action='store_true', help='预检成功后输出固定的模式/Cookie标志/端口，供BAT直接启动服务')
    args = parser.parse_args(argv)
    try:
        env = build_service_env(os.environ)
        check = subprocess.run([sys.executable, '-c', 'import config; config.validate_production_security_config()'],
                               cwd=APP_DIR, env=env, capture_output=True, text=True, encoding='utf-8', timeout=20)
        if check.returncode:
            raise ValueError('生产配置检查未通过：' + (check.stderr.strip().splitlines() or ['请核对配置'])[-1])
        if args.check_idle:
            from service_control import process_snapshot
            if process_snapshot(int(env['WMS_PORT']))['listeners']:
                raise ValueError('指定端口已有进程，拒绝覆盖部署；请先安排人工维护。')
        if args.check_database or not (args.check or args.check_idle or args.health):
            from runtime_guard import server_database_path
            database = server_database_path(env)
            validator = APP_DIR.parent / 'scripts' / 'restore_backup.py'
            if database is None or not database.is_file() or not validator.is_file():
                raise ValueError('服务需要已初始化的SQLite业务库和完整源码校验工具；请先完成首次安装/初始化，不会自动重置或创建账号。')
            valid = subprocess.run([sys.executable, str(validator), str(database), '--validate-only'],
                                   cwd=APP_DIR, env=env, capture_output=True, timeout=30)
            if valid.returncode:
                raise ValueError('业务库只读校验失败，保留原库，拒绝启动。')
        if args.health:
            return check_service_health(env)
        if args.batch_config:
            # Only enumerated values and the validated integer port may cross the CMD boundary.
            flags = [(yes if env[key].strip().lower() in {'1', 'true', 'yes'} else no)
                     if key in env else 'unset' for key, yes, no in (
                         ('SESSION_COOKIE_SECURE', 'true', 'false'), ('WMS_ALLOW_INSECURE_COOKIE', '1', '0'))]
            sys.stdout.write('|'.join([env['WMS_DEPLOYMENT_MODE'], *flags, env['WMS_PORT']]) + '\n')
            return 0
        if args.check or args.check_idle or args.check_database:
            sys.stdout.write('服务配置检查通过，未启动应用或初始化数据库。\n')
            return 0
        sys.stdout.write('启动WMS服务；启动时拉取更新已关闭，更新须使用维护流程。\n')
        sys.stdout.flush()
        return subprocess.call([sys.executable, str(APP_DIR / 'run_server.py')], cwd=APP_DIR, env=env)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        sys.stderr.write('服务启动拒绝：' + str(error) + '\n')
        return 2


def check_service_health(env):
    """Require the listener to be this installation's real run_server process."""
    from service_control import process_snapshot, is_target_process
    port = int(env['WMS_PORT'])
    for _ in range(10):
        snapshot = process_snapshot(port)
        owners = set(snapshot['listeners'])
        matches = [row for row in snapshot['processes'] if row['pid'] in owners and is_target_process(row, APP_DIR)]
        if len(matches) == 1 and owners == {matches[0]['pid']}:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/login', timeout=3) as response:
                    second = process_snapshot(port)
                    if response.status == 200 and set(second['listeners']) == owners and matches[0] in second['processes']:
                        sys.stdout.write('WMS进程身份与登录页检查通过。\n')
                        return 0
            except OSError:
                pass
        time.sleep(1)
    raise ValueError('未确认本目录WMS健康运行；不会把其他进程的HTTP响应当作部署成功。')


if __name__ == '__main__':
    raise SystemExit(main())
