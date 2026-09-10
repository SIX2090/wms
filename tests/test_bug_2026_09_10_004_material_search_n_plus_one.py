# -*- coding: utf-8 -*-
"""BUG-2026-09-10-004 回归：物料列表接口消除 N+1 查询（手机端查库存性能）。

原实现 /api/material/search 在带仓库上下文时，每个物料重复一次全仓库存聚合
（get_warehouse_stock_quantities 是全仓聚合查询）+ 一次 LocationInventory
库位查询；命中上限 100 条时高达 200+ 次查询，手机端搜索明显卡顿。

修复：api_material_payload 接受调用方预取的 warehouse_stock_map / locations_map，
search 与 all 接口各预取一次（固定 1 次聚合 + 1 次库位 IN 分组查询），
单物料 /api/material/info 保持原逐物料路径，两者 payload 口径严格一致。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["WMS_DEBUG"] = "0"

from sqlalchemy import event  # noqa: E402
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

MATERIAL_COUNT = 10


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
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        wh_b = Warehouse.query.filter_by(code="WHB").first()
        for i in range(MATERIAL_COUNT):
            material = Material(
                code=f"DX{i:03d}", name=f"电线型号{i}", spec=f"{i}.5mm²",
                brand="远东", category_id=1, unit_id=1,
                stock=100 + i, min_stock=5, reorder_point=10,
            )
            db.session.add(material)
            db.session.flush()
            db.session.add_all([
                LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                                  location=f"货架A-{i:02d}", quantity=30 + i),
                LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                                  location=f"货架B-{i:02d}", quantity=10 + i),
                # B 仓数据用于验证仓库隔离不串仓（R2）
                LocationInventory(material_id=material.id, warehouse_id=wh_b.id,
                                  location=f"货架X-{i:02d}", quantity=999),
            ])
        db.session.commit()
    test_client = app_module.app.test_client()
    response = test_client.post("/login", data={"username": "admin", "password": "admin"})
    assert response.status_code in (302, 303)
    return test_client


@pytest.fixture()
def location_sql_counter():
    """统计请求期间针对 location_inventory 表执行的 SQL 次数。"""
    counts = {"location_inventory": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if "location_inventory" in statement.lower():
            counts["location_inventory"] += 1

    with app_module.app.app_context():
        engine = db.engine
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counts
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_search_with_warehouse_calls_aggregation_once(client, monkeypatch):
    """带仓库搜索 N 条物料：全仓库存聚合只算 1 次（原实现为 N 次）。"""
    calls = {"count": 0}
    original = app_module.get_warehouse_stock_quantities

    def counting_wrapper(warehouse):
        calls["count"] += 1
        return original(warehouse)

    monkeypatch.setattr(app_module, "get_warehouse_stock_quantities", counting_wrapper)

    body = client.get("/api/material/search?kw=电线&warehouse=仓库A").get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == MATERIAL_COUNT
    # 关键断言：无论命中多少条，聚合固定 1 次（原实现为 MATERIAL_COUNT 次）
    assert calls["count"] == 1
    # 账面库存口径不变：A 仓两库位之和
    for i, row in enumerate(body["data"]):
        expected = (30 + i) + (10 + i)
        assert row["stock"] == expected


def test_search_location_queries_constant(client, location_sql_counter):
    """库位分布改为批量预取：location_inventory 查询次数与命中物料数无关。

    带仓库上下文时固定为 2 次：1 次全仓库存聚合（库位管理开启时聚合
    LocationInventory）+ 1 次库位分布批量 IN 查询；原实现为 2N 次。
    """
    body = client.get("/api/material/search?kw=电线&warehouse=仓库A").get_json()
    assert len(body["data"]) == MATERIAL_COUNT
    assert location_sql_counter["location_inventory"] == 2

    # 命中数变化（10 条 → 1 条）查询次数不变，证明与 N 无关
    location_sql_counter["location_inventory"] = 0
    one = client.get("/api/material/search?kw=电线型号1&warehouse=仓库A").get_json()
    assert len(one["data"]) == 1
    assert location_sql_counter["location_inventory"] == 2
    # 库位分布内容不变：非零、数量降序、按仓库过滤
    for i, row in enumerate(body["data"]):
        assert row["locations"] == [
            {"location": f"货架A-{i:02d}", "quantity": 30 + i},
            {"location": f"货架B-{i:02d}", "quantity": 10 + i},
        ]
        assert row["location_code"] == f"货架A-{i:02d}"
        assert all(loc["location"] != f"货架X-{i:02d}" for loc in row["locations"])


def test_material_all_batches_locations(client, location_sql_counter):
    """/api/material/all 同样消除库位 N+1（原 1000 条上限即 1000 次查询）。"""
    body = client.get("/api/material/all").get_json()
    assert body["status"] == "success"
    assert len(body["data"]) == MATERIAL_COUNT
    assert location_sql_counter["location_inventory"] <= 1
    # 无仓库上下文时库位分布含全部仓库的非零库位（与原逐物料路径一致）
    row0 = body["data"][0]
    locations = [loc["location"] for loc in row0["locations"]]
    assert "货架X-00" in locations  # B 仓 999 数量最大排最前


def test_search_batched_payload_equals_single_material_path(client):
    """批量预取路径与单物料 /api/material/info（原逐物料路径）payload 严格一致。"""
    search_body = client.get("/api/material/search?kw=电线&warehouse=仓库A").get_json()
    by_code = {row["code"]: row for row in search_body["data"]}
    for code, search_row in by_code.items():
        info_row = client.get(
            f"/api/material/info?code={code}&warehouse=仓库A"
        ).get_json()["data"]
        for field in ("stock", "min_stock", "reorder_point",
                      "location_code", "locations"):
            assert search_row[field] == info_row[field], (
                f"{code} 字段 {field} 批量路径与单物料路径不一致："
                f"{search_row[field]!r} != {info_row[field]!r}"
            )


def test_search_without_warehouse_no_aggregation(client, monkeypatch):
    """不带仓库上下文：不做全仓聚合（0 次），stock 取全局 Material.stock。"""
    calls = {"count": 0}
    original = app_module.get_warehouse_stock_quantities

    def counting_wrapper(warehouse):
        calls["count"] += 1
        return original(warehouse)

    monkeypatch.setattr(app_module, "get_warehouse_stock_quantities", counting_wrapper)

    body = client.get("/api/material/search?kw=电线").get_json()
    assert len(body["data"]) == MATERIAL_COUNT
    assert calls["count"] == 0
    for i, row in enumerate(body["data"]):
        assert row["stock"] == 100 + i  # 全局口径不变


def test_build_material_locations_map():
    """预取函数边界：空列表返回空 dict；分批 IN 查询结果完整。"""
    with app_module.app.app_context():
        assert app_module.build_material_locations_map([]) == {}
        assert app_module.build_material_locations_map(None) == {}
        ids = [m.id for m in Material.query.all()]
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        full_map = app_module.build_material_locations_map(ids, wh_obj=wh_a)
        assert len(full_map) == MATERIAL_COUNT
        # 排序口径：数量降序、库位升序（与逐物料路径一致）
        first = full_map[ids[0]]
        assert [loc["location"] for loc in first] == ["货架A-00", "货架B-00"]
