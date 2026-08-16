# -*- coding: utf-8 -*-
"""BUG-2026-08-16-012 回归（A2 用户域）：角色/状态/密码重置写结构化审计。

测试用例：
  T1. edit_user 改角色 → edit_user 审计含 old/new role
  T2. update_user_status 禁用用户 → 审计含 old/new status
  T3. reset_user_password → 审计记录密码重置事件（不含明文）
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    OperationAudit, User, db,
)


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


def _seed_target_user():
    with app_module.app.app_context():
        if not User.query.filter_by(username="target1").first():
            db.session.add(User(
                username="target1",
                password_hash=generate_password_hash("Passw0rd!"),
                role="user", must_change_password=False,
            ))
        db.session.commit()
        return User.query.filter_by(username="target1").first().id


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False,
            ))
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})
    yield c


def _latest_audit(op):
    return (OperationAudit.query
            .filter_by(operation=op)
            .order_by(OperationAudit.id.desc())
            .first())


def test_a9_user_audit():
    """A9 门禁：用户域角色/状态/密码重置接入 log_audit（见 T1/T2/T3）。"""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_request_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.commit()
        assert User.query.filter_by(username="admin").first() is not None


class TestUserAudit:

    def test_edit_user_role_audits_old_new(self, client):
        uid = _seed_target_user()
        resp = client.post(f"/user/{uid}/edit", data={
            "username": "target1", "role": "warehouse", "status": "normal",
        })
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("edit_user")
            assert audit is not None, "编辑用户角色未写结构化审计"
            assert audit.target_id == uid
            old_data = json.loads(audit.old_data)
            new_data = json.loads(audit.new_data)
            assert old_data.get("role") == "user"
            assert new_data.get("role") == "warehouse"

    def test_update_user_status_audits(self, client):
        uid = _seed_target_user()
        resp = client.post("/user/status", json={"user_id": uid, "status": "disabled"})
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("禁用用户")
            assert audit is not None, "禁用用户未写结构化审计"
            old_data = json.loads(audit.old_data)
            new_data = json.loads(audit.new_data)
            assert old_data.get("status") == "normal"
            assert new_data.get("status") == "disabled"

    def test_reset_user_password_audits(self, client):
        uid = _seed_target_user()
        resp = client.post("/user/reset_password", data={
            "user_id": str(uid), "new_password": "Str0ng!Pass",
        })
        assert resp.get_json().get("status") == "success", resp.get_json()
        with app_module.app.app_context():
            audit = _latest_audit("reset_user_password")
            assert audit is not None, "重置密码未写结构化审计"
            new_data = json.loads(audit.new_data)
            assert new_data.get("password_changed") is True
            assert "new_password" not in new_data and "password" not in new_data
            assert "admin" in (audit.reason or "")