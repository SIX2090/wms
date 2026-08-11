# -*- coding: utf-8 -*-
"""BUG-2026-08-11-021 回归：扫码盘点必须有盘点仓库。

背景：Android/原生 /api/stocktake 提交扫码盘点时，后端完全忽略
payload 中的 warehouse 字段，InventoryCheckScan 模型也没有 warehouse 列，
导致盘点单及其自动生成的库存调整草稿都没有仓库，违反 AGENTS.md
仓库必填规则（盘点单据仓库必填，未选择时自动带入默认仓库，
无默认仓库则拒绝保存）。

覆盖：
T1. 未填仓库且未配置默认仓库 → 400 并提示选择仓库
T2. 未填仓库但配置了默认仓库 → 自动带入默认仓库并落库到盘点单与调整草稿
T3. 显式传仓库 → 盘点单与调整草稿均使用该仓库
T4. inventory_check_scan 表必须具备 warehouse 列（模型/建表）
"""
from __future__ import annotations

import os
import sys
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

_ctx = app_module.app.app_context()
_ctx.push()


def _reset_db():
    db.drop_all()
    db.create_all()


def _make_client():
    return app_module.app.test_client()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()


def _bearer(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _seed_material(code="M001", stock=10.0):
    from app import Material
    m = Material(code=code, name=f"物料{code}", stock=stock)
    db.session.add(m)
    db.session.commit()
    return m


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _post_stocktake(client, headers, warehouse=None):
    payload = {"mode": "scan", "lines": [{"material_code": "M001", "actual_stock": 8}]}
    if warehouse:
        payload["warehouse"] = warehouse
    return client.post("/api/stocktake", json=payload, headers=headers)


def test_t1_reject_when_no_warehouse_and_no_default():
    """T1: 未填仓库且无默认仓库时必须拒绝保存。"""
    _reset_db()
    _seed_admin()
    _seed_material()
    client = _make_client()
    r = _post_stocktake(client, _bearer(client))
    assert r.status_code == 400, r.get_data(as_text=True)
    assert "仓库" in r.get_json()["message"]


def test_t2_fallback_to_default_warehouse():
    """T2: 未填仓库时自动带入默认仓库，并写入盘点单与调整草稿。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _reset_db()
    _seed_admin()
    _seed_material()
    _seed_warehouse("DEF", "默认仓", is_default=True)
    client = _make_client()
    r = _post_stocktake(client, _bearer(client))
    assert r.status_code == 200, r.get_data(as_text=True)
    check = InventoryCheckScan.query.one()
    assert check.warehouse == "默认仓"
    drafts = AdjustmentOrder.query.filter_by(source_type="check_scan", source_id=check.id).all()
    assert drafts, "盘点差异应生成调整草稿"
    assert all(d.warehouse == "默认仓" for d in drafts)


def test_t3_explicit_warehouse_persisted():
    """T3: 显式传入的仓库必须落库到盘点单与调整草稿。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _reset_db()
    _seed_admin()
    _seed_material()
    _seed_warehouse("WA", "A仓")
    client = _make_client()
    r = _post_stocktake(client, _bearer(client), warehouse="A仓")
    assert r.status_code == 200, r.get_data(as_text=True)
    check = InventoryCheckScan.query.one()
    assert check.warehouse == "A仓"
    drafts = AdjustmentOrder.query.filter_by(source_type="check_scan", source_id=check.id).all()
    assert drafts and all(d.warehouse == "A仓" for d in drafts)


def test_t4_inventory_check_scan_has_warehouse_column():
    """T4: inventory_check_scan 表必须具备 warehouse 列。"""
    _reset_db()
    cols = [c[1] for c in db.session.execute(
        db.text("PRAGMA table_info(inventory_check_scan)")).fetchall()]
    assert "warehouse" in cols
