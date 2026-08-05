# -*- coding: utf-8 -*-
"""
app.py 拆分回归测试：库存预警（inventory_alert）域路由迁移到 routes/inventory_alert.py。

register-on-app 模式（register_inventory_alert_routes(app)），endpoint 名与 URL 不变。

验收点：
P1. 核心 endpoint 已注册，且无 inventory_alert.xxx 前缀重复。
P2. URL 路径保持不变（/alert、/alert/batch_update_thresholds 均在）。
P3. 辅助函数 _parse_alert_threshold_value / _parse_alert_material_ids 行为与原实现一致。
P4. /alert 列表页在启用库存预警后返回 200。
P5. /alert/batch_update_thresholds 无 id 返回 400，合法 id 更新最低库存返回 success。
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
from app import Material, SystemSetting, db  # noqa: E402
from routes.inventory_alert import (  # noqa: E402
    _parse_alert_material_ids,
    _parse_alert_threshold_value,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

ENDPOINTS = ["alert_list", "batch_update_alert_thresholds"]


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _enable_inventory_alert():
    setting = SystemSetting.query.filter_by(key="inventory_alert_enabled").first()
    if not setting:
        setting = SystemSetting(key="inventory_alert_enabled", value="1")
        db.session.add(setting)
    else:
        setting.value = "1"
    db.session.commit()


def _seed_material():
    m = Material(code="MAT-ALERT-001", name="预警测试物料", spec="A",
                 stock=0, min_stock=10, reorder_point=0)
    db.session.add(m)
    db.session.commit()
    return m


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _setup():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        _enable_inventory_alert()
    client = _make_client()
    _login(client)
    return client


def test_endpoints_registered():
    rules = {r.endpoint for r in app_module.app.url_map.iter_rules()}
    for ep in ENDPOINTS:
        assert ep in rules, f"endpoint {ep} 未注册"
    # register-on-app 模式不应产生 inventory_alert.xxx 前缀的 endpoint
    assert not any(ep.startswith("inventory_alert.") for ep in rules)


def test_parse_alert_threshold_value_valid_and_invalid():
    # 正数 -> (True, 值, None)
    ok, val, err = _parse_alert_threshold_value({"min_stock": "5.25"}, "min_stock", "最低库存")
    assert ok is True
    assert val == 5.25
    assert err is None
    # 数字字符串
    ok, val, err = _parse_alert_threshold_value({"min_stock": 8}, "min_stock", "最低库存")
    assert ok is True and val == 8 and err is None
    # list 形式（form to_dict(flat=False)）
    ok, val, err = _parse_alert_threshold_value({"min_stock": ["3"]}, "min_stock", "最低库存")
    assert ok is True and val == 3 and err is None
    # 负数 -> 错误
    ok, val, err = _parse_alert_threshold_value({"min_stock": "-1"}, "min_stock", "最低库存")
    assert ok is False and val is None and err == "最低库存不能小于 0"
    # 非数字 -> 错误
    ok, val, err = _parse_alert_threshold_value({"min_stock": "abc"}, "min_stock", "最低库存")
    assert ok is False and val is None and err == "最低库存必须是数字"
    # 空值 -> (False, None, None)
    ok, val, err = _parse_alert_threshold_value({"min_stock": ""}, "min_stock", "最低库存")
    assert ok is False and val is None and err is None


def test_parse_alert_material_ids_dedup_and_filter():
    raw = ["1", "2", "2", "0", "-3", "abc", "3", "1"]
    ids = _parse_alert_material_ids(raw)
    assert ids == [1, 2, 3]
    assert _parse_alert_material_ids(None) == []
    assert _parse_alert_material_ids([]) == []
    assert _parse_alert_material_ids([1, 2]) == [1, 2]


def test_alert_list_page_returns_200():
    client = _setup()
    with app_module.app.app_context():
        _seed_material()
    resp = client.get("/alert")
    assert resp.status_code == 200, f"/alert -> {resp.status_code}"


def test_batch_update_thresholds_no_ids_400():
    client = _setup()
    resp = client.post("/alert/batch_update_thresholds", json={"min_stock": 5})
    assert resp.status_code == 400


def test_batch_update_thresholds_valid_updates_min_stock():
    client = _setup()
    with app_module.app.app_context():
        m = _seed_material()
        mid = m.id
    resp = client.post("/alert/batch_update_thresholds",
                       json={"ids": [mid], "min_stock": 5, "safety_stock": 8})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "success"
    assert data["updated"] == 1
    with app_module.app.app_context():
        m = db.session.get(Material, mid)
        assert m.min_stock == 5
        assert m.reorder_point == 8