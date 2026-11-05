# -*- coding: utf-8 -*-
"""P1-6 第二批回归：out_order（出库/领料单）仓库参数统一为 warehouse_id。

承接 BUG-2026-09-25-007（in_order 首批）。out_order 有两处写入路径：
  - `/out_order/<id>/update`（草稿改表头，非销售单）
  - `/out_order/add`（新增；销售出库分支**原本已支持** warehouse_id，
    非销售分支——领料单/其他出库——只有名称，本次补上）

策略同首批：ID 优先、名称兜底、两者都无则回退默认仓，无默认 400。

测试用例：
  T1. add 非销售分支：传 warehouse_id 正确落库
  T2. add 非销售分支：传名称仍正确（防回归）
  T3. add 非销售分支：ID 优先于名称
  T4. add 非销售分支：无效 ID → 400
  T5. update 分支：传 warehouse_id 改仓库
  T6. 前端 out_order_add 渲染 warehouse_id 且 option value 为 ID
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

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    Material, OutOrder, Unit, User, Warehouse, db,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed(default=True):
    unit = Unit(code="PCS", name="个")
    wh_a = Warehouse(code="WHA", name="仓库甲", status="active", is_default=default)
    wh_b = Warehouse(code="WHB", name="仓库乙", status="active", is_default=False)
    user = User(username="p16_out", password_hash=generate_password_hash("admin"),
                role="warehouse", must_change_password=False)
    material = Material(code="P16OUT", name="出库物料", unit=unit, stock=0, price=10)
    db.session.add_all([unit, wh_a, wh_b, user, material])
    db.session.commit()
    return wh_a, wh_b, material


def _login(client):
    client.post("/login", data={"username": "p16_out", "password": "admin"},
                content_type="application/x-www-form-urlencoded")


def _add_payload(**extra):
    payload = {
        "order_no": "P16-OUT-1",
        "business_type": "领料单",
        "date": "2026-09-25",
        "items": [{"code": "P16OUT", "quantity": 1, "price": 10}],
    }
    payload.update(extra)
    return payload


def _make_draft(wh, material):
    order = OutOrder(order_no="P16-DRAFT", date=__import__("datetime").date.today(),
                     business_type="领料单", warehouse=wh.name, status="pending")
    db.session.add(order)
    db.session.commit()
    return order


class TestOutOrderWarehouseIdParam:

    def test_add_accepts_warehouse_id(self):
        """T1：add 非销售分支传 warehouse_id → 落库该仓名称。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/out_order/add", json=_add_payload(warehouse_id=wh_b.id))
            body = resp.get_json()
            assert body["status"] == "success", body
            order = OutOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_add_legacy_name_still_works(self):
        """T2：add 非销售分支传名称仍正确（防回归）。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/out_order/add", json=_add_payload(warehouse="仓库乙"))
            body = resp.get_json()
            assert body["status"] == "success", body
            order = OutOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_add_id_takes_precedence(self):
        """T3：ID 优先于名称。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/out_order/add", json=_add_payload(
                warehouse_id=wh_b.id, warehouse="仓库甲"))
            body = resp.get_json()
            assert body["status"] == "success", body
            order = OutOrder.query.get(body["id"])
            assert order.warehouse == "仓库乙", order.warehouse

    def test_add_invalid_id_rejected(self):
        """T4：无效 warehouse_id → 400。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/out_order/add", json=_add_payload(warehouse_id=99999))
            assert resp.status_code == 400
            assert resp.get_json()["status"] == "error"

    def test_update_accepts_warehouse_id(self):
        """T5：update 分支传 warehouse_id 改仓库。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            order = _make_draft(wh_a, material)
            order_id = order.id
            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/out_order/{order_id}/update",
                               json={"date": "2026-09-25", "warehouse_id": wh_b.id})
            body = resp.get_json()
            assert body["status"] == "success", body
            updated = OutOrder.query.get(order_id)
            assert updated.warehouse == "仓库乙", updated.warehouse


class TestOutOrderAddFormUsesWarehouseId:
    """前端迁移：out_order_add.html 仓库选择器传 ID。"""

    def test_form_field_is_warehouse_id(self):
        """T6：渲染 name="warehouse_id"，option value 为 ID。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/out_order/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert 'name="warehouse"' not in html, "仍存在旧的名称模式字段"
            assert f'value="{wh_a.id}"' in html, html
            assert 'value="仓库甲"' not in html, "option value 仍是仓库名称（未迁移）"
