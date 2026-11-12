# -*- coding: utf-8 -*-
"""F2.1 回归：admin 默认弱密码强制改密。

- 未设 WMS_BOOTSTRAP_PASSWORD 且 admin 密码仍为默认 'admin' → must_change_password 置位。
- 已显式设置 WMS_BOOTSTRAP_PASSWORD（可信密码）→ 不强制。
- 已自行改过密码 → 幂等，不再被重复置位。
- 置位后登录被强制导向改密页（/user/change_password）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import User, db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _seed_admin(password, must_change):
    db.drop_all()
    db.create_all()
    db.session.add(User(
        username="admin", password_hash=generate_password_hash(password),
        role="admin", status="normal", must_change_password=must_change,
    ))
    db.session.commit()


def test_default_password_forces_change(monkeypatch):
    """未设 WMS_BOOTSTRAP_PASSWORD + 密码仍为 'admin' → 强制改密。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("admin", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is True


def test_explicit_bootstrap_password_not_forced(monkeypatch):
    """显式设置 WMS_BOOTSTRAP_PASSWORD（可信）→ 不强制改密。"""
    monkeypatch.setenv("WMS_BOOTSTRAP_PASSWORD", "S3cret-Strong-1")
    with app_module.app.app_context():
        _seed_admin("S3cret-Strong-1", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is False


def test_already_changed_password_is_idempotent(monkeypatch):
    """已自行改过密码（不再是默认 'admin'）→ 不被重复置位。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("MyOwnPass-9", False)
        app_module.ensure_admin_user_exists()
        u = User.query.filter_by(username="admin").first()
        assert u.must_change_password is False


def test_login_redirects_to_change_password_when_forced(monkeypatch):
    """must_change_password=True 时登录被强制导向改密页。"""
    monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
    with app_module.app.app_context():
        _seed_admin("admin", True)
    client = app_module.app.test_client()
    resp = client.post("/login", data={"username": "admin", "password": "admin"},
                       content_type="application/x-www-form-urlencoded")
    assert resp.status_code == 302
    assert "/user/change_password" in resp.headers.get("Location", "")


# ============================================================================
# G10（2026-11-11 P0 闸门）：默认凭证与「停用 admin 被静默解锁」
#
# 体检缺口：admin 被显式停用后，启动期 ensure_admin_user_exists() 会**无条件**
# 把它改回 normal——"停用 admin"这条安全动作重启一次就失效，而它恰恰是账号
# 泄露时的第一处置手段。现改为显式开关 WMS_AUTO_UNLOCK_DISABLED_ADMIN，
# 默认不解锁。
#
# 同时锁定两条**不得改变**的既有铁律（改动很容易"顺手优化"掉）：
#   - 未设 WMS_BOOTSTRAP_PASSWORD 时仍用固定默认 'admin' 并强制改密，
#     **不得**随机生成密码、**不得**拒绝启动（AGENTS §一）；
#   - 被停用但状态为 'inactive' 的账号从来不在解锁范围内，语义保持不变。
# ============================================================================

import logging  # noqa: E402


def _seed_admin_status(status):
    db.drop_all()
    db.create_all()
    db.session.add(User(
        username="admin", password_hash=generate_password_hash("admin"),
        role="admin", status=status, must_change_password=False,
    ))
    db.session.commit()


def _admin_status():
    db.session.expire_all()
    return User.query.filter_by(username="admin").first().status


class TestG10AutoUnlockSwitch:
    """停用 admin 不得被启动期静默解锁。"""

    def test_T1_disabled_admin_not_unlocked_by_default(self, monkeypatch):
        monkeypatch.delenv("WMS_AUTO_UNLOCK_DISABLED_ADMIN", raising=False)
        monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
        with app_module.app.app_context():
            _seed_admin_status("disabled")
            app_module.ensure_admin_user_exists()
            assert _admin_status() == "disabled", "默认不得自动解锁被停用的 admin"

    def test_T2_disabled_admin_unlocked_with_opt_in(self, monkeypatch, caplog):
        monkeypatch.setenv("WMS_AUTO_UNLOCK_DISABLED_ADMIN", "1")
        monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
        with app_module.app.app_context():
            _seed_admin_status("disabled")
            with caplog.at_level(logging.WARNING):
                app_module.ensure_admin_user_exists()
            assert _admin_status() == "normal"
            assert any("auto-unlocked" in (r.getMessage() or "") for r in caplog.records), (
                "恢复动作必须留 warning 日志作为审计证据"
            )

    def test_T3_inactive_admin_never_touched(self, monkeypatch):
        """'inactive' 不在解锁范围（现状语义），任何开关下都不得改动。"""
        monkeypatch.setenv("WMS_AUTO_UNLOCK_DISABLED_ADMIN", "1")
        monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
        with app_module.app.app_context():
            _seed_admin_status("inactive")
            app_module.ensure_admin_user_exists()
            assert _admin_status() == "inactive"

    def test_T4_bootstrap_literal_preserved(self):
        """AGENTS §一 铁律：默认密码必须是字面量 'admin'，不得随机、不得拒绝启动。"""
        src = (APP_DIR / "app.py").read_text(encoding="utf-8")
        assert "os.environ.get('WMS_BOOTSTRAP_PASSWORD') or 'admin'" in src, (
            "scripts/verify_wms_bugs.py 的 BUG-NEW-005 静态断言依赖此字面量"
        )
        assert "secrets.token_urlsafe" not in src.split("def ensure_bootstrap_admin_user")[1][:2000]


class TestG10DeploymentSurface:
    """部署清单与启动自检必须把「初始口令未设置」显性化。"""

    def test_T5_checklist_mentions_both_switches(self):
        text = (ROOT / "PRODUCTION_DEPLOYMENT_CHECKLIST.md").read_text(encoding="utf-8")
        assert "WMS_BOOTSTRAP_PASSWORD" in text, "部署清单必须要求设置初始口令"
        assert "WMS_AUTO_UNLOCK_DISABLED_ADMIN" in text, "部署清单必须要求确认解锁开关"

    def test_T6_startup_banner_warns_when_unset(self, monkeypatch):
        from startup_check import build_config_check_line
        monkeypatch.delenv("WMS_BOOTSTRAP_PASSWORD", raising=False)
        line = build_config_check_line(app_module.app)
        assert "bootstrap_pw=UNSET" in line, f"未设置时应显式告警：{line}"
        # 自检永不阻断：只产出字符串，不抛异常（上面能返回即已证明）

    def test_T7_startup_banner_reports_set(self, monkeypatch):
        from startup_check import build_config_check_line
        monkeypatch.setenv("WMS_BOOTSTRAP_PASSWORD", "S3cret-Strong-1")
        line = build_config_check_line(app_module.app)
        assert "bootstrap_pw=set" in line, f"已设置时不应告警：{line}"
        assert "S3cret-Strong-1" not in line, "自检行绝不能输出密码本身"
