# -*- coding: utf-8 -*-
"""INV-BATCH-001-C 回归：扫码盘点挂钩批次（多人协作盘点）。

背景：此前手机扫码盘点（mobile.py scan_submit / native_api.py
/api/stocktake）与 PC 盘点单（批次）完全割裂——多人各扫各的、互不
知晓，批次内同一物料可被多人重复扫码且无法判责；扫码差异独立生成
调整草稿，与批次 complete 生成的草稿口径分裂。

能力：扫码提交时检测同仓库是否存在 status='pending' 的 PC 盘点单
（活动批次）：
- 有批次：CS 单挂 check_id（留痕），**不再独立生成调整草稿**；批次
  明细行级 upsert——已有行未盘（counted_at 空）更新实盘与行级归属、
  账面基准保留（该行首次录入时点）；已有行已盘（counted_at 非空）
  拒绝并提示已盘信息（防止两人重复盘同一物料互相覆盖）；无行插入
  新行，system_stock 取扫码时点仓库级账面（即时口径，与独立扫码
  同口径自洽：调整量=实盘−盘点时点账面，不受期间出入库影响）。
- 无批次：维持独立单模式（立即生成调整草稿 + INV-GUARD-001 护栏），
  向后兼容。

口径说明（实物守恒推导）：调整量 = 实盘 − Δ(t0→ti) − F = 实盘 − 该行
盘点时点账面。PC 表格行用冻结口径（P2-B，停机语义），扫码行用即时
口径（不停机语义），批次内各行基准各自自洽，complete 统一按
actual − system_stock 生成调整单。

覆盖（多仓库场景，A仓 M001=60/M002=30，B仓 M001=40/M002=20）：
T1. 无批次 → 独立模式（check_id 空 + 立即生成草稿），兼容锁定
T2. 有批次 → 挂批次：check_id 写入、不生成 CS 级草稿、明细新增行
    （扫码时点账面 + 行级归属）、响应提示批次号
T3. 挂批次扫已在明细的未盘行 → 更新实盘与归属，账面基准保留
T4. 重复扫码同物料（已盘行）→ 拒绝，提示含"已由"，CS 单不增
T5. 批次冻结后期间出库 → 新行账面取扫码时点当前值（即时口径）
T6. 批次 complete → 按各行口径生成调整草稿，CS 单无独立草稿
T7. B仓扫码不挂 A仓批次（仓库隔离）→ 独立模式
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


# BUG-2026-09-03-004(测试污染)：模块顶层常驻 app context 在模块结束后必须 pop，
# 否则残留 ctx 会使后续模块的请求内事务/系统设置读取异常（顺序依赖假失败）。
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
    return u


def _bearer(client):
    r = client.post("/api/login", json={"username": "admin", "password": "admin"})
    assert r.status_code == 200, r.get_data(as_text=True)
    return {"Authorization": f"Bearer {r.get_json()['data']['token']}"}


def _login_web(client):
    r = client.post("/login", data={"username": "admin", "password": "admin"})
    assert r.status_code in (302, 303), f"Web 登录失败：{r.status_code}"


def _seed_warehouse(code, name, is_default=False):
    from app import Warehouse
    w = Warehouse(code=code, name=name, status="active", is_default=is_default)
    db.session.add(w)
    db.session.commit()
    return w


def _seed_material_with_warehouse_stock(code, global_stock, per_warehouse):
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


def _seed_scene():
    _reset_db()
    admin = _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m1 = _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    m2 = _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return admin, wh_a, wh_b, m1, m2


def _seed_batch(admin, warehouse_name, check_no, items=None, frozen=True):
    """造一个活动批次（PC 盘点单，pending）。items=[(material, sys, actual)]。"""
    from app import InventoryCheck, InventoryCheckItem
    check = InventoryCheck(
        check_no=check_no, warehouse=warehouse_name, status="pending",
        operator_id=admin.id,
        frozen_at=datetime.now() if frozen else None,
    )
    db.session.add(check)
    db.session.flush()
    for material, sys_stock, actual in (items or []):
        db.session.add(InventoryCheckItem(
            inventory_check_id=check.id,
            material_id=material.id,
            system_stock=sys_stock,
            actual_stock=actual,
            difference=round(actual - sys_stock, 2),
        ))
    db.session.commit()
    return check


def _write_out_flow(material, warehouse, qty):
    from app import StockTransaction
    db.session.add(StockTransaction(
        material_id=material.id,
        transaction_type="out",
        quantity=-abs(qty),
        location=warehouse.name,
        warehouse_id=warehouse.id,
        created_at=datetime.now(),
    ))
    db.session.commit()


def _post_scan_submit(client, headers, code, warehouse, actual):
    return client.post("/mobile/api/scan_submit", headers=headers, json={
        "mode": "check", "code": code, "warehouse": warehouse,
        "actual_stock": actual,
    })


def _post_stocktake(client, headers, warehouse, lines):
    return client.post("/api/stocktake", json={
        "mode": "scan", "warehouse": warehouse, "lines": lines,
    }, headers=headers)


def _batch_item(batch, material_id):
    from app import InventoryCheckItem
    return InventoryCheckItem.query.filter_by(
        inventory_check_id=batch.id, material_id=material_id).first()


def test_t1_no_batch_keeps_standalone_mode():
    """T1: 无活动批次 → 独立单模式（check_id 空 + 立即生成草稿）。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_scene()
    client = _make_client()
    h = _bearer(client)

    r = _post_scan_submit(client, h, "M001", "A仓", 58)
    assert r.status_code == 200, r.get_data(as_text=True)
    scan = InventoryCheckScan.query.one()
    assert scan.check_id is None, "无批次时不得挂钩"
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1, (
        "独立模式必须立即生成调整草稿（向后兼容）"
    )


def test_t2_scan_hooks_into_batch():
    """T2: 有批次 → 挂 check_id、不生成 CS 级草稿、批次明细新增行带归属。"""
    from app import AdjustmentOrder, InventoryCheckScan
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    batch = _seed_batch(admin, "A仓", "CK-B1")
    client = _make_client()
    h = _bearer(client)

    r = _post_scan_submit(client, h, "M001", "A仓", 58)
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert "CK-B1" in (body.get("msg") or ""), f"响应应提示已挂批次，实际：{body}"

    scan = InventoryCheckScan.query.one()
    assert scan.check_id == batch.id, "扫码盘点单必须挂钩批次"

    # 挂批次不得生成 CS 级调整草稿（草稿由批次 complete 统一生成）
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0, (
        "挂批次的扫码不得独立生成调整草稿，否则与批次 complete 重复"
    )

    # 批次明细新增行：扫码时点账面（60）+ 行级归属
    row = _batch_item(batch, m1.id)
    assert row is not None, "批次明细必须新增扫码行"
    assert row.system_stock == 60.0, f"扫码行账面取扫码时点当前值 60，实际 {row.system_stock}"
    assert row.actual_stock == 58.0
    assert row.difference == -2.0
    assert row.counted_by == admin.id, "必须写行级盘点人"
    assert row.counted_at is not None, "必须写行级盘点时间"


def test_t3_scan_fills_uncounted_batch_row():
    """T3: 挂批次扫已在明细的未盘行 → 更新实盘与归属，账面基准保留。"""
    from app import InventoryCheckScan
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    # PC 已填 M001 行（冻结账面 60、实盘 58、未盘归属空）
    batch = _seed_batch(admin, "A仓", "CK-B1", items=[(m1, 60.0, 58.0)])
    client = _make_client()
    h = _bearer(client)

    r = _post_scan_submit(client, h, "M001", "A仓", 57)
    assert r.status_code == 200, r.get_data(as_text=True)

    db.session.expire_all()
    row = _batch_item(batch, m1.id)
    assert row.actual_stock == 57.0, "扫码实盘应覆盖该行"
    assert row.system_stock == 60.0, "已有行账面基准必须保留（首次录入时点）"
    assert row.difference == -3.0
    assert row.counted_by == admin.id and row.counted_at is not None
    # 明细行不重复（upsert 而非新增）
    from app import InventoryCheckItem
    assert InventoryCheckItem.query.filter_by(
        inventory_check_id=batch.id, material_id=m1.id).count() == 1


def test_t4_duplicate_scan_rejected():
    """T4: 重复扫码同物料（行已盘）→ 拒绝并提示已盘信息，CS 单不增。"""
    from app import InventoryCheckScan
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    batch = _seed_batch(admin, "A仓", "CK-B1")
    client = _make_client()
    h = _bearer(client)

    r1 = _post_scan_submit(client, h, "M001", "A仓", 58)
    assert r1.status_code == 200
    r2 = _post_stocktake(client, h, "A仓", [{"material_code": "M001", "actual_stock": 57}])
    assert r2.status_code == 400, (
        f"重复扫码同物料必须拒绝（防两人互覆），实际返回 {r2.status_code}"
    )
    msg = (r2.get_json().get("msg") or "") + (r2.get_json().get("message") or "")
    assert "已由" in msg, f"提示应含已盘信息，实际：{msg}"
    assert "CK-B1" in msg, f"提示应含批次号，实际：{msg}"
    assert InventoryCheckScan.query.count() == 1, "被拒绝的扫码不得落 CS 单"


def test_t5_scan_row_uses_current_book_at_scan_time():
    """T5: 批次冻结后期间出库 → 新行账面取扫码时点当前值（即时口径）。

    实物守恒：调整量 = 实盘 − Δ(t0→ti) − F = 实盘 − 扫码时点账面。
    期间出库 10 后账面 60→50，扫码实盘 49 → 行差异应为 -1（而非 −11）。
    """
    from app import InventoryCheckScan
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    batch = _seed_batch(admin, "A仓", "CK-B1")
    _write_out_flow(m1, wh_a, 10)  # 期间出库：账面 60 → 50
    client = _make_client()
    h = _bearer(client)

    r = _post_scan_submit(client, h, "M001", "A仓", 49)
    assert r.status_code == 200, r.get_data(as_text=True)

    row = _batch_item(batch, m1.id)
    assert row.system_stock == 50.0, (
        f"扫码行账面必须取扫码时点当前值 50（含期间流水），实际 {row.system_stock}"
    )
    assert row.difference == -1.0, "即时口径下差异 = 实盘 − 扫码时点账面 = -1"


def test_t6_batch_complete_uses_row_baselines():
    """T6: 批次 complete → 按各行口径生成调整草稿；CS 单无独立草稿。"""
    from app import (AdjustmentOrder, AdjustmentOrderItem, InventoryCheckScan)
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    # PC 行 M001（冻结 60，实盘 58 → 差异 -2）
    batch = _seed_batch(admin, "A仓", "CK-B1", items=[(m1, 60.0, 58.0)])
    client = _make_client()
    h = _bearer(client)
    # 扫码行 M002（即时账面 30，实盘 29 → 差异 -1）
    r = _post_scan_submit(client, h, "M002", "A仓", 29)
    assert r.status_code == 200

    _login_web(client)
    r2 = client.post(f"/check/{batch.id}/complete")
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json().get("status") == "success"

    order = AdjustmentOrder.query.filter_by(
        source_type="check", source_id=batch.id).one()
    items = {i.material_id: i.quantity for i in
             AdjustmentOrderItem.query.filter_by(adjustment_order_id=order.id).all()}
    assert items[m1.id] == -2.0, f"PC 行按冻结口径 -2，实际 {items.get(m1.id)}"
    assert items[m2.id] == -1.0, f"扫码行按即时口径 -1，实际 {items.get(m2.id)}"
    # CS 单全程无独立草稿
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0
    assert InventoryCheckScan.query.one().check_id == batch.id


def test_t7_other_warehouse_scan_stays_standalone():
    """T7: B仓扫码不挂 A仓批次（仓库隔离）→ 独立模式。"""
    from app import AdjustmentOrder, InventoryCheckScan
    admin, wh_a, wh_b, m1, m2 = _seed_scene()
    _seed_batch(admin, "A仓", "CK-B1")
    client = _make_client()
    h = _bearer(client)

    r = _post_scan_submit(client, h, "M001", "B仓", 38)
    assert r.status_code == 200, r.get_data(as_text=True)
    scan = InventoryCheckScan.query.one()
    assert scan.check_id is None, "不同仓库的扫码不得挂钩"
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1, (
        "未挂批次的扫码维持独立模式（立即生成草稿）"
    )
