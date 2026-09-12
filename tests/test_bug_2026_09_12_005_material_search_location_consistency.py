# -*- coding: utf-8 -*-
"""BUG-2026-09-12-005 回归：/api/material/search 带仓库时 stock 与 locations 同口径。

根因：带 warehouse 上下文时
- stock 走 get_warehouse_stock_quantities（含历史 NULL warehouse_id 兼容）
- locations 走 build_material_locations_map（默认仅 warehouse_id 精确匹配）
两者口径分叉 → 同一响应出现「stock=70 但库位明细只列 50」，作业员按库位
找货会少找 20 件（违反 R2 第 2、3 条）。

修复：带仓上下文时向 build_material_locations_map 传 legacy_location_names。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    LocationInventory,
    Material,
    MaterialCategory,
    Unit,
    User,
    Warehouse,
    db,
    set_system_setting,
)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["WTF_CSRF_ENABLED"] = False
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        set_system_setting("location_management_enabled", "1")
        db.session.add_all([
            User(username="admin", password_hash=generate_password_hash("admin"),
                 role="admin", must_change_password=False),
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
            Warehouse(code="WHB", name="仓库B", is_default=False, status="active"),
        ])
        db.session.commit()
        db.session.add(Material(code="M001", name="测试物料", brand="测试品牌",
                                category_id=1, unit_id=1, stock=100))
        db.session.commit()
    tc = app_module.app.test_client()
    tc.post("/login", data={"username": "admin", "password": "admin"})
    return tc


def _search(client, qs):
    body = client.get("/api/material/search?" + qs).get_json()
    assert body["status"] == "success"
    return body["data"][0]


def test_search_stock_equals_locations_sum_with_warehouse(client):
    """R2-3 汇总=明细：带仓搜索时 stock 必须等于 locations 明细之和。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            # 历史脏数据行：warehouse_id 为 NULL、location 写的是本仓库名
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="仓库A", quantity=20),
        ])
        db.session.commit()

    row = _search(client, "kw=M001&warehouse=仓库A")
    assert row["stock"] == 70.0
    assert sum(x["quantity"] for x in row["locations"]) == 70.0
    locs = {x["location"]: x["quantity"] for x in row["locations"]}
    assert locs == {"货架A-03": 50.0, "仓库A": 20.0}


def test_search_legacy_row_by_warehouse_code(client):
    """历史行的 location 写的是仓库编码（而非名称）时同样纳入。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=5),
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="WHA", quantity=15),
        ])
        db.session.commit()

    row = _search(client, "kw=M001&warehouse=仓库A")
    assert row["stock"] == 20.0
    assert sum(x["quantity"] for x in row["locations"]) == 20.0


def test_search_warehouse_isolation_for_legacy_rows(client):
    """R2-1 隔离：B 仓的历史行不得串入 A 仓搜索结果。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        wh_b = Warehouse.query.filter_by(code="WHB").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="仓库B", quantity=888),
            LocationInventory(material_id=m.id, warehouse_id=wh_b.id,
                              location="货架X-01", quantity=999),
        ])
        db.session.commit()

    row = _search(client, "kw=M001&warehouse=仓库A")
    assert row["stock"] == 50.0
    locs = {x["location"]: x["quantity"] for x in row["locations"]}
    assert locs == {"货架A-03": 50.0}
    assert "仓库B" not in locs and "货架X-01" not in locs


def test_search_without_warehouse_unchanged(client):
    """无仓上下文：stock 走全局，locations 不过滤仓库——行为保持不变。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        wh_b = Warehouse.query.filter_by(code="WHB").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=m.id, warehouse_id=wh_b.id,
                              location="货架X-01", quantity=999),
        ])
        db.session.commit()

    row = _search(client, "kw=M001")
    assert row["stock"] == 100.0  # 全局 Material.stock
    assert {x["location"] for x in row["locations"]} == {"货架A-03", "货架X-01"}


def test_search_still_no_n_plus_1(client):
    """防退化：命中 100 条时库位查询仍为常量级（不得退化为逐条）。"""
    from sqlalchemy import event

    with app_module.app.app_context():
        for i in range(2, 31):
            db.session.add(Material(code="M%03d" % i, name="物料%d" % i,
                                    category_id=1, unit_id=1, stock=1))
        db.session.commit()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        for m in Material.query.all():
            db.session.add(LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                                             location="货架A-01", quantity=5))
        db.session.commit()
        engine = db.engine

    counted = {"loc": 0}

    def _before(conn, cursor, statement, params, context, executemany):
        if "location_inventory" in statement.lower():
            counted["loc"] += 1

    event.listen(engine, "before_cursor_execute", _before)
    try:
        client.get("/api/material/search?kw=M&warehouse=仓库A")
    finally:
        event.remove(engine, "before_cursor_execute", _before)

    assert counted["loc"] <= 5, (
        "带仓搜索的库位查询应为常量级，实际 %d 条（疑似 N+1）" % counted["loc"]
    )
