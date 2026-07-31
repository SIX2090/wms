"""AI-LOGIN-F01 regression checks for the usable and safe web login page."""
# AI_TASK: AI-LOGIN-F01
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"


def csrf_token(client) -> str:
    response = client.get("/login")
    assert response.status_code == 200, f"login GET status={response.status_code}, location={response.headers.get('Location')}"
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "login form must render a CSRF token"
    return match.group(1)


def login(client, username: str, password: str, **extra):
    data = {
        "csrf_token": csrf_token(client),
        "username": username,
        "password": password,
        "login_mode": "user",
        "usage_consent": "1",
    }
    data.update(extra)
    return client.post("/login", data=data, follow_redirects=False)


def main() -> int:
    os.environ["FLASK_ENV"] = "testing"
    os.environ["WMS_SKIP_STARTUP_DB_UPGRADE"] = "1"
    os.chdir(APP_DIR)
    sys.path.insert(0, str(APP_DIR))

    from werkzeug.security import generate_password_hash
    import app as wms

    template = (APP_DIR / "templates" / "login.html").read_text(encoding="utf-8")
    source = (APP_DIR / "app.py").read_text(encoding="utf-8")
    checks: list[tuple[str, bool, str]] = []

    checks.append((
        "template accessibility and consent wiring",
        all(marker in template for marker in (
            'name="usage_consent"', 'aria-label="用户名"', 'aria-label="密码"',
            'role="tablist"', 'role="tab"', 'aria-live="polite"',
        )),
        "consent, labels, tabs and live hint are present",
    ))
    checks.append((
        "captcha is explicitly disabled without a fake route",
        '验证码登录（暂未启用）' in template
        and 'disabled aria-describedby="captchaLoginHint"' in template
        and "验证码服务" in template
        and "captcha_login" not in source,
        "no fake captcha endpoint or clickable empty link",
    ))
    checks.append((
        "forgot-password is safe help only",
        '请联系系统管理员重置密码' in template
        and '账号是否存在' in template
        and 'url_for("reset_user_password")' not in template
        and "@app.route('/forgot" not in source,
        "no public reset endpoint or account enumeration",
    ))
    checks.append((
        "browser and mobile help are real status text",
        'Chrome 或 Microsoft Edge' in template and '支持移动端访问' in template,
        "browser guidance and mobile status are visible",
    ))
    checks.append((
        "server records unchecked consent without blocking login",
        "usage_consent = request.form.get('usage_consent') == '1'" in source
        and "登录时未勾选 usage_consent（不阻断）" in source,
        "consent is audited without blocking a valid login",
    ))

    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=True)
    with wms.app.app_context():
        wms.db.drop_all()
        wms.db.create_all()
        users = (
            ("login_user", "warehouse", False),
            ("login_admin", "admin", False),
            ("login_first", "admin", True),
        )
        for username, role, must_change_password in users:
            wms.db.session.add(wms.User(
                username=username,
                password_hash=generate_password_hash("Password123!"),
                role=role,
                status="normal",
                must_change_password=must_change_password,
            ))
        wms.db.session.commit()

        # TestingConfig disables CSRF at extension initialization. CSRF is
        # separately verified by verify_wms_bugs.py under its dedicated setup.
        wms.app.config["WTF_CSRF_ENABLED"] = False

        no_consent_client = wms.app.test_client()
        no_consent = login(no_consent_client, "login_user", "Password123!", usage_consent="")
        checks.append((
            "unchecked consent does not block login",
            no_consent.status_code in (302, 303) and "/login" not in no_consent.headers.get("Location", ""),
            f"status={no_consent.status_code}",
        ))
        no_consent_client.get("/logout", follow_redirects=False)

        admin_mode_client = wms.app.test_client()
        denied = login(admin_mode_client, "login_user", "Password123!", login_mode="admin")
        checks.append((
            "non-admin is rejected in administrator mode",
            denied.status_code == 403 and "管理员模式仅允许管理员账号登录" in denied.get_data(as_text=True),
            f"status={denied.status_code}, body={denied.get_data(as_text=True)[:120]!r}",
        ))

        first_login_client = wms.app.test_client()
        first_login = login(first_login_client, "login_first", "Password123!", login_mode="admin")
        checks.append((
            "initial password still forces password change",
            first_login.status_code in (302, 303)
            and first_login.headers.get("Location", "").endswith("/user/change_password"),
            f"status={first_login.status_code}, location={first_login.headers.get('Location')}, body={first_login.get_data(as_text=True)[:120]!r}",
        ))

    failed = [name for name, passed, _ in checks if not passed]
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'} {name}: {detail}")
    if failed:
        print("FAIL AI-LOGIN-F01: " + ", ".join(failed))
        return 1
    print(f"PASS AI-LOGIN-F01: {len(checks)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
