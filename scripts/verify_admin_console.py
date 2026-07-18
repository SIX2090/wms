"""Regression checks for the login admin mode and administrator console."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'app' / 'app.py').read_text(encoding='utf-8')
LOGIN = (ROOT / 'app' / 'templates' / 'login.html').read_text(encoding='utf-8')
CONSOLE = (ROOT / 'app' / 'templates' / 'admin_console.html').read_text(encoding='utf-8')


def main() -> int:
    checks = {
        'login mode field': 'name="login_mode"' in LOGIN and 'data-login-mode="admin"' in LOGIN,
        'server enforces admin role': "login_mode == 'admin' and user.role != 'admin'" in APP,
        'admin redirects to console': "url_for('admin_console')" in APP,
        'console route is admin-only': "def admin_console" in APP and "@role_required('admin')" in APP,
        'console management entries': all(path in CONSOLE for path in ('/user', '/system_settings', '/operation_audit', '/backup', '/ai/acceptance')),
        'no password action': 'reset_password' not in CONSOLE and 'change_password' not in CONSOLE,
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        print('FAIL ADMIN-CONSOLE: ' + ', '.join(failed))
        return 1
    print(f'PASS ADMIN-CONSOLE: {len(checks)} checks')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
