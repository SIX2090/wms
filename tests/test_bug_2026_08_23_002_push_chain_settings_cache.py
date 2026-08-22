# -*- coding: utf-8 -*-
"""BUG-2026-08-23-002 回归测试：系统设置请求级缓存。

背景：采购入库单提交+自动下推领料单时，每条明细都会读
location_management_enabled / allow_negative_stock 等开关——100 明细的单据
一次提交触发 202 次 system_setting 查询（占全部 SQL 的 24%），生产机上放大为
秒级卡顿。修复：get_system_setting 增加请求级缓存（flask.g），
set_system_setting 同步更新缓存，complete_in_order 循环内开关提升到循环外。

覆盖：
- 同一请求内重复读同一 key 只查一次库
- 同请求内 set 后 get 读到新值（缓存一致）
- 提交+自动下推全流程中 system_setting 查询数从 2N+2 降到常量级
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module
from app import (
    DocumentPushLine,
    InOrder,
    InOrderItem,
    Material,
    OutOrder,
    Supplier,
    SystemSetting,
    Unit,
    User,
    Warehouse,
    db,
    get_system_setting,
    set_system_setting,
)
from werkzeug.security import generate_password_hash

from sqlalchemy import event

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

N_ITEMS = 20


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    unit = Unit(code="PCS", name="个")
    warehouse = Warehouse(code="CACHE_WH", name="缓存压测仓", status="active", is_default=True)
    supplier = Supplier(code="CACHE_SUP", name="缓存压测供应商")
    user = User(
        username="cache_admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        status="normal",
        must_change_password=False,
    )
    materials = [Material(code=f"CMAT{i:02d}", name=f"缓存物料{i}", unit=unit, stock=1000, price=1.2)
                 for i in range(N_ITEMS)]
    db.session.add_all([unit, warehouse, supplier, user] + materials)
    db.session.commit()
    return supplier.id, warehouse.name


def _login(client):
    response = client.post(
        "/login",
        data={"username": "cache_admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    assert response.status_code in (200, 302)


def _create_purchase_in_order(client, supplier_id, warehouse_name):
    response = client.post(
        "/in_order/add",
        json={
            "business_type": "采购入库",
            "supplier_id": supplier_id,
            "warehouse": warehouse_name,
            "auto_push_requisition": True,
            "items": [{"code": f"CMAT{i:02d}", "quantity": 3, "price": 1.2} for i in range(N_ITEMS)],
        },
    )
    body = response.get_json()
    assert body["status"] == "success", body
    return body["id"]


class _SqlCounter:
    """统计 engine 上命中关键词的 SQL 执行次数。"""

    def __init__(self, keyword):
        self.keyword = keyword
        self.count = 0
        with app_module.app.app_context():
            self.engine = db.engine

    def _before(self, conn, cursor, statement, parameters, context, executemany):
        if self.keyword in statement:
            self.count += 1

    def start(self):
        event.listen(self.engine, "before_cursor_execute", self._before)

    def stop(self):
        event.remove(self.engine, "before_cursor_execute", self._before)


class TestSystemSettingRequestCache:
    def setup_method(self):
        with app_module.app.app_context():
            _reset_db()
            self.supplier_id, self.warehouse_name = _seed()
        self.client = app_module.app.test_client()
        _login(self.client)

    def test_repeated_reads_hit_cache_within_request(self):
        """同一请求内重复读同一 key 只查一次库。"""
        with app_module.app.test_request_context():
            counter = _SqlCounter("system_setting")
            counter.start()
            try:
                for _ in range(5):
                    assert get_system_setting("location_management_enabled", "0") == "0"
                for _ in range(5):
                    assert get_system_setting("allow_negative_stock", "0") == "0"
                assert get_system_setting("allow_negative_stock", "0") == "0"
            finally:
                counter.stop()
            # 2 个 key 各自只查一次；修复前是 11 次
            assert counter.count == 2, f"system_setting 查询 {counter.count} 次，应为 2"

    def test_set_updates_request_cache(self):
        """同请求内 set_system_setting 后 get 立即读到新值，且不额外查库。"""
        with app_module.app.test_request_context():
            counter = _SqlCounter("system_setting")
            counter.start()
            try:
                assert get_system_setting("quantity_decimal_places", "3") == "3"
                set_system_setting("quantity_decimal_places", "5")
                assert get_system_setting("quantity_decimal_places", "3") == "5"
            finally:
                counter.stop()
            # 1 次 get 查询 + 1 次 set 定位行 = 2；set 后 get 命中缓存不额外查库
            assert counter.count == 2, f"system_setting 查询 {counter.count} 次，应为 2"

    def test_complete_auto_push_settings_query_count_bounded(self):
        """提交+自动下推领料单全流程：system_setting 查询数从 2N+2 降到常量级。"""
        order_id = _create_purchase_in_order(self.client, self.supplier_id, self.warehouse_name)
        counter = _SqlCounter("system_setting")
        counter.start()
        try:
            response = self.client.post(f"/in_order/{order_id}/complete?force=1")
        finally:
            counter.stop()
        body = response.get_json()
        assert body["status"] == "success", body
        assert body["auto_requisition_id"]
        # 修复前约 2*N+2=42；修复后应 ≤ 6（登录态/预检等少量常数次）
        assert counter.count <= 6, f"complete+autopush 中 system_setting 查询 {counter.count} 次，应 ≤ 6"

        with app_module.app.app_context():
            requisition = db.session.get(OutOrder, body["auto_requisition_id"])
            assert requisition.status == "completed"
            assert len(requisition.items) == N_ITEMS
            assert DocumentPushLine.query.count() == N_ITEMS
