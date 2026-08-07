# -*- coding: utf-8 -*-
"""AI 数据保留配置持久化回归测试（M8 / AI-R14-F01）。

修复前：POST /api/ai/data_retention_config 仅校验输入不落库，响应明示
"演示模式，重启后恢复默认值"；GET 与页面永远返回默认保留期。
修复后：配置写入 SystemSetting（ai_retention_<category>_days），GET、
管理页面、清理预览/执行端点均读取已保存值。

验收点：
1. 未保存时 GET 返回默认保留期。
2. POST 保存后 GET 返回已保存值（持久化生效）。
3. 非整数输入返回 400。
4. 非审计类别保留期为 0 返回 400。
5. 保存后 _ai_data_retention_config 帮助函数反映已保存值。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _setup_client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    client = app_module.app.test_client()
    _login(client)
    return client


def _policy_days(payload, category):
    for policy in payload["config"]["policies"]:
        if policy["category"] == category:
            return policy["retention_days"]
    raise AssertionError(f"策略缺少类别 {category}")


def test_get_returns_defaults_when_nothing_saved():
    client = _setup_client()
    resp = client.get("/api/ai/data_retention_config")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "success"
    assert _policy_days(payload, "conversations") == 90
    assert _policy_days(payload, "images") == 30
    assert _policy_days(payload, "tasks") == 180
    assert _policy_days(payload, "feedback") == 365
    assert _policy_days(payload, "audit") == 0


def test_post_persists_and_get_returns_saved_values():
    client = _setup_client()
    resp = client.post("/api/ai/data_retention_config", json={
        "conversations_days": 7,
        "images_days": 15,
        "tasks_days": 60,
        "feedback_days": 120,
        "audit_days": 0,
    })
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["status"] == "success"
    assert "演示模式" not in payload["msg"]

    # 重新 GET 应读到已保存值
    resp = client.get("/api/ai/data_retention_config")
    payload = resp.get_json()
    assert _policy_days(payload, "conversations") == 7
    assert _policy_days(payload, "images") == 15
    assert _policy_days(payload, "tasks") == 60
    assert _policy_days(payload, "feedback") == 120
    assert _policy_days(payload, "audit") == 0


def test_post_rejects_non_integer():
    client = _setup_client()
    resp = client.post("/api/ai/data_retention_config", json={
        "conversations_days": "abc",
    })
    assert resp.status_code == 400
    assert resp.get_json()["status"] == "error"


def test_post_rejects_zero_for_non_audit_category():
    client = _setup_client()
    resp = client.post("/api/ai/data_retention_config", json={
        "conversations_days": 0,
    })
    assert resp.status_code == 400
    assert "保留期限" in resp.get_json()["msg"]


def test_helper_reflects_saved_values():
    client = _setup_client()
    client.post("/api/ai/data_retention_config", json={
        "conversations_days": 3,
        "images_days": 9,
        "tasks_days": 27,
        "feedback_days": 81,
        "audit_days": 3650,
    })
    with app_module.app.app_context():
        config = app_module._ai_data_retention_config(dry_run=True)
        assert config.get_policy("conversations").retention_days == 3
        assert config.get_policy("images").retention_days == 9
        assert config.get_policy("tasks").retention_days == 27
        assert config.get_policy("feedback").retention_days == 81
        assert config.get_policy("audit").retention_days == 3650
        assert config.get_policy("audit").critical_exempt is True
