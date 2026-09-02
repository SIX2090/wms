# -*- coding: utf-8 -*-
"""INV-AUDIT-003-FIX-01 / BUG-2026-09-02-001 回归：Android 扫码盘点必须按仓库级账面库存。

背景：INV-AUDIT-003（已完成，commit 2b47d8e7）把手机端扫码盘点的账面库存
从全局 Material.stock 改为仓库级 get_warehouse_stock_quantities()，但只改了
app/routes/mobile.py（Web 手机端），遗漏了 app/routes/native_api.py 的
/api/stocktake（Android 原生端）。

BUG-2026-08-11-021 后续为 /api/stocktake 补了仓库必填与 InventoryCheckScan
的 warehouse 列，但没有改取数口径，于是：

    native_api.py: system_stock = parse_float_value(line.get('system_stock'),
                                                    material.stock or 0)

默认值仍是全局 Material.stock。而 Android 端 ScanViewModel.kt 显式传
system_stock = null，服务端必定落到该默认值 —— 多仓库下盘点差异按"全部仓库
合计"计算，盘盈盘亏全部算错，并据此生成错误的库存调整草稿。

覆盖（多仓库场景，A仓 60 / B仓 40 / 全局 100，数据本身自洽）：
T1. 盘点 B仓（该仓 40）实盘 38 → 账面应取 40、差异 -2；BUG 时取 100、差异 -62
T2. 盘点 A仓（该仓 60）实盘 60 → 无差异、不生成调整单；BUG 时差异 -40 并生成草稿
T3. 单仓库场景不受影响（get_warehouse_stock_quantities 的单仓 fallback 分支）
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
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


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material_with_warehouse_stock(code, global_stock, per_warehouse):
    """建物料并按仓库写入流水。

    global_stock     → Material.stock（全局账面，多仓合计）
    per_warehouse    → {warehouse_obj: quantity} 各仓库实际归属的流水数量
    """
    from app import Material, StockTransaction
    m = Material(code=code, name=f"物料{code}", stock=global_stock)
    db.session.add(m)
    db.session.commit()
    for wh, qty in per_warehouse.items():
        db.session.add(StockTransaction(
            material_id=m.id,
            transaction_type="in",
            quantity=qty,
            location=wh.name,
            warehouse_id=wh.id,
            created_at=datetime.now(),
        ))
    db.session.commit()
    return m


def _post_stocktake(client, headers, warehouse, material_code, actual_stock):
    payload = {
        "mode": "scan",
        "warehouse": warehouse,
        "lines": [{"material_code": material_code, "actual_stock": actual_stock}],
    }
    return client.post("/api/stocktake", json=payload, headers=headers)


def test_t1_stocktake_uses_warehouse_level_system_stock():
    """T1: 多仓库下盘点 B仓，账面必须取 B仓的 40，而不是全局的 100。"""
    from app import InventoryCheckScanItem
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    # 全局 100 = A仓 60 + B仓 40，数据自洽
    _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})

    client = _make_client()
    r = _post_stocktake(client, _bearer(client), "B仓", "M001", 38)
    assert r.status_code == 200, r.get_data(as_text=True)

    item = InventoryCheckScanItem.query.one()
    assert item.system_stock == 40.0, (
        f"盘点 B仓应取 B仓账面 40，实际取到 {item.system_stock}（疑似回退全局 Material.stock=100）"
    )
    assert item.difference == -2.0, f"差异应为 -2（38-40），实际 {item.difference}"


def test_t2_no_difference_generates_no_adjustment():
    """T2: 盘点 A仓（该仓 60）实盘 60 → 无差异，不应生成调整草稿。"""
    from app import AdjustmentOrder
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    _seed_material_with_warehouse_stock("M002", 100.0, {wh_a: 60.0, wh_b: 40.0})

    client = _make_client()
    r = _post_stocktake(client, _bearer(client), "A仓", "M002", 60)
    assert r.status_code == 200, r.get_data(as_text=True)

    drafts = AdjustmentOrder.query.filter_by(source_type="check_scan").all()
    assert not drafts, (
        f"A仓实盘与账面一致（60/60）不应产生调整单，实际生成 {len(drafts)} 张；"
        f"若取全局 100 会误判盘亏 -40"
    )


def test_t3_single_warehouse_fallback_unchanged():
    """T3: 单仓库场景回归保护——仍走 Material.stock 兜底分支。"""
    from app import InventoryCheckScanItem
    _reset_db()
    _seed_admin()
    wh = _seed_warehouse("SOLO", "唯一仓", is_default=True)
    # 单仓 fallback：只有流水无 warehouse_id 归属时，按 Material.stock 取值
    from app import Material, StockTransaction
    m = Material(code="M003", name="物料M003", stock=80.0)
    db.session.add(m)
    db.session.commit()
    db.session.add(StockTransaction(
        material_id=m.id, transaction_type="in", quantity=80.0,
        location="唯一仓", warehouse_id=wh.id, created_at=datetime.now(),
    ))
    db.session.commit()

    client = _make_client()
    r = _post_stocktake(client, _bearer(client), "唯一仓", "M003", 75)
    assert r.status_code == 200, r.get_data(as_text=True)

    item = InventoryCheckScanItem.query.one()
    assert item.system_stock == 80.0, f"单仓场景账面应为 80，实际 {item.system_stock}"
    assert item.difference == -5.0, f"单仓场景差异应为 -5，实际 {item.difference}"
