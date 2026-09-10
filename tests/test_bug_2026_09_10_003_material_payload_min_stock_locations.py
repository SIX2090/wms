# -*- coding: utf-8 -*-
"""BUG-2026-09-10-003 回归：手机端查库存 payload 补 min_stock 与库位分布。

P1-①「库存充足/不足」徽标误导：Android 按 stock > min_stock 判断，但
api_material_payload 此前不下发 min_stock，恒按 0 比较退化为"大于 0 即充足"。
P1-②现场找货需要「货在哪个库位、各多少」：payload 新增 locations 数组
（开启库位管理时下发非零库位、按数量降序、有仓库上下文按仓库过滤）。
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
            code="M001", name="测试物料", category_id=1, unit_id=1,
            stock=100, min_stock=10, reorder_point=20,
        ))
        db.session.commit()
    test_client = app_module.app.test_client()
    response = test_client.post("/login", data={"username": "admin", "password": "admin"})
    assert response.status_code in (302, 303)
    return test_client


def test_payload_contains_real_min_stock_and_reorder_point(client):
    """徽标判断所需的 min_stock/reorder_point 必须真实下发，不再恒为 0。"""
    body = client.get("/api/material/info?code=M001").get_json()
    assert body["status"] == "success"
    data = body["data"]
    assert data["min_stock"] == 10
    assert data["reorder_point"] == 20
    assert data["stock"] == 100
    # 徽标语义可计算：stock(100) > min_stock(10) → 充足
    assert data["stock"] > data["min_stock"]


def test_locations_distribution_non_zero_and_ordered(client):
    """库位分布只含非零库位，按数量降序；location_code 保持"最多库位"语义。"""
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        db.session.add_all([
            LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                              location="货架B-01", quantity=20),
            LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                              location="货架C-09", quantity=0),
        ])
        db.session.commit()

    data = client.get("/api/material/info?code=M001").get_json()["data"]
    assert data["locations"] == [
        {"location": "货架A-03", "quantity": 50},
        {"location": "货架B-01", "quantity": 20},
    ]
    assert data["location_code"] == "货架A-03"  # 原语义不变（数量最多的库位）


def test_locations_filtered_by_warehouse_context(client):
    """带仓库上下文时库位分布只含该仓（与该仓账面 stock 口径一致，R2）。"""
    with app_module.app.app_context():
        material = Material.query.filter_by(code="M001").first()
        wh_a = Warehouse.query.filter_by(code="WHA").first()
        wh_b = Warehouse.query.filter_by(code="WHB").first()
        db.session.add_all([
            LocationInventory(material_id=material.id, warehouse_id=wh_a.id,
                              location="货架A-03", quantity=50),
            LocationInventory(material_id=material.id, warehouse_id=wh_b.id,
                              location="货架X-01", quantity=999),
        ])
        db.session.commit()

    data = client.get("/api/material/info?code=M001&warehouse=仓库A").get_json()["data"]
    assert data["locations"] == [{"location": "货架A-03", "quantity": 50}]
    # B 仓 999 不得串入 A 仓上下文
    assert all(loc["location"] != "货架X-01" for loc in data["locations"])


def test_locations_empty_when_location_management_disabled(client):
    with app_module.app.app_context():
        set_system_setting("location_management_enabled", "0")
    data = client.get("/api/material/info?code=M001").get_json()["data"]
    assert data["locations"] == []
    assert data["location_code"] == ""


def test_search_response_also_carries_new_fields(client):
    body = client.get("/api/material/search?kw=M001").get_json()
    assert body["status"] == "success"
    row = body["data"][0]
    assert row["min_stock"] == 10
    assert row["reorder_point"] == 20
    assert "locations" in row
