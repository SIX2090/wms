# -*- coding: utf-8 -*-
"""P1-6 第三批回归：requisition（工单领料）/ check（盘点）/ adjustment（调整）
仓库参数统一为 warehouse_id。

承接 BUG-2026-09-25-007（in_order）、008（out_order）。策略一致：
ID 优先、名称兜底、两者都无回退默认仓，无默认 400。

覆盖写入路径：
  - requisition: `/requisition/add`（表单）、`/requisition/<id>/update`（表单）、
                 `/requisition/save_table`（JSON）
  - check:       `/check/add`（表单）
  - adjustment:  `/adjustment/add`（JSON + 表单两模式）

测试用例：
  T1. requisition add 传 warehouse_id → 落库正确
  T2. requisition add 传名称仍正确（防回归）
  T3. requisition update 传 warehouse_id → 改仓库
  T4. requisition 无效 ID → 400
  T5. check add 传 warehouse_id → 落库正确
  T6. adjustment add 传 warehouse_id → 落库正确
  T7. 三个前端页面渲染 name="warehouse_id" 且 option value 为 ID
  T8. 共用单据模板 document_table_form.html 的 requisition/check 分支同样
      渲染 name="warehouse_id" 且 collectHeader 提交 warehouse_id
"""
from __future__ import annotations

import datetime
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
    Material, Unit, User, Warehouse, db,
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
    user = User(username="p16r", password_hash=generate_password_hash("admin"),
                role="admin", must_change_password=False)
    material = Material(code="P16R", name="领料物料", unit=unit, stock=100, price=10)
    db.session.add_all([unit, wh_a, wh_b, user, material])
    db.session.commit()
    return wh_a, wh_b, material


def _login(client):
    client.post("/login", data={"username": "p16r", "password": "admin"},
                content_type="application/x-www-form-urlencoded")


class TestRequisitionWarehouseIdParam:

    def test_add_accepts_warehouse_id(self):
        """T1：requisition add 传 warehouse_id → 落库该仓名称。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/requisition/add", data={
                "date": "2026-09-25",
                "warehouse_id": wh_b.id,
                "items": "[]",
            }, content_type="application/x-www-form-urlencoded")
            body = resp.get_json()
            assert body is not None, resp.get_data(as_text=True)[:400]
            assert body.get("status") == "success", body
            from app import ProductionRequisition
            req = ProductionRequisition.query.get(body["id"])
            assert req.warehouse == "仓库乙", req.warehouse

    def test_add_legacy_name_still_works(self):
        """T2：requisition add 传名称仍正确（防回归）。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/requisition/add", data={
                "date": "2026-09-25",
                "warehouse": "仓库乙",
                "items": "[]",
            }, content_type="application/x-www-form-urlencoded")
            body = resp.get_json()
            assert body.get("status") == "success", body
            from app import ProductionRequisition
            req = ProductionRequisition.query.get(body["id"])
            assert req.warehouse == "仓库乙", req.warehouse

    def test_update_accepts_warehouse_id(self):
        """T3：requisition update 传 warehouse_id 改仓库。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            from app import ProductionRequisition
            req = ProductionRequisition(
                req_no="P16-REQ-1", date=datetime.date.today(),
                warehouse=wh_a.name, status="pending")
            db.session.add(req)
            db.session.commit()
            req_id = req.id
            client = app_module.app.test_client()
            _login(client)
            resp = client.post(f"/requisition/{req_id}/update", data={
                "date": "2026-09-25",
                "warehouse_id": wh_b.id,
                "items": "[]",
            }, content_type="application/x-www-form-urlencoded")
            body = resp.get_json()
            assert body.get("status") == "success", body
            updated = ProductionRequisition.query.get(req_id)
            assert updated.warehouse == "仓库乙", updated.warehouse

    def test_invalid_id_rejected(self):
        """T4：无效 warehouse_id → 400。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/requisition/add", data={
                "date": "2026-09-25",
                "warehouse_id": 99999,
                "items": "[]",
            }, content_type="application/x-www-form-urlencoded")
            body = resp.get_json()
            assert body.get("status") == "error", body


class TestCheckAndAdjustmentWarehouseIdParam:

    def test_check_add_accepts_warehouse_id(self):
        """T5：check add 传 warehouse_id → 落库正确。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/check/add", data={
                "date": "2026-09-25",
                "warehouse_id": wh_b.id,
            }, content_type="application/x-www-form-urlencoded")
            body = resp.get_json()
            assert body.get("status") == "success", body
            from app import InventoryCheck
            chk = InventoryCheck.query.get(body["id"])
            assert chk.warehouse == "仓库乙", chk.warehouse

    def test_adjustment_add_accepts_warehouse_id(self):
        """T6：adjustment add 传 warehouse_id → 落库正确。"""
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            resp = client.post("/adjustment/add", json={
                "date": "2026-09-25",
                "adjustment_type": "surplus",  # 有效值：surplus / loss（中文"盘盈"会被拒）
                "warehouse_id": wh_b.id,
                # 至少一条明细，否则后端报「请至少填写一条调整明细」
                "items": [{"material_id": material.id, "quantity": 1}],
            })
            body = resp.get_json()
            assert body.get("status") == "success", body
            from app import AdjustmentOrder
            adj = AdjustmentOrder.query.get(body["id"])
            assert adj.warehouse == "仓库乙", adj.warehouse


class TestFormsUseWarehouseId:
    """前端迁移：三个页面渲染 warehouse_id 且 option value 为 ID。"""

    def test_requisition_form(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/requisition/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert 'name="warehouse"' not in html
            assert f'value="{wh_a.id}"' in html, html

    def test_check_form(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/check").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert f'value="{wh_a.id}"' in html, html

    def test_adjustment_form(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/adjustment/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert f'value="{wh_a.id}"' in html, html


class TestSharedDocumentTableForm:
    """T8：/requisition/add 与 /check/add 实际渲染的是共用模板
    document_table_form.html（不是 requisition.html / check.html），
    必须一并迁移，否则用户点「新增」提交的还是仓库名称。"""

    def test_requisition_add_form_uses_warehouse_id(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/requisition/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert 'name="warehouse"' not in html, html
            assert f'value="{wh_a.id}"' in html, html
            # collectHeader 不再提交 warehouse 名称
            assert "warehouse_id:get('warehouse_id')" in html, html
            assert "warehouse:get('warehouse')" not in html, html
            # 刷新下拉的 JS 用 ID 比对
            assert 'String(current) === String(w.id)' in html, html

    def test_check_add_form_uses_warehouse_id(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/check/add").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert 'name="warehouse"' not in html, html
            assert f'value="{wh_a.id}"' in html, html

    def test_requisition_list_form_uses_warehouse_id(self):
        with app_module.app.app_context():
            _reset_db()
            wh_a, wh_b, material = _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/requisition").get_data(as_text=True)
            assert 'name="warehouse_id"' in html, html
            assert f'value="{wh_a.id}"' in html, html
