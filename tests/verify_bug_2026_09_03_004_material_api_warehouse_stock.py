# -*- coding: utf-8 -*-
"""BUG-2026-09-03-004 回归：/api/material/info|search 支持可选 warehouse 仓库级账面。

修复前：api_material_payload 的 stock 固定返回全局 Material.stock。Android
原生扫码/识别物料卡用 /api/material/info|search 拉取物料后展示"库存数量"
并按 stock 判"库存充足/不足"——多仓库下把 A+B 全仓合计当成本仓账面，
出库/盘点前会误判（A 仓只剩 5 却显示全局 100 → 误标"库存充足"）。

修复后：info/search 接受可选 warehouse（仓库名或编码）参数，命中时
stock 取该仓 get_warehouse_stock_quantities；未传或仓库无效回退全局展示，
不影响 Web 物料档案（/api/material/all 保持全局总库存口径）。

覆盖：
T1. /api/material/info?code=M001&warehouse=A仓 → stock=10（全局 100）
T2. /api/material/info?code=M001（不带仓库）→ stock=100 兼容
T3. /api/material/search?keyword=M001&warehouse=WA（编码别名）→ stock=10
T4. /api/material/all 保持全局口径（不传 warehouse，stock=100）
T5. 无效仓库 → 回退全局不报错
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

from werkzeug.security import generate_password_hash  # noqa: E402

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_admin():
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _seed_warehouse(code, name):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active")
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material(code="M001", global_stock=100.0):
    from app import Material, Unit
    unit = Unit.query.first()
    if not unit:
        unit = Unit(code="U1", name="个")
        db.session.add(unit)
        db.session.commit()
    m = Material(code=code, name=f"物料{code}", stock=global_stock, price=5, unit=unit)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_txn_stock(material, warehouse, qty):
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id, transaction_type="in", quantity=qty,
        location=warehouse.name, warehouse_id=warehouse.id, created_at=datetime.now()))
    db.session.commit()


@pytest.fixture()
def client():
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
        m = _seed_material("M001", 100.0)
        wa = _seed_warehouse("WA", "A仓")
        wb = _seed_warehouse("WB", "B仓")
        _seed_txn_stock(m, wa, 10)
        _seed_txn_stock(m, wb, 40)
    c = app_module.app.test_client()
    _login_web(c)
    yield c


def test_t1_info_with_warehouse_returns_warehouse_stock(client):
    r = client.get("/api/material/info?code=M001&warehouse=A仓")
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json()["data"]["stock"] == 10.0, "带仓库必须返回 A 仓账面 10，而非全局 100"


def test_t2_info_without_warehouse_keeps_global(client):
    r = client.get("/api/material/info?code=M001")
    assert r.status_code == 200
    assert r.get_json()["data"]["stock"] == 100.0, "未带仓库保持全局展示（兼容）"


def test_t3_search_with_warehouse_code_alias(client):
    r = client.get("/api/material/search?keyword=M001&warehouse=WA")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data and data[0]["stock"] == 10.0, "search 带仓库编码应返回 A 仓账面"


def test_t4_all_keeps_global_total(client):
    r = client.get("/api/material/all")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data and data[0]["stock"] == 100.0, "material/all 为总库存列表，保持全局口径"


def test_t5_invalid_warehouse_falls_back(client):
    r = client.get("/api/material/info?code=M001&warehouse=不存在的仓")
    assert r.status_code == 200
    assert r.get_json()["data"]["stock"] == 100.0, "无效仓库应回退全局，不报错"
