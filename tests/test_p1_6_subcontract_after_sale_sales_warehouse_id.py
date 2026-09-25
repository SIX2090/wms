# -*- coding: utf-8 -*-
"""P1-6 第四批回归：subcontract（委外收发料）/ after_sale_out（售后出库）/
sales_order（销售订单）仓库参数统一为 warehouse_id。

承接 BUG-2026-09-25-007（in_order）、008（out_order）、009（requisition/check/adjustment）。
策略一致：ID 优先 → 名称兜底 → 默认仓 → 无默认 400；JSON 模式下
warehouse_id 可能是 int，不可 .strip()。

本批特殊点：
  - 委外父单（SubcontractOrder.warehouse）只存**名称**，下拉改成 ID 后无法
    直接回填，故模板在委外单 option 上补 `data-warehouse-id`，JS 按 ID 回填。
  - 售后出库编辑页对「历史仓库名已不在启用列表」的场景，不能把名称当 ID 提交
    （resolve_active_inventory_warehouse 对非数字 warehouse_id 直接判无效），
    改为置空禁用强制重选。
  - 销售订单后端**早就支持** warehouse_id（sales.py:545/691），本批只迁前端。

测试用例：
  T1. 委外发料 add 传 warehouse_id → 落库正确
  T2. 委外收料 add 传 warehouse_id → 落库正确
  T3. ID 优先于名称（同时传 warehouse=主仓 + warehouse_id=委外仓 → 委外仓）
  T4. 无效 warehouse_id → 400
  T5. 售后出库 add 传 warehouse_id → 落库正确（JSON int）
  T6. 售后出库 add 传名称仍可用（旧客户端兜底）
  T7. 5 个页面渲染 name="warehouse_id" 且 option value 为 ID
  T8. 委外两个页面的委外单 option 带 data-warehouse-id
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    AfterSaleOutOrder, Material, MaterialCategory, SubcontractIssue,
    SubcontractOrder, SubcontractReceive, Supplier, Unit, User, Warehouse, db,
    generate_order_no, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    return token.group(1) if token else ""


@pytest.fixture()
def client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(
            username="p16d", password_hash=generate_password_hash("admin"),
            role="admin", must_change_password=False,
        ))
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Supplier(code="SUP001", name="加工厂"),
            Warehouse(code="WH01", name="主仓", status="active", is_default=True),
            Warehouse(code="WH02", name="委外仓", status="active", is_default=False),
        ])
        db.session.commit()
        db.session.add(Material(code="M-P16D", name="原材料", spec="S",
                                category_id=1, unit_id=1, supplier_id=1,
                                stock=100, price=1))
        db.session.add(SubcontractOrder(order_no="SC001", supplier_id=1,
                                        warehouse="主仓", status="processing"))
        set_system_setting("location_management_enabled", "0")
        db.session.commit()
    c = app_module.app.test_client()
    token = _login(c)
    c.post("/login", data={"username": "p16d", "password": "admin",
                           "csrf_token": token})
    yield c


def _wh_id(name):
    with app_module.app.app_context():
        return Warehouse.query.filter_by(name=name).one().id


def _order_id():
    with app_module.app.app_context():
        return SubcontractOrder.query.filter_by(order_no="SC001").one().id


class TestSubcontractWarehouseIdParam:
    """委外发料 / 收料：后端接受 warehouse_id。"""

    def test_issue_add_accepts_warehouse_id(self, client):
        wh2 = _wh_id("委外仓")
        resp = client.post("/subcontract/issue/add", data={
            "subcontract_order_id": str(_order_id()),
            "warehouse_id": str(wh2),
            "remark": "ID 选仓",
        })
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
            assert issue.warehouse == "委外仓"

    def test_receive_add_accepts_warehouse_id(self, client):
        wh2 = _wh_id("委外仓")
        resp = client.post("/subcontract/receive/add", data={
            "subcontract_order_id": str(_order_id()),
            "warehouse_id": str(wh2),
            "remark": "ID 选仓",
        })
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            receive = SubcontractReceive.query.order_by(
                SubcontractReceive.id.desc()).first()
            assert receive.warehouse == "委外仓"

    def test_id_takes_precedence_over_name(self, client):
        """同时传 warehouse=主仓 与 warehouse_id=委外仓时，必须以 ID 为准。

        防止「改了字段名但后端仍按名称优先」的假迁移。
        """
        wh2 = _wh_id("委外仓")
        resp = client.post("/subcontract/issue/add", data={
            "subcontract_order_id": str(_order_id()),
            "warehouse": "主仓",
            "warehouse_id": str(wh2),
        })
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            issue = SubcontractIssue.query.order_by(SubcontractIssue.id.desc()).first()
            assert issue.warehouse == "委外仓"

    def test_invalid_warehouse_id_rejected(self, client):
        resp = client.post("/subcontract/issue/add", data={
            "subcontract_order_id": str(_order_id()),
            "warehouse_id": "999999",
        })
        body = resp.get_json()
        assert body.get("status") == "error", body
        assert "仓库" in (body.get("msg") or ""), body


class TestAfterSaleOutWarehouseIdParam:
    """售后出库：后端接受 warehouse_id（JSON 下为 int，不可 .strip()）。"""

    def _payload(self, **extra):
        with app_module.app.app_context():
            order_no = generate_order_no("ASO")
        payload = {
            "order_no": order_no,
            "date": "2026-09-25",
            "customer": "P16D客户",
            "items": [{"code": "M-P16D", "quantity": 1, "price": 1}],
        }
        payload.update(extra)
        return payload

    def test_add_accepts_warehouse_id(self, client):
        wh2 = _wh_id("委外仓")
        resp = client.post("/after_sale_out/add",
                           json=self._payload(warehouse_id=wh2))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            order = AfterSaleOutOrder.query.filter_by(
                customer="P16D客户").order_by(AfterSaleOutOrder.id.desc()).first()
            assert order is not None
            assert order.warehouse == "委外仓"

    def test_add_legacy_name_still_works(self, client):
        resp = client.post("/after_sale_out/add",
                           json=self._payload(warehouse="委外仓"))
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success", body
        with app_module.app.app_context():
            order = AfterSaleOutOrder.query.filter_by(
                customer="P16D客户").order_by(AfterSaleOutOrder.id.desc()).first()
            assert order.warehouse == "委外仓"

    def test_invalid_warehouse_id_rejected(self, client):
        resp = client.post("/after_sale_out/add",
                           json=self._payload(warehouse_id=999999))
        assert resp.status_code == 400, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body.get("status") == "error", body


class TestFormsUseWarehouseId:
    """前端迁移：5 个页面渲染 warehouse_id 且 option value 为 ID。"""

    @pytest.mark.parametrize("url,marker", [
        ("/subcontract_issue", 'id="issueWarehouse"'),
        ("/subcontract_receive", 'id="receiveWarehouse"'),
        ("/after_sale_out/add", "请选择仓库"),
        ("/sales/add", "发货仓库"),
    ])
    def test_form_uses_warehouse_id(self, client, url, marker):
        html = client.get(url).get_data(as_text=True)
        assert 'name="warehouse_id"' in html, (url, html[:500])
        assert 'name="warehouse"' not in html, (url, "仍有旧字段名")
        assert marker in html, (url, marker)

    def test_sales_order_edit_uses_warehouse_id(self, client):
        """编辑页：option 原来连 value 都没有（提交文本），必须补 ID。"""
        from app import Customer, SalesOrder
        with app_module.app.app_context():
            customer = Customer(code="C01", name="客户一")
            db.session.add(customer)
            db.session.commit()
            order = SalesOrder(order_no="SO-P16D", customer_id=customer.id,
                               warehouse="委外仓", warehouse_id=_wh_id("委外仓"),
                               status="draft")
            db.session.add(order)
            db.session.commit()
            oid = order.id
        html = client.get(f"/sales/{oid}/edit").get_data(as_text=True)
        assert 'name="warehouse_id"' in html, html[:500]
        assert 'name="warehouse"' not in html
        # 编辑页按 ID 预选当前仓库
        wh2 = _wh_id("委外仓")
        assert re.search(r'<option value="%d"[^>]*selected[^>]*>' % wh2, html), html


class TestSubcontractOrderOptionCarriesWarehouseId:
    """委外父单只存名称，模板必须额外给出 ID 供 JS 回填。"""

    @pytest.mark.parametrize("url", ["/subcontract_issue", "/subcontract_receive"])
    def test_order_option_has_warehouse_id(self, client, url):
        wh1 = _wh_id("主仓")
        html = client.get(url).get_data(as_text=True)
        assert f'data-warehouse-id="{wh1}"' in html, html
        # JS 必须按 ID 回填，而不是按名称
        assert "data('warehouse-id')" in html, html
        assert ".data('warehouse')" not in html, html
