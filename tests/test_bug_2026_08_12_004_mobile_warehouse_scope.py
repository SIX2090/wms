# -*- coding: utf-8 -*-
"""BUG-2026-08-12-004 回归：移动端库存/告警/单据/期初读取接口必须按仓库隔离。

规则依据（AGENTS.md 仓库必填规则 + WMS_FULL_AUDIT_REPAIR_PROMPT FIX-1）：
- 显式 warehouse_id / warehouse_code / warehouse 必须指向存在且 active 的仓库；
- 未提供仓库参数时带入默认仓库；无默认仓库统一返回 400「请选择仓库」；
- 单据列表/详情、dashboard 统计、期初库存必须按解析仓库过滤，详情跨仓返回 404；
- 移动库存查询/告警必须使用仓库级数量（LocationInventory 以仓库名为键；
  库位管理关闭时回退 StockTransaction.location 流水净额），不得读取全局 Material.stock。
"""
from __future__ import annotations

import os
import sys
from datetime import date
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

TODAY = date.today()


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    return client.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name, is_default=False, status="active"):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status=status, is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code, name, stock=0, min_stock=0):
    from app import Material
    m = Material(code=code, name=name, stock=stock, min_stock=min_stock)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_location_stock(material, warehouse_name, quantity):
    from app import LocationInventory
    db.session.add(LocationInventory(material_id=material.id, location=warehouse_name, quantity=quantity))
    db.session.commit()


def _seed_in_order(order_no, warehouse_name, status="pending", with_item=None):
    from app import InOrder, InOrderItem
    order = InOrder(order_no=order_no, warehouse=warehouse_name, status=status, date=TODAY)
    db.session.add(order)
    db.session.flush()
    if with_item is not None:
        material, quantity = with_item
        db.session.add(InOrderItem(in_order_id=order.id, material_id=material.id,
                                   quantity=quantity, price=1, amount=quantity))
    db.session.commit()
    return order


def _seed_out_order(order_no, warehouse_name, status="pending", with_item=None):
    from app import OutOrder, OutOrderItem
    order = OutOrder(order_no=order_no, warehouse=warehouse_name, status=status, date=TODAY)
    db.session.add(order)
    db.session.flush()
    if with_item is not None:
        material, quantity = with_item
        db.session.add(OutOrderItem(out_order_id=order.id, material_id=material.id,
                                    quantity=quantity, price=1, amount=quantity))
    db.session.commit()
    return order


def _seed_opening_stock(material, warehouse, quantity=1):
    from app import OpeningStock
    db.session.add(OpeningStock(material_id=material.id, warehouse_id=warehouse.id,
                                date=TODAY, quantity=quantity, price=1, amount=quantity))
    db.session.commit()


def _enable_location_management():
    from app import set_system_setting
    set_system_setting("location_management_enabled", "1")
    set_system_setting("inventory_alert_enabled", "1")
    db.session.commit()


class _BaseScope:
    """公共夹具：仓库 A（默认）/ B / C（停用），物料与仓库级库存。"""

    def _setup(self, with_default=True):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            self.wh_a = _seed_warehouse("WHA", "仓库A", is_default=with_default)
            self.wh_b = _seed_warehouse("WHB", "仓库B")
            self.wh_c = _seed_warehouse("WHC", "仓库C", status="inactive")
            self.m1 = _seed_material("M001", "6204轴承", stock=100, min_stock=10)
            self.m2 = _seed_material("M002", "M8螺母", stock=50, min_stock=0)
            _enable_location_management()
            # 仓库级库存：A=5 / B=95（全局 stock=100 不得被移动端读取）
            _seed_location_stock(self.m1, "仓库A", 5)
            _seed_location_stock(self.m1, "仓库B", 95)
            _seed_location_stock(self.m2, "仓库A", 3)
            # 单据：A/B 各一完成一待办
            self.in_a1 = _seed_in_order("IN-A1", "仓库A", status="completed", with_item=(self.m1, 2))
            self.in_a2 = _seed_in_order("IN-A2", "仓库A", status="pending")
            self.in_b1 = _seed_in_order("IN-B1", "仓库B", status="pending")
            self.out_a1 = _seed_out_order("OUT-A1", "仓库A", status="pending")
            self.out_b1 = _seed_out_order("OUT-B1", "仓库B", status="completed", with_item=(self.m2, 3))
            # 期初库存：M001→A，M002→B
            _seed_opening_stock(self.m1, self.wh_a, quantity=7)
            _seed_opening_stock(self.m2, self.wh_b, quantity=9)
            # 在 app_context 内提取 ID，避免外部访问 detached ORM 实例
            self.wh_a_id = self.wh_a.id
            self.wh_b_id = self.wh_b.id
            self.wh_c_id = self.wh_c.id
            self.in_a1_id = self.in_a1.id
            self.in_b1_id = self.in_b1.id
            self.out_a1_id = self.out_a1.id
            self.out_b1_id = self.out_b1.id
        client = _make_client()
        _login(client)
        return client


class TestMobileWarehouseScope(_BaseScope):
    def test_dashboard_scoped_to_default_warehouse(self):
        """无仓库参数且存在默认仓库 A 时，dashboard 只统计仓库 A。"""
        client = self._setup()
        resp = client.get("/api/mobile/dashboard")
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()["data"]
        assert data["today_in_orders"] == 1  # IN-A1（B 仓的完成单不计）
        assert data["today_in_quantity"] == 2
        assert data["today_out_orders"] == 0  # OUT-B1 属于 B 仓
        assert data["today_out_quantity"] == 0
        assert data["pending_in_orders"] == 1  # IN-A2（IN-B1 不计）
        assert data["pending_out_orders"] == 1  # OUT-A1（OUT-B1 已完成为 0）
        # 告警：M001 在 A 仓 5 <= min_stock 10 → 1 条；M002 无 min_stock → 不计
        assert data["alert_count"] == 1

    def test_order_lists_scoped_to_default_warehouse(self):
        """入库/出库列表无参数时只返回默认仓库 A 的单据。"""
        client = self._setup()
        resp = client.get("/api/mobile/in_order/list")
        assert resp.status_code == 200
        numbers = {item["order_no"] for item in resp.get_json()["data"]["items"]}
        assert numbers == {"IN-A1", "IN-A2"}, numbers

        resp = client.get("/api/mobile/out_order/list")
        assert resp.status_code == 200
        numbers = {item["order_no"] for item in resp.get_json()["data"]["items"]}
        assert numbers == {"OUT-A1"}, numbers

    def test_explicit_warehouse_id_scopes_results(self):
        """显式 warehouse_id=B 时，列表/dashboard/期初库存不得包含 A 仓数据。"""
        client = self._setup()
        resp = client.get(f"/api/mobile/in_order/list?warehouse_id={self.wh_b_id}")
        assert resp.status_code == 200
        numbers = {item["order_no"] for item in resp.get_json()["data"]["items"]}
        assert numbers == {"IN-B1"}, numbers

        resp = client.get(f"/api/mobile/dashboard?warehouse_id={self.wh_b_id}")
        data = resp.get_json()["data"]
        assert data["today_out_orders"] == 1  # OUT-B1
        assert data["today_out_quantity"] == 3
        assert data["today_in_orders"] == 0
        assert data["pending_in_orders"] == 1  # IN-B1
        assert data["alert_count"] == 0  # M001 在 B 仓 95 > min_stock 10

        resp = client.get(f"/api/opening_stock?warehouse_id={self.wh_b_id}")
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        assert {item["material_code"] for item in items} == {"M002"}, items

    def test_warehouse_code_param_scopes_results(self):
        """warehouse_code 与 warehouse_id 走同一解析规则。"""
        client = self._setup()
        resp = client.get("/api/mobile/out_order/list?warehouse_code=WHB")
        assert resp.status_code == 200
        numbers = {item["order_no"] for item in resp.get_json()["data"]["items"]}
        assert numbers == {"OUT-B1"}, numbers

    def test_no_default_warehouse_returns_400(self):
        """无仓库参数且无默认仓库时，所有移动端读取接口统一 400「请选择仓库」。"""
        client = self._setup(with_default=False)
        order_id = self.in_a1_id
        out_id = self.out_a1_id
        endpoints = [
            "/api/mobile/dashboard",
            "/api/mobile/stock/query",
            "/api/mobile/alert/list",
            "/api/mobile/in_order/list",
            f"/api/mobile/in_order/{order_id}",
            "/api/mobile/out_order/list",
            f"/api/mobile/out_order/{out_id}",
            "/api/opening_stock",
        ]
        for url in endpoints:
            resp = client.get(url)
            assert resp.status_code == 400, f"{url} 应返回 400，实际 {resp.status_code}"
            body = resp.get_json()
            assert "请选择仓库" in body["msg"], f"{url} 错误信息: {body}"

    def test_cross_warehouse_detail_returns_404(self):
        """请求仓库 A 的单据详情但单据属于仓库 B 时返回 404。"""
        client = self._setup()
        resp = client.get(f"/api/mobile/in_order/{self.in_b1_id}?warehouse_id={self.wh_a_id}")
        assert resp.status_code == 404, resp.get_data(as_text=True)
        resp = client.get(f"/api/mobile/out_order/{self.out_b1_id}?warehouse_id={self.wh_a_id}")
        assert resp.status_code == 404, resp.get_data(as_text=True)
        # 同仓详情正常返回
        resp = client.get(f"/api/mobile/in_order/{self.in_a1_id}?warehouse_id={self.wh_a_id}")
        assert resp.status_code == 200, resp.get_data(as_text=True)

    def test_stock_query_uses_warehouse_quantities_not_global(self):
        """移动库存查询必须返回仓库级数量，不得回退到全局 Material.stock。"""
        client = self._setup()
        resp = client.get(f"/api/mobile/stock/query?warehouse_id={self.wh_a_id}")
        assert resp.status_code == 200
        items = {item["code"]: item for item in resp.get_json()["data"]["items"]}
        assert items["M001"]["stock"] == 5, items["M001"]  # 全局 stock=100 不得出现
        assert items["M002"]["stock"] == 3, items["M002"]

        resp = client.get(f"/api/mobile/stock/query?warehouse_id={self.wh_b_id}")
        items = {item["code"]: item for item in resp.get_json()["data"]["items"]}
        assert items["M001"]["stock"] == 95, items["M001"]
        # B 仓无 M002 记录 → 0，不得回退全局 50
        assert items["M002"]["stock"] == 0, items["M002"]

    def test_alert_list_uses_warehouse_quantities(self):
        """告警列表的低库存判定必须针对解析仓库。"""
        client = self._setup()
        resp = client.get(f"/api/mobile/alert/list?warehouse_id={self.wh_a_id}")
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        assert [item["code"] for item in items] == ["M001"], items
        assert items[0]["stock"] == 5
        assert items[0]["gap"] == 5  # min_stock 10 - 5

        resp = client.get(f"/api/mobile/alert/list?warehouse_id={self.wh_b_id}")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["items"] == []

    def test_opening_stock_scoped_to_default_warehouse(self):
        """期初库存 GET 无参数时必须按默认仓库过滤。"""
        client = self._setup()
        resp = client.get("/api/opening_stock")
        assert resp.status_code == 200
        items = resp.get_json()["data"]["items"]
        assert {item["material_code"] for item in items} == {"M001"}, items
        assert all(item["warehouse_id"] == self.wh_a_id for item in items)

    def test_inactive_or_unknown_warehouse_returns_400(self):
        """仓库不存在或已停用时返回 400 并带用户可读错误。"""
        client = self._setup()
        resp = client.get("/api/mobile/stock/query?warehouse_id=99999")
        assert resp.status_code == 400
        assert "不存在" in resp.get_json()["msg"]

        resp = client.get(f"/api/mobile/stock/query?warehouse_id={self.wh_c_id}")
        assert resp.status_code == 400
        assert "已停用" in resp.get_json()["msg"]


class TestWarehouseScopeHelpers:
    """仓库解析与仓库级库存汇总 helper 的直接单元覆盖。"""

    def test_resolve_request_warehouse(self):
        """A9 入口：解析 helper 冒烟——显式 ID 命中、未知编码报错、无默认仓报请选择仓库。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import resolve_request_warehouse
            wh_a = _seed_warehouse("WHA", "仓库A", is_default=True)
            warehouse, err = resolve_request_warehouse({"warehouse_id": str(wh_a.id)})
            assert err is None and warehouse.id == wh_a.id
            _, err = resolve_request_warehouse({"warehouse_code": "NOPE"})
            assert err and "不存在" in err

    def test_get_warehouse_stock_quantities(self):
        """A9 入口：汇总 helper 冒烟——按 LocationInventory 仓库名汇总，不回退全局库存。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import get_warehouse_stock_quantities
            wh_a = _seed_warehouse("WHA", "仓库A", is_default=True)
            m1 = _seed_material("M001", "6204轴承", stock=100)
            _enable_location_management()
            _seed_location_stock(m1, "仓库A", 5)
            quantities = get_warehouse_stock_quantities(wh_a)
            assert quantities.get(m1.id) == 5, quantities

    def test_resolve_request_warehouse_precedence_and_default(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import resolve_request_warehouse
            wh_a = _seed_warehouse("WHA", "仓库A", is_default=True)
            _seed_warehouse("WHB", "仓库B")

            # 显式 ID 优先
            warehouse, err = resolve_request_warehouse({"warehouse_id": str(wh_a.id)})
            assert err is None and warehouse.id == wh_a.id
            # 编码解析
            warehouse, err = resolve_request_warehouse({"warehouse_code": "WHB"})
            assert err is None and warehouse.code == "WHB"
            # 名称解析
            warehouse, err = resolve_request_warehouse({"warehouse": "仓库A"})
            assert err is None and warehouse.id == wh_a.id
            # 无参数回退默认仓
            warehouse, err = resolve_request_warehouse({})
            assert err is None and warehouse.code == "WHA"
            # 未知 ID / 未知编码
            _, err = resolve_request_warehouse({"warehouse_id": "424242"})
            assert err and "不存在" in err
            _, err = resolve_request_warehouse({"warehouse_code": "NOPE"})
            assert err and "不存在" in err

    def test_resolve_request_warehouse_rejects_inactive(self):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import resolve_request_warehouse
            wh_c = _seed_warehouse("WHC", "仓库C", status="inactive")
            _, err = resolve_request_warehouse({"warehouse_id": str(wh_c.id)})
            assert err and "已停用" in err
            _, err = resolve_request_warehouse({})
            assert err == "请选择仓库"

    def test_stock_quantities_ledger_fallback_when_location_management_off(self):
        """库位管理关闭时按 StockTransaction.location == 仓库名 的流水净额汇总。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import (StockTransaction, get_warehouse_stock_quantities,
                             set_system_setting)
            wh_a = _seed_warehouse("WHA", "仓库A", is_default=True)
            _seed_warehouse("WHB", "仓库B")
            m1 = _seed_material("M001", "6204轴承", stock=100)
            set_system_setting("location_management_enabled", "0")
            db.session.add_all([
                StockTransaction(material_id=m1.id, transaction_type="in", quantity=7,
                                 location="仓库A"),
                StockTransaction(material_id=m1.id, transaction_type="out", quantity=-2,
                                 location="仓库A"),
                StockTransaction(material_id=m1.id, transaction_type="in", quantity=40,
                                 location="仓库B"),
            ])
            db.session.commit()

            quantities = get_warehouse_stock_quantities(wh_a)
            assert quantities.get(m1.id) == 5, quantities  # 7-2，绝非全局 100

            from app import Warehouse
            wh_b = Warehouse.query.filter_by(code="WHB").one()
            quantities_b = get_warehouse_stock_quantities(wh_b)
            assert quantities_b.get(m1.id) == 40, quantities_b

    def test_stock_quantities_never_fall_back_to_global_stock(self):
        """库位管理开启时仅汇总 LocationInventory（仓库名为键），空仓返回 0 而非全局库存。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            from app import get_warehouse_stock_quantities
            wh_a = _seed_warehouse("WHA", "仓库A", is_default=True)
            m1 = _seed_material("M001", "6204轴承", stock=100)
            _enable_location_management()
            _seed_location_stock(m1, "仓库A", 5)

            quantities = get_warehouse_stock_quantities(wh_a)
            assert quantities.get(m1.id) == 5, quantities

            # 仓库 B 无任何记录 → 空 dict，不得回退 Material.stock
            from app import Warehouse
            wh_b = _seed_warehouse("WHB", "仓库B")
            assert get_warehouse_stock_quantities(wh_b).get(m1.id) is None
