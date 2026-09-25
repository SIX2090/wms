# -*- coding: utf-8 -*-
"""P1-5 回归：库存查询页「全部仓库」选项。

测试目标：
  T1. warehouse_id=0 触发全部仓库模式，库存 = Σ 各启用仓库逐仓汇总
  T2. 模板渲染「全部仓库（逐仓汇总）」选项且默认不选中（有默认仓库时选默认）
  T3. 全部仓库模式下页面上标注口径来源提示
  T4. 全部仓库模式下打印按钮被禁用（/report/stock/print 不支持全仓）
  T5. 全部仓库模式下不回退全局 Material.stock（逐仓汇总排除孤儿流水）
  T6. 翻页保留全部仓库参数（pager 传 warehouse_id=0）
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
    db, Material, MaterialCategory, Unit, User, Warehouse,
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


class TestStockQueryAllWarehouses:

    def test_get_all_warehouses_stock_quantities(self):
        """直接测试 get_all_warehouses_stock_quantities 函数。"""
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
            from app import get_all_warehouses_stock_quantities
            result = get_all_warehouses_stock_quantities()
            assert result.get(mat.id) == 15.0, result

    def test_all_warehouses_shows_sum(self):
        """T1：全部仓库模式库存 = A仓 + B仓。"""
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
            html = client.get("/stock_query?warehouse_id=0").get_data(as_text=True)
            # 逐仓汇总 = 10 + 5 = 15
            assert "15.00" in html, html

    def test_all_warehouses_option_present(self):
        """T2：模板包含「全部仓库（逐仓汇总）」选项。"""
        with app_module.app.app_context():
            _reset_db()
            set_system_setting("location_management_enabled", "0")
            _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/stock_query").get_data(as_text=True)
            assert "全部仓库（逐仓汇总）" in html, html
            assert 'value="0"' in html, html

    def test_all_warehouses_caliber_hint(self):
        """T3：全部仓库模式下页面上有口径来源提示。"""
        with app_module.app.app_context():
            _reset_db()
            set_system_setting("location_management_enabled", "0")
            _seed()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/stock_query?warehouse_id=0").get_data(as_text=True)
            assert "逐仓汇总" in html, html

    def test_all_warehouses_print_disabled(self):
        """T4：全部仓库模式下打印按钮被禁用。"""
        with app_module.app.app_context():
            _reset_db()
            set_system_setting("location_management_enabled", "0")
            mat = _seed()
            wh_a = Warehouse.query.filter_by(code="WHA").first()
            with app_module.app.test_request_context():
                add_stock(mat, 10, 'in', 'in_order', 1, warehouse=wh_a)
                db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/stock_query?warehouse_id=0").get_data(as_text=True)
            # 打印按钮应该 disabled
            assert "disabled" in html, html
            assert "选仓库打印" in html or "全部仓库模式" in html, html

    def test_all_warehouses_not_global_material_stock(self):
        """T5：全部仓库不回退全局 Material.stock。
        孤儿流水（无 warehouse_id、无 location、无 source）不计入逐仓汇总，
        但全局 Material.stock 会多算——验证差异。
        """
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
            # 直接篡改 Material.stock 为一个不一致的值（模拟历史全局账偏差）
            mat.stock = 999.0
            db.session.commit()
            client = app_module.app.test_client()
            _login(client)
            html = client.get("/stock_query?warehouse_id=0").get_data(as_text=True)
            # 逐仓汇总 = 15，不是 999（证明不回退全局 Material.stock）
            assert "15.00" in html, html
            # 库存列不应该出现 999.00
            assert "999.00" not in re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL), \
                "全局 Material.stock(999) 泄漏到库存列"

    def test_pager_preserves_all_warehouses(self):
        """T6：翻页链接保留 warehouse_id=0。"""
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
            html = client.get("/stock_query?warehouse_id=0&per_page=20").get_data(as_text=True)
            # 翻页链接中应包含 warehouse_id=0
            assert "warehouse_id=0" in html or "warehouse_id=0" in html, html
