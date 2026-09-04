# -*- coding: utf-8 -*-
"""INV-REVERT-001 / BUG-2026-09-02-003（INV-BATCH-001-E 重构版）回归：扫码盘点作废回退。

背景：INV-BATCH-001-E 强制选单后，扫码盘点（mobile scan_submit /
native /api/stocktake）必须先选 PC 进行中盘点单并把差异 upsert 进批次，
CS 不再独立生成调整草稿。作废（_void_check_scan）相应升级（BUG-2026-09-04-005）：
- 批次已完成 → 拒绝作废（差异已被 PC 采纳生成调整单，提示先反提交）；
- 批次仍 pending：本 CS 新建的批次行（reason=='手机扫码盘点' 且
  counted_by==本 CS 操作人）删除，解禁同物料重盘；PC 预置行被本 CS 补盘
  （reason 非扫码标记且 counted_by==本 CS 操作人）重置回"待盘"
  （actual=system、difference=0、counted_by/counted_at=NULL）；
- counted_by 已被他人改写的行不动。

覆盖（多仓库场景，A仓 60 / B仓 40，数据自洽）：
T1. 有差异扫码进空批次 → 作废 → 批次行删除、CS 置 void、审计留痕
T2. 作废后同批次同物料可重新扫码
T3. 批次已完成 → 作废拒绝（提示含批次号与反提交指引）
T4. 重复作废（已 void）→ 拒绝
T5. 无差异扫码（账实一致）→ 作废成功，批次行同步删除
T6. Android 端点 /api/stocktake/void 按 check_no 作废成功；不存在单号 404
T7. Web 手机端 scan_submit 响应含 int check_id（前端撤销按钮依赖）
T8. PC 预置未盘行被手机补盘后作废 → 行重置回"待盘"而非删除（保护 PC 行）
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


def _seed_check_order(warehouse_name, check_no, items=None):
    """预置进行中盘点单；items=[(material, sys, actual)] 可含 PC 预置行。"""
    from app import InventoryCheck, InventoryCheckItem
    check = InventoryCheck(check_no=check_no, warehouse=warehouse_name,
                           status="pending")
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


def _seed_two_warehouse_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return wh_a, wh_b


def _post_stocktake(client, headers, warehouse, lines, check_id):
    payload = {"mode": "scan", "warehouse": warehouse, "lines": lines,
               "check_id": check_id}
    return client.post("/api/stocktake", json=payload, headers=headers)


def _post_scan_submit(client, headers, warehouse, code, actual, check_id):
    return client.post("/mobile/api/scan_submit", headers=headers, json={
        "mode": "check", "code": code, "warehouse": warehouse,
        "actual_stock": actual, "check_id": check_id,
    })


def _batch_rows(batch_id):
    from app import InventoryCheckItem
    return InventoryCheckItem.query.filter_by(inventory_check_id=batch_id).all()


def test_t1_void_deletes_scan_rows_and_marks_void():
    """T1: 空批次扫码作废 → 批次行删除、CS 置 void、审计留痕。"""
    from app import InventoryCheckItem, InventoryCheckScan, OperationLog
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R1")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    check = InventoryCheckScan.query.one()
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 1

    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json().get("status") == "success"

    # 批次行必须随作废删除——否则脏行残留导致同物料无法重盘/批次完成出脏草稿
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 0, (
        "作废必须回退本 CS 写入的批次行"
    )
    assert InventoryCheckScan.query.get(check.id).status == "void"

    logs = OperationLog.query.filter_by(
        target_type="inventory_check_scan", target_id=check.id).all()
    assert any("作废" in (log.operation_type or "") for log in logs), (
        "作废是审计敏感操作，必须留操作日志（含 Bearer 请求路径）"
    )


def test_t2_restocktake_after_void_allowed():
    """T2: 作废后同批次同物料可重新扫码。"""
    from app import InventoryCheckItem, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R2")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    # 行已删 → 不再被"已盘"拦截，可重扫
    r3 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 39}], batch.id)
    assert r3.status_code == 200, (
        f"作废后重新盘点应放行，实际返回 {r3.status_code}：{r3.get_data(as_text=True)}"
    )
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 1
    assert InventoryCheckScan.query.count() == 2


def test_t3_completed_batch_blocks_void():
    """T3: 批次已完成 → 拒绝作废（差异已被 PC 采纳成调整单）。"""
    from app import InventoryCheckItem, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R3")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()

    _login_web(client)
    rc = client.post(f"/check/{batch.id}/complete")
    assert rc.status_code == 200, rc.get_data(as_text=True)
    # 换回 Bearer 作废
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 400, (
        f"批次已完成时作废应被拒绝，实际 {r2.status_code}"
    )
    msg = (r2.get_json().get("msg") or "") + (r2.get_json().get("message") or "")
    assert "CK-R3" in msg, f"提示应包含批次号，实际：{msg}"
    assert InventoryCheckScan.query.get(check.id).status == "completed"
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 1


def test_t4_double_void_rejected():
    """T4: 重复作废（已 void）→ 拒绝。"""
    from app import InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R4")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    r3 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r3.status_code == 400, f"已作废单据不得重复作废，实际返回 {r3.status_code}"
    assert InventoryCheckScan.query.get(check.id).status == "void"


def test_t5_void_without_difference():
    """T5: 无差异扫码 → 作废成功，批次行同步删除。"""
    from app import InventoryCheckItem, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R5")

    # B仓 M001 账面 40，实盘 40 → 无差异仍按扫码留痕落批次行
    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 40}], batch.id)
    assert r1.status_code == 200
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 1
    check = InventoryCheckScan.query.one()

    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert InventoryCheckScan.query.get(check.id).status == "void"
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 0


def test_t6_android_void_endpoint():
    """T6: Android 端点 /api/stocktake/void 按 check_no 作废；不存在单号 404。"""
    from app import InventoryCheckItem, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R6")

    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200
    check_no = r1.get_json()["data"]["check_no"]
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 1

    r2 = client.post("/api/stocktake/void", json={"check_no": check_no}, headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json().get("status") == "success"
    check = InventoryCheckScan.query.filter_by(check_no=check_no).one()
    assert check.status == "void"
    assert InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).count() == 0

    r3 = client.post("/api/stocktake/void", json={"check_no": "CS999999"}, headers=h)
    assert r3.status_code == 404, f"作废不存在的盘点单应 404，实际返回 {r3.status_code}"


def test_t7_scan_submit_returns_check_id():
    """T7: Web 手机端 scan_submit 响应 data 含 int check_id（撤销按钮依赖）。"""
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)
    batch = _seed_check_order("B仓", "CK-R7")

    r = _post_scan_submit(client, h, "B仓", "M001", 38, batch.id)
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert isinstance(data.get("check_id"), int), (
        f"scan_submit 响应应含 int 型 check_id 供前端撤销，实际：{data}"
    )
    assert data.get("inventory_check_id") == batch.id


def test_t8_void_resets_pc_preseeded_row_instead_of_delete():
    """T8: PC 预置未盘行被手机补盘后作废 → 行重置回"待盘"而非删除（保护 PC 行）。"""
    from app import InventoryCheckItem, InventoryCheckScan
    _reset_db()
    from werkzeug.security import generate_password_hash
    from app import User
    u = User(username="admin", password_hash=generate_password_hash("admin"),
             role="admin", must_change_password=False)
    db.session.add(u)
    db.session.commit()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    m = _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})

    # PC 预置 M001 未盘行（账面 40、实盘 0 占位、无盘点人）
    batch = _seed_check_order("B仓", "CK-R8", items=[(m, 40.0, 0.0)])
    client = _make_client()
    h = _bearer(client)

    # 手机补盘该行：实盘 38 → 行被更新（counted_by 写扫码人）
    r1 = _post_stocktake(client, h, "B仓",
                         [{"material_code": "M001", "actual_stock": 38}], batch.id)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    row = InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).one()
    assert row.actual_stock == 38.0
    assert row.counted_at is not None

    # 作废扫码 → PC 预置行必须保留并回"待盘"（不得删 PC 计划行）
    check = InventoryCheckScan.query.one()
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    row = InventoryCheckItem.query.filter_by(inventory_check_id=batch.id).one()
    assert row is not None, "PC 预置行不得被删除"
    assert row.actual_stock == 40.0, "预置行实盘应重置回账面（待盘状态）"
    assert row.difference == 0.0
    assert row.counted_by is None and row.counted_at is None, "预置行应回到'未盘'"
