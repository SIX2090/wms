# -*- coding: utf-8 -*-
"""BUG-2026-09-19-004 回归测试：访问令牌 sha256 哈希存储 + 一次性返显 + 存量平滑迁移。

覆盖：
- /api/login 响应一次性返显明文，库内只存 "sha256:<hex>" 哈希
- 哈希存储后 Bearer 鉴权正常（get_bearer_user 走哈希路径）
- 存量明文 ApiToken 行：鉴权通过且原位升级为哈希（迁移后走哈希路径仍通过）
- 存量明文 PrintWorkstation.auth_token 行：代理心跳通过且原位升级
- 工作站新增/重置：响应明文一次性返显、库内哈希、旧令牌失效
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (ApiToken, PrintWorkstation, User, Warehouse, db,  # noqa: E402
                 get_bearer_user, hash_access_token, is_hashed_access_token)


# ---------- 哈希助手单元测试 ----------

def test_hash_access_token():
    digest = hash_access_token("plain-abc")
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64
    assert digest == hash_access_token("plain-abc")  # 确定性
    assert digest != hash_access_token("plain-abd")
    assert "plain-abc" not in digest  # 不可逆，明文不出现在存储值中


def test_is_hashed_access_token():
    assert is_hashed_access_token(hash_access_token("x"))
    assert is_hashed_access_token("sha256:" + "0" * 64)
    assert not is_hashed_access_token("plain-token")
    assert not is_hashed_access_token(None)
    assert not is_hashed_access_token("")


def _reset_db():
    db.drop_all()
    db.create_all()


def _login_web(client, username="admin", password="admin"):
    resp = client.post(
        "/login",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code in (200, 302)


@pytest.fixture()
def client():
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    app_module.app.config["TESTING"] = True
    with app_module.app.app_context():
        _reset_db()
        db.session.add(User(
            username="admin", password_hash=generate_password_hash("admin"),
            role="admin", status="normal", must_change_password=False,
        ))
        db.session.add(User(
            username="wh1", password_hash=generate_password_hash("pass1"),
            role="warehouse", status="normal", must_change_password=False,
        ))
        db.session.add(Warehouse(code="RWH0", name="默认仓", status="active", is_default=True))
        db.session.commit()
    return app_module.app.test_client()


def _bearer_user(token_value):
    with app_module.app.test_request_context(
            headers={"Authorization": f"Bearer {token_value}"}):
        return get_bearer_user()


# ---------- ApiToken（移动端 Bearer） ----------

def test_api_login_returns_plaintext_once_and_stores_hash(client):
    resp = client.post("/api/login", json={"username": "wh1", "password": "pass1"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "success"
    plaintext = body["data"]["token"]
    assert plaintext and not plaintext.startswith("sha256:")
    with app_module.app.app_context():
        rows = ApiToken.query.all()
        assert len(rows) == 1
        # 库内只存哈希，且与返显明文一一对应；明文不落库
        assert rows[0].token == hash_access_token(plaintext)
        assert rows[0].token.startswith("sha256:")
        assert rows[0].token != plaintext


def test_hashed_token_bearer_auth(client):
    resp = client.post("/api/login", json={"username": "wh1", "password": "pass1"})
    plaintext = resp.get_json()["data"]["token"]
    user = _bearer_user(plaintext)
    assert user is not None and user.username == "wh1"


def test_legacy_plaintext_api_token_authenticates_and_migrates(client):
    """存量明文行：首次鉴权走明文兜底并原位升级为哈希，此后走哈希路径。"""
    with app_module.app.app_context():
        user = User.query.filter_by(username="wh1").one()
        legacy = ApiToken(
            token="legacy-plain-token-001",
            user_id=user.id,
            expires_at=datetime.now() + timedelta(days=7),
            revoked=False,
        )
        db.session.add(legacy)
        db.session.commit()
        legacy_id = legacy.id
    user = _bearer_user("legacy-plain-token-001")
    assert user is not None and user.username == "wh1"
    with app_module.app.app_context():
        row = db.session.get(ApiToken, legacy_id)
        assert row.token == hash_access_token("legacy-plain-token-001")
    # 升级后再次鉴权（哈希路径）仍通过
    user = _bearer_user("legacy-plain-token-001")
    assert user is not None and user.username == "wh1"
    # 错误令牌仍然拒绝
    assert _bearer_user("legacy-plain-token-002") is None


# ---------- PrintWorkstation.auth_token（打印代理 Bearer） ----------

def _seed_workstation(code, token, enabled=True):
    wh = Warehouse.query.filter_by(code="RWH0").one()
    ws = PrintWorkstation(
        code=code, name=code, device_id=f"device-{code}",
        warehouse_id=wh.id, status="offline", enabled=enabled,
        auth_token=token,
    )
    db.session.add(ws)
    db.session.commit()
    return ws


def _heartbeat(client, token):
    return client.post(
        "/print_queue/api/v1/heartbeat",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_legacy_plaintext_workstation_token_authenticates_and_migrates(client):
    with app_module.app.app_context():
        ws = _seed_workstation("WS-LEG", "ws-legacy-plain-001")
        ws_id = ws.id
    resp = _heartbeat(client, "ws-legacy-plain-001")
    assert resp.status_code == 200
    with app_module.app.app_context():
        row = db.session.get(PrintWorkstation, ws_id)
        assert row.auth_token == hash_access_token("ws-legacy-plain-001")
    # 升级后再次心跳（哈希路径）仍通过；错误令牌拒绝
    assert _heartbeat(client, "ws-legacy-plain-001").status_code == 200
    assert _heartbeat(client, "ws-legacy-plain-002").status_code == 401


def test_hashed_workstation_token_authenticates(client):
    with app_module.app.app_context():
        _seed_workstation("WS-HASH", hash_access_token("ws-hashed-001"))
    assert _heartbeat(client, "ws-hashed-001").status_code == 200
    assert _heartbeat(client, "ws-hashed-002").status_code == 401


def test_workstation_add_and_reset_return_plaintext_once(client):
    _login_web(client)
    resp = client.post("/print_routing/workstations", json={
        "code": "WS-NEW", "name": "新工作站", "warehouse_id": None,
    })
    assert resp.status_code == 200
    token1 = resp.get_json()["token"]
    assert token1 and not token1.startswith("sha256:")
    with app_module.app.app_context():
        ws = PrintWorkstation.query.filter_by(code="WS-NEW").one()
        ws_id = ws.id
        assert ws.auth_token == hash_access_token(token1)
    # 新令牌可用（哈希路径）
    assert _heartbeat(client, token1).status_code == 200
    # 重置：返显新明文、库内新哈希、旧令牌立即失效
    resp = client.post(f"/print_routing/workstations/{ws_id}/reset_token", json={})
    assert resp.status_code == 200
    token2 = resp.get_json()["token"]
    assert token2 and token2 != token1
    with app_module.app.app_context():
        ws = db.session.get(PrintWorkstation, ws_id)
        assert ws.auth_token == hash_access_token(token2)
    assert _heartbeat(client, token1).status_code == 401
    assert _heartbeat(client, token2).status_code == 200
