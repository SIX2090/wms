# -*- coding: utf-8 -*-
"""INV-REVERT-001 / BUG-2026-09-02-003 回归：扫码盘点单作废（可回退）。

背景：扫码盘点单（mobile.py scan_submit / native_api.py /api/stocktake）
创建即 status='completed'，且全系统无任何作废/删除/回退端点。扫错物料/
数量/仓库后无法纠正：要么放任错误调整草稿被审核（库存错调），要么在
库存调整页删草稿（盘点单永远挂着 completed，审计无法区分哪次盘点被
采纳）。移动端 UI 也无撤销入口。

能力：app.py _void_check_scan（写锁 + 级联删除未提交调整草稿 + 状态置
void 留痕）+ 双端点（Web 手机端 POST /mobile/api/check_scan/<id>/void、
Android POST /api/stocktake/void 按 check_no）。任一关联调整单已提交
（completed）则拒绝作废（需先反提交调整单，保证库存一致性）；作废后
INV-GUARD-001 护栏解除，同物料可重新盘点。

覆盖（多仓库场景，A仓 60 / B仓 40，数据自洽）：
T1. 有差异盘点（生成 pending 草稿）→ 作废 → 草稿与明细级联删除，单据
    状态 void，审计留痕（Bearer 请求补写 OperationLog）
T2. 作废后同物料重盘 → 护栏解除，正常生成新草稿
T3. 关联调整单已提交（completed）→ 作废拒绝，提示含单号与反提交指引，
    单据状态仍 completed、草稿仍在
T4. 重复作废（已 void）→ 拒绝
T5. 无差异盘点（无草稿）→ 直接作废成功
T6. Android 端点 /api/stocktake/void 按 check_no 作废成功；不存在单号 404
T7. Web 手机端 scan_submit 响应含 check_id（前端撤销按钮依赖）
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


def _post_stocktake(client, headers, warehouse, lines):
    payload = {"mode": "scan", "warehouse": warehouse, "lines": lines}
    return client.post("/api/stocktake", json=payload, headers=headers)


def _seed_two_warehouse_scene():
    _reset_db()
    _seed_admin()
    wh_a = _seed_warehouse("WA", "A仓")
    wh_b = _seed_warehouse("WB", "B仓")
    _seed_material_with_warehouse_stock("M001", 100.0, {wh_a: 60.0, wh_b: 40.0})
    _seed_material_with_warehouse_stock("M002", 50.0, {wh_a: 30.0, wh_b: 20.0})
    return wh_a, wh_b


def test_t1_void_deletes_pending_drafts_and_marks_void():
    """T1: 作废 → pending 草稿与明细级联删除、状态置 void、审计留痕。"""
    from app import (AdjustmentOrder, AdjustmentOrderItem, InventoryCheckScan,
                     OperationLog)
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    # 盘 B仓 M001：账面 40，实盘 38 → 差异 -2，生成 pending 草稿（含明细）
    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200, r1.get_data(as_text=True)
    check = InventoryCheckScan.query.one()
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1
    assert AdjustmentOrderItem.query.count() >= 1

    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    body = r2.get_json()
    assert body.get("status") == "success", body

    # 草稿与明细级联删除——否则孤儿草稿仍可被审核，库存照错不误
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0, (
        "作废必须级联删除未提交的调整草稿"
    )
    assert AdjustmentOrderItem.query.count() == 0, "调整草稿明细必须一并删除"

    # 单据状态置 void（软作废留痕，不物理删除）
    assert InventoryCheckScan.query.get(check.id).status == "void"

    # 审计留痕：Bearer 请求 current_user 未认证，必须补写 OperationLog
    logs = OperationLog.query.filter_by(
        target_type="inventory_check_scan", target_id=check.id).all()
    assert any("作废" in (log.operation_type or "") for log in logs), (
        "作废是审计敏感操作，必须留操作日志（含 Bearer 请求路径）"
    )


def test_t2_restocktake_after_void_allowed():
    """T2: 作废后护栏解除——同物料可重新盘点并生成新草稿。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    # 草稿已随作废删除，护栏不得拦截重新盘点（扫错重扫的正道）
    r3 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 39}])
    assert r3.status_code == 200, (
        f"作废后重新盘点应放行，实际返回 {r3.status_code}：{r3.get_data(as_text=True)}"
    )
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1


def test_t3_completed_adjustment_blocks_void():
    """T3: 关联调整单已提交 → 拒绝作废（库存已真实变动，先反提交调整单）。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()
    # 模拟人工已审核提交草稿（M001 差异 -2 已作用于库存）
    draft = AdjustmentOrder.query.filter_by(source_type="check_scan").one()
    draft.status = "completed"
    db.session.commit()

    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 400, (
        f"调整单已提交时作废应被拒绝，实际返回 {r2.status_code}"
    )
    msg = (r2.get_json().get("msg") or "") + (r2.get_json().get("message") or "")
    assert "ADJ" in msg, f"提示应包含已提交调整单号，实际：{msg}"
    assert "反提交" in msg, f"提示应指引先反提交调整单，实际：{msg}"

    # 单据与草稿原样保留
    assert InventoryCheckScan.query.get(check.id).status == "completed"
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1


def test_t4_double_void_rejected():
    """T4: 重复作废（已 void）→ 拒绝，防止并发/误触重复处理。"""
    from app import InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    check = InventoryCheckScan.query.one()
    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)

    r3 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r3.status_code == 400, (
        f"已作废单据不得重复作废，实际返回 {r3.status_code}"
    )
    assert InventoryCheckScan.query.get(check.id).status == "void"


def test_t5_void_without_draft():
    """T5: 无差异盘点（账实一致，无草稿）→ 直接作废成功。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    # B仓 M001 账面 40，实盘 40 → 无差异无草稿
    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 40}])
    assert r1.status_code == 200
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0
    check = InventoryCheckScan.query.one()

    r2 = client.post(f"/mobile/api/check_scan/{check.id}/void", headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert InventoryCheckScan.query.get(check.id).status == "void"


def test_t6_android_void_endpoint():
    """T6: Android 端点 /api/stocktake/void 按 check_no 作废；不存在单号 404。"""
    from app import AdjustmentOrder, InventoryCheckScan
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r1 = _post_stocktake(client, h, "B仓", [{"material_code": "M001", "actual_stock": 38}])
    assert r1.status_code == 200
    check_no = r1.get_json()["data"]["check_no"]
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 1

    r2 = client.post("/api/stocktake/void", json={"check_no": check_no}, headers=h)
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json().get("status") == "success"
    assert AdjustmentOrder.query.filter_by(source_type="check_scan").count() == 0
    check = InventoryCheckScan.query.filter_by(check_no=check_no).one()
    assert check.status == "void"

    # 不存在的单号 → 404，不得静默成功
    r3 = client.post("/api/stocktake/void", json={"check_no": "CS999999"}, headers=h)
    assert r3.status_code == 404, (
        f"作废不存在的盘点单应 404，实际返回 {r3.status_code}"
    )


def test_t7_scan_submit_returns_check_id():
    """T7: Web 手机端 scan_submit 响应 data 含 check_id（撤销按钮依赖）。"""
    _seed_two_warehouse_scene()
    client = _make_client()
    h = _bearer(client)

    r = client.post("/mobile/api/scan_submit", headers=h, json={
        "mode": "check",
        "code": "M001",
        "warehouse": "B仓",
        "actual_stock": 38,
    })
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()["data"]
    assert isinstance(data.get("check_id"), int), (
        f"scan_submit 响应应含 int 型 check_id 供前端撤销，实际：{data}"
    )
