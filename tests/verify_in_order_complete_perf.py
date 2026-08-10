# -*- coding: utf-8 -*-
"""
采购入库单完成入库性能测试。

验证 complete_in_order 在多明细场景下的响应时间和查询扩展性。

核心指标：
- 查询斜率（每条明细增加的查询次数）：应 < 5，超过则存在 N+1 lazy load
- 响应时间：20 条明细应在 2s 内完成
- 数据正确性：完成后库存和状态正确
"""
from __future__ import annotations

import os
import sys
import time
import unittest
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
from app import db, InOrder, InOrderItem, Material, LocationInventory  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

# 每条明细的查询次数阈值：优化前 N+1 约 5+ 次/条，优化后应 < 5
MAX_QUERIES_PER_ITEM = 5
# 响应时间阈值（秒）：内存 SQLite 20 条明细应在 2s 内
MAX_TIME_SECONDS = 2.0


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _login(client):
    r = client.post("/login", data={
        "username": "admin",
        "password": "admin",
    }, content_type="application/x-www-form-urlencoded")
    assert r.status_code in (200, 302)


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _seed_base(num_materials=20):
    from app import MaterialCategory, Supplier, Unit, Warehouse
    cat = MaterialCategory(code="PCAT", name="性能分类")
    unit = Unit(code="PCS", name="个")
    wh = Warehouse(code="PWH", name="性能仓", status="active", is_default=True)
    sup = Supplier(code="PS1", name="性能供应商")
    db.session.add_all([cat, unit, wh, sup])
    db.session.flush()
    for i in range(num_materials):
        db.session.add(Material(
            code=f"PERF-{i:03d}", name=f"性能物料{i}", spec=f"SPEC-{i}",
            category_id=cat.id, unit_id=unit.id, stock=0, price=10.0,
        ))
    db.session.commit()
    return sup.id


def _reset_stock_and_orders():
    """每次测试前重置物料库存、库位库存和入库单，确保测试隔离。"""
    LocationInventory.query.delete()
    InOrderItem.query.delete()
    InOrder.query.delete()
    Material.query.update({Material.stock: 0})
    db.session.commit()


def _create_in_order_with_items(client, supplier_id, num_items=20):
    items = [{"code": f"PERF-{i:03d}", "quantity": 10, "price": 10.0}
             for i in range(num_items)]
    resp = client.post("/in_order/add", json={
        "business_type": "采购入库",
        "supplier_id": supplier_id,
        "warehouse": "性能仓",
        "items": items,
    })
    data = resp.get_json()
    assert data["status"] == "success", f"创建入库单失败: {data}"
    return data["id"]


class TestInOrderCompletePerformance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            cls.supplier_id = _seed_base(num_materials=20)

    def setUp(self):
        with app_module.app.app_context():
            _reset_stock_and_orders()
        self.client = _make_client()
        _login(self.client)

    def _complete_and_measure(self, num_items):
        """创建 num_items 明细的入库单并完成，返回 (耗时秒, 查询次数)。"""
        with app_module.app.app_context():
            _reset_stock_and_orders()

        order_id = _create_in_order_with_items(self.client, self.supplier_id, num_items)

        query_count = {"n": 0}
        with app_module.app.app_context():
            @db.event.listens_for(db.engine, "before_cursor_execute")
            def _counter(conn, cursor, statement, parameters, context, executemany):
                query_count["n"] += 1

        try:
            t0 = time.perf_counter()
            resp = self.client.post(f"/in_order/{order_id}/complete?force=true")
            elapsed = time.perf_counter() - t0
        finally:
            with app_module.app.app_context():
                db.event.remove(db.engine, "before_cursor_execute", _counter)

        data = resp.get_json()
        assert resp.status_code == 200, f"完成失败: {resp.status_code} {resp.get_data(as_text=True)}"
        assert data["status"] == "success", f"完成返回错误: {data}"

        return elapsed, query_count["n"]

    def test_complete_20_items_response_time(self):
        """20 条明细：完成响应时间应在 2s 内。"""
        elapsed, queries = self._complete_and_measure(20)
        print(f"\n[20 条明细] 耗时: {elapsed*1000:.1f}ms, 查询次数: {queries}")
        self.assertLess(elapsed, MAX_TIME_SECONDS,
                        f"20 条明细完成耗时 {elapsed:.3f}s 超过 {MAX_TIME_SECONDS}s")

    def test_query_slope_no_n_plus_1(self):
        """查询斜率验证：每条明细增加的查询次数应 < 5（无 N+1 退化）。

        优化前 N+1 导致每条明细增加 5+ 次查询（lazy-load material +
        source_purchase_order_item.purchase_order）。
        优化后每条只有业务必需查询（UPDATE Material + INSERT StockTransaction +
        SELECT/INSERT LocationInventory），约 3-4 次。
        """
        _, q5 = self._complete_and_measure(5)
        _, q20 = self._complete_and_measure(20)
        slope = (q20 - q5) / (20 - 5)
        print(f"\n[扩展性] 5 条: {q5} 次, 20 条: {q20} 次, 斜率: {slope:.1f} 次/条")
        self.assertLess(slope, MAX_QUERIES_PER_ITEM,
                        f"查询斜率 {slope:.1f} 次/条超过 {MAX_QUERIES_PER_ITEM}，"
                        f"存在 N+1 lazy load 退化（5条={q5}, 20条={q20}）")

    def test_complete_5_items_correctness(self):
        """5 条明细：完成后库存和状态正确。"""
        order_id = _create_in_order_with_items(self.client, self.supplier_id, 5)
        resp = self.client.post(f"/in_order/{order_id}/complete?force=true")
        assert resp.status_code == 200
        with app_module.app.app_context():
            order = db.session.get(InOrder, order_id)
            assert order.status == "completed"
            for item in order.items:
                mat = db.session.get(Material, item.material_id)
                assert mat.stock == 10, f"物料 {mat.code} 库存应为 10，实际 {mat.stock}"

    def test_complete_20_items_correctness(self):
        """20 条明细：完成后库存和状态正确。"""
        order_id = _create_in_order_with_items(self.client, self.supplier_id, 20)
        resp = self.client.post(f"/in_order/{order_id}/complete?force=true")
        assert resp.status_code == 200
        with app_module.app.app_context():
            order = db.session.get(InOrder, order_id)
            assert order.status == "completed"
            assert len(order.items) == 20
            for item in order.items:
                mat = db.session.get(Material, item.material_id)
                assert mat.stock == 10, f"物料 {mat.code} 库存应为 10，实际 {mat.stock}"


if __name__ == "__main__":
    unittest.main(verbosity=2)
