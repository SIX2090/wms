# -*- coding: utf-8 -*-
"""INV-BATCH-001-E / BUG-2026-09-04-005 回归：移动盘点强制选单 + 盘点单列表。

新契约（业务决策：所有盘点结果统一记录到一张 PC 盘点单上）：
- Android POST /api/stocktake 与 H5 POST /mobile/api/scan_submit（check 模式）
  必须携带并校验所选 PC 进行中盘点单（InventoryCheck id，status='pending'）；
- 缺省/不存在/非 pending/与盘点仓库不一致 → 400，不落任何 CS/草稿；
- 校验通过后明细统一 upsert 进所选批次，返回 batch_no/inventory_check_id；
- 新增盘点单列表 GET /api/stocktake/check_orders（native）与
  GET /mobile/api/check_orders（H5），可按仓库过滤（名称/编码）。

覆盖：
T1. native 缺 check_id → 400，无 CS 落库
T2. native 携带合法盘点单 → 200，挂批次、CS.check_id 写入、无 CS 级草稿
T3. native 仓库与盘点单不一致 → 400
T4. native check_id 不存在 / 已完结（completed）→ 400
T5. H5 scan_submit 对称场景（缺省 400 / 成功挂批次 / 仓库不一致 400）
T6. 盘点单列表接口：全量 pending、按仓库过滤、仅 pending 不含 completed
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


# BUG-2026-09-03-004(测试污染)：模块顶层常驻 app context 在模块结束后必须 pop
import pytest as _pytest  # noqa: E402


@_pytest.fixture(autouse=True, scope="module")
def _release_app_ctx_after_module():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


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
    """建物料并按仓库写入流水（global_stock = 各仓之和，数据自洽）。"""
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


def _seed_check_order(warehouse_name, check_no, status="pending"):
    from app import InventoryCheck
    check = InventoryCheck(check_no=check_no, warehouse=warehouse_name,
                           status=status)
    db.session.add(check)
    db.session.commit()
    return check


def _seed_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m1 = _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    return wh_a, wh_b, m1


def _post_stocktake(client, headers, warehouse, lines, check_id=None):
    payload = {"mode": "scan", "warehouse": warehouse, "lines": lines}
    if check_id is not None:
        payload["check_id"] = check_id
    return client.post("/api/stocktake", json=payload, headers=headers)


def _post_scan_submit(client, headers, warehouse, code, actual, check_id=None):
    payload = {"mode": "check", "code": code, "warehouse": warehouse,
               "actual_stock": actual}
    if check_id is not None:
        payload["check_id"] = check_id
    return client.post("/mobile/api/scan_submit", headers=headers, json=payload)


def test_t1_native_missing_check_id_rejected():
    """T1: native 缺 check_id → 400 且不落任何 CS。"""
    from app import InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    r = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r.status_code == 400, f"缺 check_id 应 400，实际 {r.status_code}"
    msg = (r.get_json().get("msg") or "") + (r.get_json().get("message") or "")
    assert "进行中的盘点单" in msg, f"提示应引导先选盘点单，实际：{msg}"
    assert InventoryCheckScan.query.count() == 0


def test_t2_native_valid_check_hooks_batch():
    """T2: native 携带合法盘点单 → 200 挂批次，无 CS 级草稿。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-001E-T2")

    r = _post_stocktake(client, h, "B仓",
                        [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert data["batch_no"] == "CK-001E-T2"
    assert data["inventory_check_id"] == batch.id

    scan = InventoryCheckScan.query.one()
    assert scan.check_id == batch.id
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0


def test_t3_native_warehouse_mismatch_rejected():
    """T3: native 仓库与盘点单不一致 → 400。"""
    from app import InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    batch_a = _seed_check_order("A仓", "CK-001E-T3")

    r = _post_stocktake(client, h, "B仓",
                        [{"material_code": "M001", "actual_stock": 38}], batch_a.id)
    assert r.status_code == 400, f"仓库不一致应 400，实际 {r.status_code}"
    msg = (r.get_json().get("msg") or "") + (r.get_json().get("message") or "")
    assert "不一致" in msg, f"提示应指出仓库不一致，实际：{msg}"
    assert InventoryCheckScan.query.count() == 0


def test_t4_native_invalid_or_completed_check_rejected():
    """T4: native check_id 不存在 / 已完结 → 400。"""
    from app import InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    done = _seed_check_order("B仓", "CK-001E-DONE", status="completed")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], 999999)
    assert r1.status_code == 400, f"不存在盘点单应 400，实际 {r1.status_code}"
    r2 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], done.id)
    assert r2.status_code == 400, f"已完结盘点单应 400，实际 {r2.status_code}"
    assert InventoryCheckScan.query.count() == 0


def test_t5_h5_scan_submit_symmetric():
    """T5: H5 scan_submit 对称强制（缺省 400 / 仓库不一致 400 / 合法成功挂批次）。"""
    from app import InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-001E-T5")

    r1 = _post_scan_submit(client, h, "B仓", "M001", 38)
    assert r1.status_code == 400, f"H5 缺 check_id 应 400，实际 {r1.status_code}"

    r2 = _post_scan_submit(client, h, "A仓", "M001", 58, check_id=batch.id)
    assert r2.status_code == 400, f"H5 仓库不一致应 400，实际 {r2.status_code}"

    r3 = _post_scan_submit(client, h, "B仓", "M001", 38, check_id=batch.id)
    assert r3.status_code == 200, r3.get_data(as_text=True)
    assert r3.get_json()["data"]["batch_no"] == "CK-001E-T5"
    assert InventoryCheckScan.query.one().check_id == batch.id


def test_t6_check_orders_listing():
    """T6: 盘点单列表接口：全量 / 按仓库过滤 / 仅 pending。"""
    _seed_scene()
    client = _make_client()
    h = _bearer(client)
    _seed_check_order("A仓", "CK-001E-LA")
    _seed_check_order("B仓", "CK-001E-LB1")
    _seed_check_order("B仓", "CK-001E-LB2")
    _seed_check_order("B仓", "CK-001E-LDONE", status="completed")

    r = client.get("/api/stocktake/check_orders", headers=h)
    assert r.status_code == 200
    orders = r.get_json()["data"]["orders"]
    codes = {o["check_no"] for o in orders}
    assert codes == {"CK-001E-LA", "CK-001E-LB1", "CK-001E-LB2"}, (
        f"列表应只含 pending 盘点单，实际：{codes}"
    )
    for o in orders:
        assert {"id", "check_no", "warehouse", "date", "remark",
                "frozen_at", "item_count"} <= set(o.keys()), o

    # 按仓库过滤（编码与名称都支持）
    r2 = client.get("/api/stocktake/check_orders?warehouse_code=WB", headers=h)
    assert r2.status_code == 200
    codes2 = {o["check_no"] for o in r2.get_json()["data"]["orders"]}
    assert codes2 == {"CK-001E-LB1", "CK-001E-LB2"}
    r3 = client.get("/api/stocktake/check_orders?warehouse=B仓", headers=h)
    assert {o["check_no"] for o in r3.get_json()["data"]["orders"]} == codes2

    # H5 列表接口同信封
    r4 = client.get("/mobile/api/check_orders?warehouse=B仓", headers=h)
    assert r4.status_code == 200
    assert {o["check_no"] for o in r4.get_json()["data"]["orders"]} == codes2
