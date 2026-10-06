# -*- coding: utf-8 -*-
"""BUG-2026-10-06-001 回归：首页 dashboard 告警计数与告警列表口径一致。

场景（生产实测，手机端截图）：
  D1. 专仓物料不计入他仓计数：铜排只入铜排仓（阈值 5 挂物料全局）→
      GET /api/mobile/dashboard?warehouse_id=项目仓 的 alert_count 应为 0
      （修复前为 1：dashboard 从未套"本仓业务物料"范围过滤，与
      /api/mobile/alert/list 口径不一致，首页显示 20 点进去却是空列表）。
  D2. 列表同步为空：同场景下 /api/mobile/alert/list?warehouse_id=项目仓
      返回空——两处口径一致。
  D3. 真缺货计入：铜排入项目仓 3 件（< 阈值 5）→ dashboard alert_count==1
      且列表含 M001——修复不引入漏报。
  D4. 全部仓库模式逐仓过滤：warehouse_id 缺省时逐仓套范围过滤，从未进过
      任何仓的物料不误计。

口径：dashboard alert_count 与 /api/mobile/alert/list 共用
_mobile_alert_warehouse_scoped_ids（判据 a 库位行 / b 净流水>0 / c out
流水），与 PC /alert 同口径。
"""
from __future__ import annotations

import os
import re
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

import app as app_module  # noqa: E402
if not hasattr(app_module, "__path__"):
    app_module.__path__ = [str(APP_DIR)]
from app import (  # noqa: E402
    db, Material, MaterialCategory, Unit, Warehouse, User, add_stock,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset():
    db.drop_all()
    db.create_all()


def _seed():
    admin = User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False)
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHCU", name="铜排仓", is_default=True, status="active"),
        Warehouse(code="WHPJ", name="项目仓库", status="active"),
        admin,
    ])
    db.session.commit()
    app_module.set_system_setting("inventory_alert_enabled", "1")
    mat = Material(code="M001", name="铜排", spec="T2",
                   category_id=1, unit_id=1, stock=0, price=10, min_stock=5)
    db.session.add(mat)
    db.session.commit()
    return mat, admin


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _pj_wh():
    return Warehouse.query.filter_by(code="WHPJ").first()


def _dashboard_alert_count(client, warehouse_id=None):
    qs = f"?warehouse_id={warehouse_id}" if warehouse_id else ""
    body = client.get(f"/api/mobile/dashboard{qs}").get_data(as_text=True)
    import json
    return json.loads(body)["data"]["alert_count"]


def _alert_list_body(client, warehouse_id=None):
    qs = f"?warehouse_id={warehouse_id}" if warehouse_id else ""
    return client.get(f"/api/mobile/alert/list{qs}").get_data(as_text=True)


class TestDashboardAlertCountScope:

    def test_d1_foreign_warehouse_material_not_counted(self):
        """D1：铜排只入铜排仓 → 项目仓 dashboard 计数 0（修复前为 1）。"""
        with app_module.app.app_context():
            _reset()
            mat, _ = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                admin = User.query.filter_by(username="admin").first()
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="铜排仓")
                assert ok, err
                db.session.commit()
            pj_id = _pj_wh().id
        client = app_module.app.test_client()
        _login(client)
        assert _dashboard_alert_count(client, pj_id) == 0

    def test_d2_alert_list_empty_same_scope(self):
        """D2：同场景下列表也为空——计数与列表口径一致。"""
        with app_module.app.app_context():
            _reset()
            mat, _ = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                admin = User.query.filter_by(username="admin").first()
                login_user(admin)
                ok, err = add_stock(mat, 20, transaction_type="in", warehouse="铜排仓")
                assert ok, err
                db.session.commit()
            pj_id = _pj_wh().id
        client = app_module.app.test_client()
        _login(client)
        assert "M001" not in _alert_list_body(client, pj_id)

    def test_d3_real_shortage_counted(self):
        """D3：铜排入项目仓 3 件（< 阈值 5）→ 计数 1 且列表含 M001。"""
        with app_module.app.app_context():
            _reset()
            mat, _ = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                admin = User.query.filter_by(username="admin").first()
                login_user(admin)
                ok, err = add_stock(mat, 3, transaction_type="in", warehouse="项目仓库")
                assert ok, err
                db.session.commit()
            pj_id = _pj_wh().id
        client = app_module.app.test_client()
        _login(client)
        assert _dashboard_alert_count(client, pj_id) == 1
        assert "M001" in _alert_list_body(client, pj_id)

    def test_d4_all_warehouses_mode_scoped_per_warehouse(self):
        """D4：全部仓库模式逐仓过滤——铜排是铜排仓业务物料且 3<5，
        全部模式计 1；项目仓视角非本仓业务 → 0。"""
        with app_module.app.app_context():
            _reset()
            mat, _ = _seed()
            with app_module.app.test_request_context("/"):
                from flask_login import login_user
                admin = User.query.filter_by(username="admin").first()
                login_user(admin)
                ok, err = add_stock(mat, 3, transaction_type="in", warehouse="铜排仓")
                assert ok, err
                db.session.commit()
            pj_id = _pj_wh().id
        client = app_module.app.test_client()
        _login(client)
        # 全部仓库：铜排是铜排仓业务物料且 3<5 → 计 1
        assert _dashboard_alert_count(client) == 1
        # 项目仓视角：非本仓业务 → 0
        assert _dashboard_alert_count(client, pj_id) == 0
