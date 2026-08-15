# -*- coding: utf-8 -*-
"""BUG-2026-08-16-007 回归：库存查询按所选仓库过滤展示。

根因：stock_query 页面把 material.stock 全局总数当仓库级库存展示，
LocationInventory 行不按所选仓库过滤（A/B 分仓时相互串仓）；而
api_query_search 已用 get_warehouse_stock_quantities 仓库级口径，
两处不一致。

修复：stock_query 路由改用 get_warehouse_stock_quantities 得到所选仓库
库存传入模板展示；开启库位管理时库位行按 warehouse_id 过滤（兼容历史上
warehouse_id IS NULL 且 location==仓库名的旧行）。

测试用例：
  T1. 关库位管理：A/B 双仓入库不同数量，A 仓页显示 A 数量、B 仓页显示 B 数量
  T2. 开库位管理：A/B 双仓库位各自落账，A 仓页不显示 B 仓库位
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
from app import (  # noqa: E402
    db, Material, MaterialCategory, LocationInventory, Unit, User, Warehouse,
    add_stock, set_system_setting,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    from werkzeug.security import generate_password_hash
    db.session.add_all([
        Unit(name="个", code="PCS"),
        MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
        Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        Warehouse(code="WHB", name="仓库B", status="active"),
        User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False),
    ])
    db.session.commit()
    mat = Material(code="M001", name="轴承", spec="6204",
                   category_id=1, unit_id=1, stock=0, price=10)
    db.session.add(mat)
    db.session.commit()
    return mat


def _login(client):
    page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


def _stock_cell(html):
    """从渲染后的表格提取库存列首个数值（去掉逗号/货币符号）。"""
    m = re.search(r'<td class="[^"]*">(\d+\.?\d*)</td>', html)
    return m.group(1) if m else None


class TestStockQueryWarehouseFilter:

    def test_off_location_warehouse_specific_stock(self):
        """T1：关库位管理，A/B 双仓库存独立展示。"""
        with app_module.app.app_context():
            _reset_db()
            set_system_setting("location_management_enabled", "0")
            mat = _seed()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            with app_module.app.test_request_context():
                add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
                add_stock(mat, 5, 'in', 'in_order', 2, warehouse=wh_b)
                db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            html_a = client.get(
                "/stock_query?warehouse_id=%d" % wh_a.id).get_data(as_text=True)
            html_b = client.get(
                "/stock_query?warehouse_id=%d" % wh_b.id).get_data(as_text=True)
            assert "10.00" in html_a, html_a
            assert "5.00" in html_b, html_b
            assert "5.00" not in html_a, html_a

    def test_on_location_rows_filtered_by_warehouse(self):
        """T2：开库位管理，库位行按仓库过滤，A 仓页不显示 B 仓库位。"""
        with app_module.app.app_context():
            _reset_db()
            set_system_setting("location_management_enabled", "1")
            mat = _seed()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            wh_b = Warehouse.query.filter_by(code="WHB").first()
            with app_module.app.test_request_context():
                add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
                add_stock(mat, 5, 'in', 'in_order', 2, warehouse=wh_b)
                db.session.commit()
            # 直接建两仓库的库位账
            db.session.add_all([
                LocationInventory(material_id=mat.id, warehouse_id=wh_a.id,
                                  location="主仓-A1", quantity=10),
                LocationInventory(material_id=mat.id, warehouse_id=wh_b.id,
                                  location="主仓-B1", quantity=5),
            ])
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            html_a = client.get(
                "/stock_query?warehouse_id=%d" % wh_a.id).get_data(as_text=True)
            assert "主仓-A1" in html_a, html_a
            assert "主仓-B1" not in html_a, html_a
            html_b = client.get(
                "/stock_query?warehouse_id=%d" % wh_b.id).get_data(as_text=True)
            assert "主仓-B1" in html_b, html_b
            assert "主仓-A1" not in html_b, html_b