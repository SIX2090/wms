# -*- coding: utf-8 -*-
"""BUG-2026-09-12-003 回归：手机端库存列表接口补齐 brand / locations。

背景：BUG-2026-09-10-003 给扫码路径（mobile_material_payload）补了
min_stock/reorder_point/locations，但**列表模式**（AI-MOB-STOCK-F01，
2026-08-09 引入，早于该修复）当时未被覆盖，响应字典漏下发 brand 与
locations。后果：同一物料扫码能看到库位、列表里看不到，"查得到却看不见"。

本测试锁定修复后的契约，并按下述口径逐条验证（R2 要求三项缺一不算完成）：
1. 多仓库隔离：A 仓库上下文不得串入 B 仓库库位。
2. 历史脏数据兼容：warehouse_id 为 NULL 但 location 等于本仓名/编码的历史行
   必须仍能查出（R2 第 2 条）。
3. 字段对齐：列表与扫码路径的 locations 语义一致（非零、按库位名排序）。

另附批量查询防退化断言：本页物料的库位查询必须是 1 条 SQL（禁止 N+1）。
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
        db.session.add(Material(
            code="M001", name="测试物料", brand="测试品牌", category_id=1, unit_id=1,
            stock=100, min_stock=10, reorder_point=20,
        ))
        db.session.commit()
    tc = app_module.app.test_client()
    resp = tc.post("/login", data={"username": "admin", "password": "admin"})
    assert resp.status_code in (302, 303)
    return tc


def _query(client, warehouse="WHA", **extra):
    qs = "warehouse=%s" % warehouse
    for k, v in extra.items():
        qs += "&%s=%s" % (k, v)
    body = client.get("/api/mobile/stock/query?" + qs).get_json()
    assert body["status"] == "success"
    return body["data"]


def test_list_item_carries_brand_and_locations(client):
    """列表行必须下发 brand 与 locations（此前两者都缺）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架B-01", quantity=20),
        ])
        db.session.commit()

    item = _query(client)["items"][0]
    assert item["brand"] == "测试品牌"
    assert item["locations"] == [
        {"location": "货架A-03", "quantity": 50.0},
        {"location": "货架B-01", "quantity": 20.0},
    ]


def test_locations_exclude_zero_and_match_lookup_semantics(client):
    """零库存库位不下发，且与扫码路径口径一致（非零）。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="空库位", quantity=0),
        ])
        db.session.commit()

    item = _query(client)["items"][0]
    assert [l["location"] for l in item["locations"]] == ["货架A-03"]


def test_locations_warehouse_isolation(client):
    """R2-1 多仓库隔离：B 仓库库位不得串入 A 仓库查询结果。"""
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

    item_a = _query(client, "WHA")["items"][0]
    assert [l["location"] for l in item_a["locations"]] == ["货架A-03"]

    item_b = _query(client, "WHB")["items"][0]
    assert [l["location"] for l in item_b["locations"]] == ["货架X-01"]


def test_locations_legacy_null_warehouse_compat(client):
    """R2-2 历史脏数据兼容：warehouse_id 为 NULL、location 为本仓名的行仍可查出。"""
    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        db.session.add_all([
            # 历史行：未归属仓库，location 写的是仓库名
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="仓库A", quantity=7),
            # 历史行：未归属仓库，location 写的是另一个仓库名 —— 不得串入
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="仓库B", quantity=888),
        ])
        db.session.commit()

    item = _query(client, "WHA")["items"][0]
    locs = {l["location"]: l["quantity"] for l in item["locations"]}
    assert locs.get("仓库A") == 7.0
    assert "仓库B" not in locs


def test_locations_empty_when_management_disabled(client):
    """关闭库位管理时 locations 为空列表，不报错。"""
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
    assert _query(client)["items"][0]["locations"] == []


def test_locations_batch_query_no_n_plus_1(client):
    """防退化：本页物料的库位查询必须是固定条数批量 SQL（禁止逐条 N+1）。

    本页 20 条物料时，location_inventory 上的 SQL 总数应远小于 20：
    ① 1 条来自既有仓库级库存汇总（get_warehouse_stock_quantities）；
    ② 1 条来自本次新增的库位分布批量 IN 查询。
    若实现退化为逐条查询，这里会暴涨到 20+ 条。
    """
    from sqlalchemy import event

    with app_module.app.app_context():
        for i in range(2, 21):
            db.session.add(Material(code="M%03d" % i, name="物料%d" % i,
                                    category_id=1, unit_id=1, stock=1))
        db.session.commit()
        mats = Material.query.all()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        for m in mats:
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
        _query(client, "WHA", page=1, page_size=20)
    finally:
        event.remove(engine, "before_cursor_execute", _before)

    # 独立于物料条数的固定开销；一旦出现 N+1 会立即超过 5
    assert counted["loc"] <= 5, (
        "本页 20 条物料的 location_inventory SQL 应为常量级，实际 %d 条（疑似 N+1）"
        % counted["loc"]
    )


def test_locations_page2_also_correct(client):
    """翻页后第 2 页同样带 locations（防止只在首页生效）。"""
    with app_module.app.app_context():
        for i in range(2, 46):
            db.session.add(Material(code="M%03d" % i, name="物料%d" % i,
                                    category_id=1, unit_id=1, stock=1))
        db.session.commit()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        m = Material.query.filter_by(code="M001").first()
        db.session.add(LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                                         location="货架A-03", quantity=50))
        db.session.commit()

    data = _query(client, "WHA", page=2, page_size=20)
    assert data["page"] == 2
    for item in data["items"]:
        assert "locations" in item
        assert "brand" in item


def test_build_locations_map_backward_compatible(client):
    """改变共用函数 build_material_locations_map 的向后兼容性。

    新增 legacy_location_names 为可选参数：
    - 不传：保持仅按 warehouse_id 精确匹配（search/all 两处调用点行为不变）。
    - 传：额外纳入 warehouse_id 为 NULL 的历史行。
    """
    from app import build_material_locations_map

    with app_module.app.app_context():
        m = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=m.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=m.id, warehouse_id=None,
                              location="仓库A", quantity=20),
        ])
        db.session.commit()

        # 默认行为：仅精确匹配，不含历史行
        default_map = build_material_locations_map([m.id], wh_obj=wh_a)
        assert default_map == {m.id: [{"location": "货架A-03", "quantity": 50.0}]}

        # 显式传 legacy_location_names：历史行被纳入
        legacy_map = build_material_locations_map(
            [m.id], wh_obj=wh_a, legacy_location_names=["仓库A", "WHA"])
        locs = {x["location"]: x["quantity"] for x in legacy_map[m.id]}
        assert locs == {"货架A-03": 50.0, "仓库A": 20.0}

        # 汇总 = 明细（R2-3）：历史行纳入后与 get_warehouse_stock_quantities 一致
        from app import get_warehouse_stock_quantities
        summary = get_warehouse_stock_quantities(wh_a).get(m.id)
        assert summary == sum(x["quantity"] for x in legacy_map[m.id])
