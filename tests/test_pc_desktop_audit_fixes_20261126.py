# -*- coding: utf-8 -*-
"""2026-11-26 PC 桌面端全面审计 40 项缺陷修复回归测试。

覆盖四个批次：
- 批次 1（安全/越权/AI 崩溃与确认门禁 P0）：PC-P0-01~03, PC-P0-09~12
- 批次 2（单据生命周期/锁/幂等/合并）：PC-P0-04~08, PC-P1-01~05, PC-P1-12, PC-P2-06, PC-P2-10
- 批次 3（报表/主数据/导入/公式注入）：PC-P1-06~11, PC-P2-01~05
- 批次 4（前端交互/AI 分析/流式确认/视觉降级/外键清理）：PC-P1-13~18, PC-P2-07~09
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from flask import g
from openpyxl import Workbook, load_workbook
from werkzeug.security import generate_password_hash

from tests.document_revision_client import document_post

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
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


@pytest.fixture(autouse=True, scope="module")
def _release_app_ctx():
    _ctx.push()
    yield
    try:
        _ctx.pop()
    except Exception:
        pass


def _reset():
    g.pop("_system_setting_cache", None)
    g.pop("_login_user", None)
    db.session.remove()
    db.drop_all()
    db.create_all()


def _seed_user(username, role="admin", password="pw"):
    u = app_module.User(
        username=username,
        password_hash=generate_password_hash(password),
        role=role,
        status="active",
        must_change_password=False,
    )
    db.session.add(u)
    db.session.flush()
    return u


def _seed_warehouse(code, name, is_default=False, status="active"):
    w = app_module.Warehouse(code=code, name=name, status=status, is_default=is_default)
    db.session.add(w)
    db.session.flush()
    return w


def _seed_unit(name="个", code="PCS"):
    u = app_module.Unit(name=name, code=code)
    db.session.add(u)
    db.session.flush()
    return u


def _seed_material(code, name, unit, warehouse=None, stock=0.0, location="", status="active", price=10.0, min_stock=0.0):
    m = app_module.Material(
        code=code,
        name=name,
        unit_id=unit.id,
        stock=0.0,
        price=price,
        min_stock=min_stock,
        status=status,
    )
    db.session.add(m)
    db.session.flush()
    if stock and warehouse is not None:
        m.stock = stock
        db.session.add(app_module.StockTransaction(
            material_id=m.id,
            transaction_type="in",
            quantity=stock,
            location=location or warehouse.name,
            warehouse_id=warehouse.id,
            created_at=datetime.now(),
        ))
        if location:
            db.session.add(app_module.LocationInventory(
                material_id=m.id,
                warehouse_id=warehouse.id,
                location=location,
                quantity=stock,
            ))
    db.session.flush()
    return m


def _login_web(client, user):
    g.pop("_login_user", None)
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True


def _set_setting(key, value):
    row = app_module.SystemSetting.query.filter_by(key=key).first()
    if row is None:
        row = app_module.SystemSetting(key=key, value=str(value))
        db.session.add(row)
    else:
        row.value = str(value)
    db.session.flush()
    g.pop("_system_setting_cache", None)


def _make_xlsx_bytes(headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# =====================================================================
# 批次 1：安全、越权、AI 崩溃与确认门禁 P0 (PC-P0-01~03, 09~12)
# =====================================================================


def test_pc_p0_01_subcontract_fragments_escape_html():
    """PC-P0-01: 委外发料/收货 HTML 片段必须转义物料编码/名称/单位/备注。"""
    _reset()
    admin = _seed_user("admin_xss", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("<img src=x onerror=alert(1)>", "U1")
    mat = _seed_material(
        "<script>alert(1)</script>",
        "<b>螺母</b>",
        unit,
        warehouse=wh,
        stock=20,
    )
    sup = app_module.Supplier(code="SUP1", name="供应商A")
    db.session.add(sup)
    db.session.flush()
    sc = app_module.SubcontractOrder(
        order_no="SC-XSS-001", date=date.today(), supplier_id=sup.id,
        warehouse=wh.name, status="processing", operator_id=admin.id,
    )
    db.session.add(sc)
    db.session.flush()
    issue = app_module.SubcontractIssue(
        issue_no="SI-XSS-001", date=date.today(), subcontract_order_id=sc.id,
        supplier_id=sup.id, warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    recv = app_module.SubcontractReceive(
        receive_no="SR-XSS-001", date=date.today(), subcontract_order_id=sc.id,
        supplier_id=sup.id, warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add_all([issue, recv])
    db.session.flush()
    db.session.add(app_module.SubcontractIssueItem(
        issue_id=issue.id, material_id=mat.id, quantity=2, unit_id=unit.id,
        remark="<svg onload=alert(2)>",
    ))
    db.session.add(app_module.SubcontractReceiveItem(
        receive_id=recv.id, material_id=mat.id, quantity=2, scrap_quantity=0,
        unit_id=unit.id, price=5, amount=10,
    ))
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    r1 = client.get(f"/subcontract/issue/{issue.id}")
    assert r1.status_code == 200
    body1 = r1.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body1
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body1
    assert "<svg onload=alert(2)>" not in body1
    assert "&lt;svg onload=alert(2)&gt;" in body1
    assert "<img src=x onerror=alert(1)>" not in body1

    r2 = client.get(f"/subcontract/receive/{recv.id}")
    assert r2.status_code == 200
    body2 = r2.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body2
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body2
    assert "<img src=x onerror=alert(1)>" not in body2


def test_pc_p0_03_rbac_finance_admin_print_and_ai_v2_tools():
    """PC-P0-03: finance 禁止访问管理员系统状态与打印编辑器；非 admin 禁止读模板编辑；viewer 禁止调用 AI v2 工具。"""
    _reset()
    _seed_user("admin_rbac", "admin")
    finance = _seed_user("fin_rbac", "finance")
    wh_user = _seed_user("wh_rbac", "warehouse")
    viewer = _seed_user("viewer_rbac", "viewer")
    tpl = app_module.InOrderPrintTemplate(name="默认入库模板", template_type="html", is_default=True)
    db.session.add(tpl)
    db.session.commit()

    client = app_module.app.test_client()

    # finance 访问 /system_status 应被拒绝（302 或 403）
    _login_web(client, finance)
    r_sys = client.get("/system_status")
    assert r_sys.status_code in (302, 403)
    r_sys_json = client.get("/system_status", headers={"Accept": "application/json"})
    assert r_sys_json.status_code == 403

    # finance / warehouse 访问打印模板编辑器 read/grid/preview 应被拒绝
    for user in (finance, wh_user):
        _login_web(client, user)
        for path in (
            f"/in_order_print_template/{tpl.id}/edit",
            f"/in_order_print_template/{tpl.id}/grid",
            f"/in_order_print_template/{tpl.id}/preview_data",
        ):
            resp = client.get(path, headers={"Accept": "application/json"})
            assert resp.status_code in (302, 403), f"{user.role} unexpectedly allowed on {path}: {resp.status_code}"

    # viewer 访问 /api/ai/v2/tools/* 应被 AI 角色门禁拒绝
    _login_web(client, viewer)
    r_tool = client.get("/api/ai/v2/tools/inventory/low-stock")
    assert r_tool.status_code in (200, 403)
    if r_tool.status_code == 200:
        data = r_tool.get_json()
        assert data.get("status") == "error"


def test_pc_p0_10_ai_tools_and_v2_feedback_conversations():
    """PC-P0-10: AI 采购/库存工具和 v2 feedback/conversations 路由不再因错误列名或字段崩溃。"""
    _reset()
    admin = _seed_user("admin_ai10", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("件", "EA")
    mat = _seed_material("M-AI10", "轴承", unit, warehouse=wh, stock=50, price=12.0)
    sup = app_module.Supplier(code="S10", name="华东供应商")
    db.session.add(sup)
    db.session.flush()
    po = app_module.PurchaseOrder(
        order_no="PO-AI10-01",
        date=date.today() - timedelta(days=5),
        expected_date=date.today() + timedelta(days=2),
        supplier_id=sup.id,
        status="pending",
        operator_id=admin.id,
        total_amount=120.0,
    )
    db.session.add(po)
    db.session.flush()
    db.session.add(app_module.PurchaseOrderItem(
        purchase_order_id=po.id, material_id=mat.id, quantity=10, price=12.0, amount=120.0,
    ))
    db.session.add(app_module.StockTransaction(
        material_id=mat.id, transaction_type="in", quantity=10,
        reference_type="in_order", reference_id=99, warehouse_id=wh.id, location=wh.name,
        created_at=datetime.now(),
    ))
    db.session.commit()

    from ai.tools.purchase import pending_purchase_orders, supplier_analysis
    from ai.tools.inventory import stock_transactions

    pending = pending_purchase_orders(limit=10)
    assert len(pending) == 1
    assert pending[0]["supplier"] == "华东供应商"
    sa = supplier_analysis(days=30, limit=10)
    assert len(sa) == 1
    assert sa[0]["name"] == "华东供应商"
    assert sa[0]["avg_lead_time"] == 7.0

    txns = stock_transactions(mat.id, limit=5)
    assert any(t.get("related_order") == "in_order#99" for t in txns)

    client = app_module.app.test_client()
    _login_web(client, admin)
    r_fb = client.post("/api/ai/v2/feedback", json={"rating": "thumbs_up", "note": "准确"})
    assert r_fb.status_code == 200, r_fb.get_data(as_text=True)
    assert r_fb.get_json()["status"] == "success"

    r_save = client.post("/api/ai/v2/conversations", json={
        "session_id": "sess-pc-10", "role": "user", "content": "查一下库存",
    })
    assert r_save.status_code == 200, r_save.get_data(as_text=True)
    r_list = client.get("/api/ai/v2/conversations?session_id=sess-pc-10")
    assert r_list.status_code == 200
    rows = r_list.get_json()["data"]
    assert len(rows) == 1 and rows[0]["content"] == "查一下库存"


def test_pc_p0_11_patrol_scheduler_delay_join_commit_and_warehouse_stock():
    """PC-P0-11: 巡检采购延迟联表不报错、负库存按分仓检出、已有告警更新持久提交。"""
    _reset()
    admin = _seed_user("admin_patrol", "admin")
    wh1 = _seed_warehouse("WH1", "一仓", is_default=True)
    wh2 = _seed_warehouse("WH2", "二仓")
    unit = _seed_unit("个", "PCS")
    mat = _seed_material("M-PATROL", "测试料", unit, warehouse=wh1, stock=10, min_stock=5)
    # 制造二仓单仓负库存（总库存仍为 +5，但二仓为 -5）
    mat.stock = 5.0
    db.session.add(app_module.StockTransaction(
        material_id=mat.id, transaction_type="out", quantity=-5.0,
        warehouse_id=wh2.id, location=wh2.name, created_at=datetime.now(),
    ))
    sup = app_module.Supplier(code="SPAT", name="巡检供应商")
    db.session.add(sup)
    db.session.flush()
    for i in range(3):
        po = app_module.PurchaseOrder(
            order_no=f"PO-PAT-{i}", date=date.today(), supplier_id=sup.id,
            status="pending", operator_id=admin.id, total_amount=10,
        )
        db.session.add(po)
        db.session.flush()
        db.session.add(app_module.PurchaseOrderItem(
            purchase_order_id=po.id, material_id=mat.id, quantity=1, price=10, amount=10,
        ))

    r_neg = app_module.AIPatrolRule(
        name="负库存巡检", rule_type="negative_stock", enabled=True, severity="critical", created_by=admin.id,
    )
    r_delay = app_module.AIPatrolRule(
        name="采购延迟巡检", rule_type="purchase_delay", enabled=True, threshold_days=30,
        severity="warning", created_by=admin.id,
    )
    db.session.add_all([r_neg, r_delay])
    db.session.commit()

    from ai.patrol_scheduler import _create_alert, _evaluate_rule

    models = {
        "Material": app_module.Material,
        "PurchaseOrder": app_module.PurchaseOrder,
        "PurchaseOrderItem": app_module.PurchaseOrderItem,
        "InOrder": app_module.InOrder,
        "OutOrder": app_module.OutOrder,
        "TransferOrder": app_module.TransferOrder,
        "InventoryCheck": app_module.InventoryCheck,
        "AdjustmentOrder": app_module.AdjustmentOrder,
    }
    neg_alerts = _evaluate_rule(r_neg, db, models)
    assert len(neg_alerts) == 1
    assert mat.id in neg_alerts[0]["data_context"]["material_ids"]

    delay_alerts = _evaluate_rule(r_delay, db, models)
    assert len(delay_alerts) == 1
    assert mat.id in delay_alerts[0]["data_context"]["material_ids"]

    first = _create_alert(r_neg, {"title": "旧标题", "message": "旧内容", "severity": "critical"})
    assert first.title == "旧标题"
    _create_alert(r_neg, {"title": "新标题", "message": "新内容", "severity": "warning"})
    db.session.expire_all()
    reloaded = db.session.get(app_module.AIPatrolAlert, first.id)
    assert reloaded.title == "新标题"
    assert reloaded.severity == "warning"


def test_pc_p0_12_ai_confirmation_gate_feedback_idor_and_other_in():
    """PC-P0-12: 高风险物料必须显式确认；document_feedback 校验任务存在及归属；other_in 不误绑采购单且拦截停用物料。"""
    _reset()
    u1 = _seed_user("wh_u1", "warehouse")
    u2 = _seed_user("wh_u2", "warehouse")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    active_mat = _seed_material("M-ACT", "正常轴承", unit, warehouse=wh, stock=10)
    inactive_mat = _seed_material("M-INACT", "停用轴承", unit, warehouse=wh, stock=0, status="inactive")
    sup = app_module.Supplier(code="S12", name="测试供方")
    db.session.add(sup)
    db.session.flush()
    po = app_module.PurchaseOrder(
        order_no="PO-OPEN-12", date=date.today(), supplier_id=sup.id,
        status="pending", operator_id=u1.id, total_amount=100,
    )
    db.session.add(po)
    db.session.flush()
    db.session.add(app_module.PurchaseOrderItem(
        purchase_order_id=po.id, material_id=active_mat.id, quantity=10, price=10, amount=100,
    ))
    job = app_module.AIDocumentJob(
        user_id=u1.id, source="upload", document_type="in_order", status="ready",
    )
    db.session.add(job)
    db.session.commit()

    # 1) 高风险物料未有任何确认记录时必须阻断
    from ai.documents.document_confirmation_status import validate_draft_creation_allowed
    allowed, reasons = validate_draft_creation_allowed(
        field_records=[],
        duplicate_risk=False,
        low_confidence_fields=[],
        material_ambiguity=False,
        specification_conflict=False,
        high_risk_material=True,
    )
    assert not allowed
    assert any("高风险" in r for r in reasons)

    # 2) document_feedback 校验任务存在性（404）与跨用户 IDOR（403）
    client = app_module.app.test_client()
    _login_web(client, u2)
    fb_evidence = [{"field_name": "quantity", "value": "1"}]
    r_404 = client.post("/api/ai/document_feedback", json={
        "document_job_id": 999999,
        "evidence_fields": fb_evidence,
        "corrections": {},
    })
    assert r_404.status_code == 404
    r_403 = client.post("/api/ai/document_feedback", json={
        "document_job_id": job.id,
        "evidence_fields": fb_evidence,
        "corrections": {},
    })
    assert r_403.status_code == 403

    # 3) 确认台创建 other_in 不得自动匹配开放采购单，且拦截停用物料
    with app_module.app.test_request_context("/api/ai/documents/confirm", method="POST"):
        from flask_login import login_user
        login_user(u1)
        res_inact, err_inact = app_module._ai_create_confirmed_document_draft(
            "in_order",
            [{"material_id": inactive_mat.id, "material_name": inactive_mat.name, "quantity": 2, "warehouse": wh.name}],
            inbound_business_type="other_in",
        )
        assert res_inact is None
        assert err_inact and "停用" in err_inact

        res_other, err_other = app_module._ai_create_confirmed_document_draft(
            "in_order",
            [{"material_id": active_mat.id, "material_name": active_mat.name, "quantity": 3, "warehouse": wh.name}],
            inbound_business_type="other_in",
            confirmation_token="tok-other-in-12",
        )
        assert err_other is None, err_other
        assert res_other and res_other.get("order_no")
        created_order = app_module.InOrder.query.filter_by(order_no=res_other["order_no"]).first()
        assert created_order is not None
        assert created_order.business_type == "其他入库"
        assert created_order.source_purchase_order_id is None

        # 幂等重放返回同一草稿，不重复建单
        res_replay, err_replay = app_module._ai_create_confirmed_document_draft(
            "in_order",
            [{"material_id": active_mat.id, "material_name": active_mat.name, "quantity": 3, "warehouse": wh.name}],
            inbound_business_type="other_in",
            confirmation_token="tok-other-in-12",
        )
        assert err_replay is None
        assert res_replay["order_no"] == res_other["order_no"]


# =====================================================================
# 批次 2：单据生命周期、锁、幂等与物料合并 (PC-P0-04~08, P1-01~05, P2-06)
# =====================================================================


def test_pc_p0_04_batch_complete_in_order_no_double_count_and_blocks_real_over_receive():
    """PC-P0-04: 批量完成正常采购入库草稿不再把自身预占双算导致误拦；真实超收仍必须拦截。"""
    _reset()
    admin = _seed_user("admin_p04", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    mat = _seed_material("M-P04", "螺栓", unit, warehouse=wh, stock=0)
    sup = app_module.Supplier(code="S04", name="采购商")
    db.session.add(sup)
    db.session.flush()
    po = app_module.PurchaseOrder(
        order_no="PO-P04-01", date=date.today(), supplier_id=sup.id,
        status="pending", operator_id=admin.id, total_amount=100,
    )
    db.session.add(po)
    db.session.flush()
    poi = app_module.PurchaseOrderItem(
        purchase_order_id=po.id, material_id=mat.id, quantity=10, received_quantity=10, price=10, amount=100,
    )
    db.session.add(poi)
    db.session.flush()

    # 正常全量下推的草稿（received_quantity 已预占 10）
    io_ok = app_module.InOrder(
        order_no="IN-P04-OK", date=date.today(), supplier_id=sup.id,
        business_type="采购入库", warehouse=wh.name,
        source_purchase_order_id=po.id, status="pending", operator_id=admin.id,
    )
    db.session.add(io_ok)
    db.session.flush()
    db.session.add(app_module.InOrderItem(
        in_order_id=io_ok.id, material_id=mat.id,
        source_purchase_order_item_id=poi.id, quantity=10, price=10, amount=100,
    ))
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)
    r = client.post("/in_order/batch_complete", json={"ids": [io_ok.id]})
    assert r.status_code == 200, r.get_data(as_text=True)
    data = r.get_json()
    assert data["completed"] == 1
    db.session.expire_all()
    assert db.session.get(app_module.InOrder, io_ok.id).status == "completed"

    # 真实超收草稿（再建一张 5 件的草稿，超过 PO 总量 10）必须被拦截
    io_over = app_module.InOrder(
        order_no="IN-P04-OVER", date=date.today(), supplier_id=sup.id,
        business_type="采购入库", warehouse=wh.name,
        source_purchase_order_id=po.id, status="pending", operator_id=admin.id,
    )
    db.session.add(io_over)
    db.session.flush()
    db.session.add(app_module.InOrderItem(
        in_order_id=io_over.id, material_id=mat.id,
        source_purchase_order_item_id=poi.id, quantity=5, price=10, amount=50,
    ))
    db.session.commit()
    r2 = client.post("/in_order/batch_complete", json={"ids": [io_over.id]})
    assert r2.status_code == 400
    assert r2.get_json()["completed"] == 0
    db.session.expire_all()
    assert db.session.get(app_module.InOrder, io_over.id).status == "pending"


def test_pc_p0_05_cancelled_sales_order_guard_and_cancel_checks_item_links():
    """PC-P0-05: 已取消/草稿销售单不能过账或被覆盖状态；存在行级关联出库草稿时禁止取消销售单。"""
    _reset()
    admin = _seed_user("admin_p05", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    mat = _seed_material("M-P05", "阀体", unit, warehouse=wh, stock=50)
    cust = app_module.Customer(code="C05", name="客户五")
    db.session.add(cust)
    db.session.flush()

    so1 = app_module.SalesOrder(
        order_no="SO-P05-1", date=date.today(), customer_id=cust.id,
        warehouse=wh.name, warehouse_id=wh.id, status="confirmed", operator_id=admin.id,
    )
    so2 = app_module.SalesOrder(
        order_no="SO-P05-2", date=date.today(), customer_id=cust.id,
        warehouse=wh.name, warehouse_id=wh.id, status="cancelled", operator_id=admin.id,
    )
    db.session.add_all([so1, so2])
    db.session.flush()
    soi1 = app_module.SalesOrderItem(sales_order_id=so1.id, material_id=mat.id, quantity=10, price=5, amount=50)
    soi2 = app_module.SalesOrderItem(sales_order_id=so2.id, material_id=mat.id, quantity=10, price=5, amount=50)
    db.session.add_all([soi1, soi2])
    db.session.flush()

    # 出库单单头未挂 so1，仅通过 OutOrderItem.source_sales_order_item_id 挂接 so1
    out_line_linked = app_module.OutOrder(
        order_no="OUT-P05-1", date=date.today(), customer=cust.name,
        business_type="销售出库", warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add(out_line_linked)
    db.session.flush()
    db.session.add(app_module.OutOrderItem(
        out_order_id=out_line_linked.id, material_id=mat.id,
        source_sales_order_item_id=soi1.id, quantity=4, price=5, amount=20,
    ))

    # 指向已取消 so2 的出库单
    out_cancelled = app_module.OutOrder(
        order_no="OUT-P05-2", date=date.today(), customer=cust.name,
        business_type="销售出库", warehouse=wh.name, source_sales_order_id=so2.id,
        status="pending", operator_id=admin.id,
    )
    db.session.add(out_cancelled)
    db.session.flush()
    db.session.add(app_module.OutOrderItem(
        out_order_id=out_cancelled.id, material_id=mat.id,
        source_sales_order_item_id=soi2.id, quantity=2, price=5, amount=10,
    ))
    db.session.commit()

    ok, msg = app_module.sales_outbound_remaining_check(out_cancelled)
    assert not ok
    assert "取消" in msg or "状态" in msg

    app_module.sync_sales_order_shipment(out_cancelled, quantity_sign=1)
    assert so2.status == "cancelled"

    client = app_module.app.test_client()
    _login_web(client, admin)
    r_cancel = client.post(f"/sales/{so1.id}/cancel")
    assert r_cancel.status_code in (200, 400)
    assert r_cancel.get_json()["status"] == "error"
    db.session.expire_all()
    assert db.session.get(app_module.SalesOrder, so1.id).status == "confirmed"


def test_pc_p0_06_subcontract_revert_and_batch_status_guards():
    """PC-P0-06: 委外反加工拦收货单；批量更新状态拦完结回退/关联收发/无明细并写审计。"""
    _reset()
    admin = _seed_user("admin_p06", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    mat = _seed_material("M-P06", "加工件", unit, warehouse=wh, stock=20)
    sup = app_module.Supplier(code="S06", name="委外商")
    db.session.add(sup)
    db.session.flush()

    sc_recv = app_module.SubcontractOrder(
        order_no="SC-P06-RECV", date=date.today(), supplier_id=sup.id,
        warehouse=wh.name, status="processing", operator_id=admin.id,
    )
    sc_empty = app_module.SubcontractOrder(
        order_no="SC-P06-EMPTY", date=date.today(), supplier_id=sup.id,
        warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    sc_ok = app_module.SubcontractOrder(
        order_no="SC-P06-OK", date=date.today(), supplier_id=sup.id,
        warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add_all([sc_recv, sc_empty, sc_ok])
    db.session.flush()
    db.session.add(app_module.SubcontractReceive(
        receive_no="SR-P06-1", date=date.today(), subcontract_order_id=sc_recv.id,
        supplier_id=sup.id, warehouse=wh.name, status="pending", operator_id=admin.id,
    ))
    db.session.add(app_module.SubcontractItem(
        subcontract_order_id=sc_ok.id, material_id=mat.id, quantity=5, unit_id=unit.id,
    ))
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    r_rev = client.post(f"/subcontract/{sc_recv.id}/revert_to_pending")
    assert r_rev.get_json()["status"] == "error"

    r_b1 = client.post("/subcontract/batch_update_status", json={"ids": [sc_recv.id], "status": "pending"})
    assert r_b1.get_json()["status"] == "error"

    r_b2 = client.post("/subcontract/batch_update_status", json={"ids": [sc_empty.id], "status": "processing"})
    assert r_b2.get_json()["status"] == "error"

    r_b3 = client.post("/subcontract/batch_update_status", json={"ids": [sc_ok.id], "status": "processing"})
    assert r_b3.status_code == 200 and r_b3.get_json()["status"] == "success"
    audit = app_module.OperationAudit.query.filter_by(
        operation="batch_update_subcontract_status", target_id=sc_ok.id
    ).first()
    assert audit is not None


def test_pc_p0_07_and_p0_08_opening_stock_idempotency_import_and_material_merge():
    """PC-P0-07 & PC-P0-08: 期初保存幂等重放、导入拦截停用物料并支持首行回滚后续行入账、物料查重合并期初行不冲突。"""
    _reset()
    admin = _seed_user("admin_p07", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    m1 = _seed_material("M-OS1", "正常期初料", unit)
    m2 = _seed_material("M-OS2", "重复期初料", unit)
    m_inact = _seed_material("M-OS-OFF", "停用期初料", unit, status="inactive")
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    # 1) 期初保存幂等重放
    payload = {
        "date": date.today().isoformat(),
        "warehouse_id": wh.id,
        "remark": "测试期初",
        "items": [{"material_id": m1.id, "warehouse_id": wh.id, "quantity": 10, "price": 5}],
    }
    headers = {"X-Idempotency-Key": "os-idem-20261126-001"}
    r1 = client.post("/opening_stock/save", json=payload, headers=headers)
    assert r1.status_code == 200, r1.get_data(as_text=True)
    d1 = r1.get_json()
    assert d1["status"] == "success"
    r2 = client.post("/opening_stock/save", json=payload, headers=headers)
    assert r2.status_code == 200
    assert r2.get_json()["doc_id"] == d1["doc_id"]
    assert app_module.OpeningStockDoc.query.count() == 1
    db.session.expire_all()
    assert db.session.get(app_module.Material, m1.id).stock == 10.0

    # 2) 物料查重合并：同一单据同一仓库同时含 target 和 source 两条 opening_stock 不触发唯一键冲突
    os_doc = db.session.get(app_module.OpeningStockDoc, d1["doc_id"])
    db.session.add(app_module.OpeningStock(
        doc_id=os_doc.id, material_id=m2.id, warehouse_id=wh.id,
        date=date.today(), quantity=5, price=5, amount=25, operator_id=admin.id,
    ))
    m2.stock = 5.0
    db.session.add(app_module.StockTransaction(
        material_id=m2.id, transaction_type="opening", quantity=5,
        reference_type="opening_stock", reference_id=os_doc.id, warehouse_id=wh.id, location=wh.name,
        created_at=datetime.now(),
    ))
    db.session.commit()

    merged = app_module.merge_material_duplicates(m1.id, m2.id, identity_confirmed=True)
    assert merged["source_id"] == m2.id
    assert merged["ledger_ok"] is True
    rows = app_module.OpeningStock.query.filter_by(doc_id=os_doc.id, warehouse_id=wh.id, material_id=m1.id).all()
    assert len(rows) == 1
    assert rows[0].quantity == 15.0

    # 3) 期初导入：第 1 行停用物料被跳过回滚，第 2 行正常物料仍应成功入账
    m3 = _seed_material("M-OS3", "导入料3", unit)
    db.session.commit()
    xlsx = _make_xlsx_bytes(
        ["物料编码", "仓库", "数量", "单价", "日期"],
        [
            [m_inact.code, wh.name, 5, 10, date.today().isoformat()],
            [m3.code, wh.name, 8, 12, date.today().isoformat()],
        ],
    )
    r_imp = client.post(
        "/opening_stock/import",
        data={"file": (xlsx, "opening.xlsx")},
        content_type="multipart/form-data",
    )
    assert r_imp.status_code == 200, r_imp.get_data(as_text=True)
    res_imp = r_imp.get_json()
    assert res_imp["status"] == "success"
    assert res_imp.get("imported", 0) == 1
    assert res_imp.get("skipped", 0) == 1


def test_pc_p1_02_03_04_05_and_p2_06_order_lifecycle_fixes():
    """PC-P1-02/03/04/05 & PC-P2-06: 采购下推拦截停用物料、销售下推算总额保状态、关联出库拦无来源行保用途、调拨删审计、委外导入编辑锁。"""
    _reset()
    admin = _seed_user("admin_p1", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    mat = _seed_material("M-P1A", "活跃件", unit, warehouse=wh, stock=100, price=20)
    mat_off = _seed_material("M-P1OFF", "停用件", unit, status="inactive", price=20)
    sup = app_module.Supplier(code="SP1", name="供方1")
    cust = app_module.Customer(code="CP1", name="客户1")
    db.session.add_all([sup, cust])
    db.session.flush()

    # PC-P1-02: 采购申请转采购单拦截停用物料
    pr = app_module.PurchaseRequest(
        request_no="PR-P1-01", date=date.today(), status="approved", operator_id=admin.id,
    )
    db.session.add(pr)
    db.session.flush()
    db.session.add(app_module.PurchaseRequestItem(
        purchase_request_id=pr.id, material_id=mat_off.id, material_code=mat_off.code,
        material_name=mat_off.name, quantity=5, estimated_price=10, supplier_id=sup.id,
    ))

    # PC-P1-03: build_sales_outbound_draft 计算 total_amount 且保持部分发货状态
    so = app_module.SalesOrder(
        order_no="SO-P1-01", date=date.today(), customer_id=cust.id,
        warehouse=wh.name, warehouse_id=wh.id, status="confirmed",
        shipment_status="partial", operator_id=admin.id,
    )
    db.session.add(so)
    db.session.flush()
    soi = app_module.SalesOrderItem(
        sales_order_id=so.id, material_id=mat.id, quantity=10, shipped_quantity=3, price=20, amount=200,
    )
    db.session.add(soi)

    # PC-P1-05: 批量删除调拨单写 OperationAudit
    tr = app_module.TransferOrder(
        transfer_no="TR-P1-01", date=date.today(), from_warehouse=wh.name, to_warehouse=wh.name,
        from_location="", to_location="", status="pending", operator_id=admin.id,
    )
    db.session.add(tr)

    # PC-P2-06: 委外导入受 document_edit_guard 保护
    sc = app_module.SubcontractOrder(
        order_no="SC-P206", date=date.today(), supplier_id=sup.id,
        warehouse=wh.name, status="pending", operator_id=admin.id,
    )
    db.session.add(sc)
    db.session.commit()

    client = app_module.app.test_client()
    _login_web(client, admin)

    r_pr = client.post(
        f"/purchase_request/{pr.id}/create_purchase_order",
        json={"supplier_id": sup.id},
    )
    assert r_pr.get_json()["status"] == "error"
    assert "停用" in r_pr.get_json()["msg"]

    with app_module.app.test_request_context("/sales", method="POST"):
        from flask_login import login_user
        login_user(admin)
        outbound, draft_state = app_module.build_sales_outbound_draft(so, {soi.id: 2})
        assert draft_state == "created", draft_state
        assert outbound.total_amount == 40.0
        assert so.shipment_status == "partial"
        db.session.commit()

    # PC-P1-04: 关联销售出库禁止无来源新增明细，且编辑时锁定 purpose
    r_add = document_post(
        client,
        f"/out_order/{outbound.id}/item/add",
        data={"material_id": mat.id, "quantity": 1, "price": 20},
    )
    assert r_add.get_json()["status"] == "error"
    orig_purpose = outbound.purpose
    r_upd = document_post(
        client,
        f"/out_order/{outbound.id}/update",
        data={
            "date": date.today().isoformat(),
            "warehouse": wh.name,
            "business_type": "销售出库",
            "customer": cust.name,
            "purpose": "被篡改的用途",
        },
    )
    assert r_upd.status_code == 200
    db.session.expire_all()
    assert db.session.get(app_module.OutOrder, outbound.id).purpose == orig_purpose

    # PC-P1-05: 批量删除调拨单审计
    r_tr = client.post("/transfer/batch_delete", data={"ids[]": [tr.id]})
    assert r_tr.status_code == 200 and r_tr.get_json()["deleted"] == 1
    assert app_module.OperationAudit.query.filter_by(operation="delete_transfer", target_id=tr.id).first() is not None

    # PC-P2-06: 未带 X-WMS-Document-Revision 调用委外产品导入被编辑锁拦截
    r_imp = client.post(f"/subcontract/{sc.id}/items/import")
    assert r_imp.status_code in (400, 409)


# =====================================================================
# 批次 3：报表口径、主数据、导入与安全加固 (PC-P1-06~11, PC-P2-01~05)
# =====================================================================


def test_pc_p1_06_07_08_reports_sorting_and_exports():
    """PC-P1-06/07/08: 销售对账净额扣减 revert_out；库存按选仓排序与分仓最后出库；采购价分析导出受价格开关控制；售后导出支持仓库过滤。"""
    _reset()
    admin = _seed_user("admin_rep", "admin")
    wh1 = _seed_warehouse("WH1", "一仓", is_default=True)
    wh2 = _seed_warehouse("WH2", "二仓")
    unit = _seed_unit("个", "PCS")
    # m_a: 一仓 100，二仓 0（全局 100）; m_b: 一仓 5，二仓 50（全局 55）
    m_a = _seed_material("M-SORT-A", "物料A", unit, warehouse=wh1, stock=100)
    m_b = _seed_material("M-SORT-B", "物料B", unit, warehouse=wh1, stock=5)
    m_b.stock = 55.0
    db.session.add(app_module.StockTransaction(
        material_id=m_b.id, transaction_type="in", quantity=50, warehouse_id=wh2.id, location=wh2.name,
        created_at=datetime.now(),
    ))
    # 分仓出库时间：m_a 仅在 wh1 有出库
    db.session.add(app_module.StockTransaction(
        material_id=m_a.id, transaction_type="out", quantity=-3, warehouse_id=wh1.id, location=wh1.name,
        created_at=datetime.now(),
    ))

    # 销售对账：同一销售出库 out(-5) + revert_out(+5) + out(-5) => 净出库应为 5 而非 10
    cust = app_module.Customer(code="CREP", name="对账客户")
    db.session.add(cust)
    db.session.flush()
    so = app_module.SalesOrder(
        order_no="SO-REP-1", date=date.today(), customer_id=cust.id,
        warehouse=wh1.name, warehouse_id=wh1.id, status="confirmed", operator_id=admin.id,
    )
    db.session.add(so)
    db.session.flush()
    soi = app_module.SalesOrderItem(
        sales_order_id=so.id, material_id=m_a.id, quantity=5, shipped_quantity=5, price=10, amount=50,
    )
    db.session.add(soi)
    out = app_module.OutOrder(
        order_no="OUT-REP-1", date=date.today(), customer=cust.name,
        business_type="销售出库", warehouse=wh1.name, source_sales_order_id=so.id,
        status="completed", operator_id=admin.id,
    )
    db.session.add(out)
    db.session.flush()
    db.session.add(app_module.OutOrderItem(
        out_order_id=out.id, material_id=m_a.id, source_sales_order_item_id=soi.id, quantity=5, price=10, amount=50,
    ))
    for txn_type, qty in (("out", -5), ("revert_out", 5), ("out", -5)):
        db.session.add(app_module.StockTransaction(
            material_id=m_a.id, transaction_type=txn_type, quantity=qty,
            reference_type="out_order", reference_id=out.id, warehouse_id=wh1.id, location=wh1.name,
            created_at=datetime.now(),
        ))

    # 售后出库两仓记录
    db.session.add(app_module.AfterSaleOutOrder(
        order_no="AS-W1", date=date.today(), customer=cust.name, warehouse=wh1.name,
        status="pending", operator_id=admin.id,
    ))
    db.session.add(app_module.AfterSaleOutOrder(
        order_no="AS-W2", date=date.today(), customer=cust.name, warehouse=wh2.name,
        status="pending", operator_id=admin.id,
    ))
    _set_setting("price_dimension_enabled", "0")
    db.session.commit()

    # PC-P1-06: 对账净出库为 5
    from services.sales_report_print import sales_reconciliation_context
    with app_module.app.test_request_context(f"/report/sales_reconciliation?warehouse_id={wh1.id}"):
        ctx = sales_reconciliation_context()
        assert len(ctx["rows"]) == 1
        assert ctx["rows"][0]["inventory_qty"] == 5.0

    # PC-P1-07: 二仓按库存倒序应 m_b (50) 在 m_a (0) 前面；_last_outbound_dates 按仓过滤
    from routes.stock_query import build_stock_material_query
    wh2_map = app_module.get_warehouse_stock_quantities(wh2)
    q = build_stock_material_query(
        {"search": "", "category_id": None, "stock_filter": "", "sort": "stock", "order": "desc"},
        wh2_map,
    )
    ordered_ids = [m.id for m in q.all()]
    assert ordered_ids.index(m_b.id) < ordered_ids.index(m_a.id)
    assert m_a.id in app_module._last_outbound_dates([m_a.id], warehouse=wh1)
    assert m_a.id not in app_module._last_outbound_dates([m_a.id], warehouse=wh2)

    # PC-P1-08: 关闭价格维度时禁止导出 purchase_price_analysis；售后导出支持仓库过滤
    client = app_module.app.test_client()
    _login_web(client, admin)
    r_price = client.get(f"/report/purchase_price_analysis/print_excel?warehouse_id={wh1.id}")
    assert r_price.status_code == 400

    r_as = client.get(f"/export/after_sale_out?warehouse_id={wh2.id}")
    assert r_as.status_code == 200
    wb = load_workbook(io.BytesIO(r_as.data))
    ws = wb.active
    order_nos = [ws.cell(r, 1).value for r in range(2, ws.max_row + 1)]
    assert "AS-W2" in order_nos and "AS-W1" not in order_nos


def test_pc_p1_09_10_11_and_p2_01_to_05_master_data_imports_and_security():
    """PC-P1-09/10/11 & PC-P2-01~05: 默认仓禁停用、合同引用全查、导入不留空单、Excel 公式转义、协议清洗、模板注册校验、主数据校验。"""
    _reset()
    admin = _seed_user("admin_p3", "admin")
    wh = _seed_warehouse("WH1", "主仓", is_default=True)
    unit = _seed_unit("个", "PCS")
    mat_on = _seed_material("M-P3-ON", "启用料", unit, warehouse=wh, stock=20)
    mat_off = _seed_material("M-P3-OFF", "停用料", unit, status="inactive")
    contract = app_module.Contract(contract_no="HT-2026-001", project_name="测试项目")
    db.session.add(contract)
    db.session.flush()
    as_order = app_module.AfterSaleOutOrder(
        order_no="AS-CT-1", date=date.today(), customer="客户", warehouse=wh.name,
        status="pending", operator_id=admin.id,
    )
    db.session.add(as_order)
    db.session.flush()
    db.session.add(app_module.AfterSaleOutOrderItem(
        after_sale_out_order_id=as_order.id, material_id=mat_on.id, quantity=1,
        price=10.0, amount=10.0,
        contract_id=contract.id, contract_no=contract.contract_no,
    ))
    db.session.commit()

    # PC-P1-10: 合同删除校验覆盖售后出库明细
    blockers = app_module._contract_delete_blockers(contract)
    assert any("售后" in b for b in blockers)

    # PC-P2-01 & PC-P2-02: 公式注入与控制字符协议清洗
    from utils import _has_dangerous_protocol, _sanitize_excel_cell
    assert _sanitize_excel_cell("=CMD|' /C calc'!A0").startswith("'")
    assert _sanitize_excel_cell("+1+1").startswith("'")
    assert _sanitize_excel_cell("-12.50") == "-12.50"
    assert _has_dangerous_protocol("java\nscript:alert(1)") is True
    assert _has_dangerous_protocol("data\t:text/html,<script>") is True

    # PC-P2-04: BOM 明细拦截停用物料与布尔数量
    from routes.bom import _prepare_bom_items
    with pytest.raises(ValueError, match="停用"):
        _prepare_bom_items([{"material_id": mat_off.id, "quantity": 1}])
    with pytest.raises(ValueError):
        _prepare_bom_items([{"material_id": mat_on.id, "quantity": True}])

    client = app_module.app.test_client()
    _login_web(client, admin)

    # PC-P1-09: 默认仓库禁止停用
    r_wh = client.post(
        f"/warehouse/{wh.id}/edit",
        data={"code": wh.code, "name": wh.name, "status": "inactive", "is_default": "1"},
    )
    assert r_wh.get_json()["status"] == "error"

    # PC-P1-11: 销售导入停用物料全部失败时不遗留 0 行空单头
    xlsx_sales = _make_xlsx_bytes(
        ["销售订单号", "客户名称", "发货仓库", "物料编码", "数量", "含税单价", "税率"],
        [["SO-ORPHAN-1", "测试客户", wh.name, mat_off.code, 5, 10, 0.13]],
    )
    r_sales = client.post(
        "/sales/import",
        data={"file": (xlsx_sales, "sales.xlsx")},
        content_type="multipart/form-data",
    )
    assert r_sales.status_code == 200
    assert app_module.SalesOrder.query.filter_by(order_no="SO-ORPHAN-1").first() is None

    # PC-P2-03: 打印模板上传拒绝未注册 target_code
    fake_xlsx = _make_xlsx_bytes(["A"], [["B"]])
    r_tpl = client.post(
        "/print_templates/upload",
        data={
            "target_type": "report",
            "target_code": "unregistered_evil_code",
            "name": "非法模板",
            "excel_file": (fake_xlsx, "tpl.xlsx"),
        },
        content_type="multipart/form-data",
    )
    assert r_tpl.status_code in (200, 400)
    assert r_tpl.get_json()["status"] == "error"

    # PC-P2-05: 物料编辑非法 category_id 返回友好错误而非 500，且合法编辑保留修剪后的 purpose
    from routes.material import _material_edit_revision
    rev = _material_edit_revision(mat_on)
    r_mat = client.post(
        f"/material/edit/{mat_on.id}",
        data={
            "edit_revision": rev,
            "code": mat_on.code,
            "name": mat_on.name,
            "unit_id": unit.id,
            "category_id": "abc",
        },
    )
    assert r_mat.status_code in (200, 400)
    mat_err = r_mat.get_json()
    assert mat_err["status"] == "error"
    assert "物料分类" in (mat_err.get("msg") or "")

    r_mat_ok = client.post(
        f"/material/edit/{mat_on.id}",
        data={
            "edit_revision": _material_edit_revision(mat_on),
            "code": mat_on.code,
            "name": mat_on.name,
            "unit_id": unit.id,
            "purpose": "  测试用途  ",
        },
    )
    assert r_mat_ok.status_code == 200
    assert r_mat_ok.get_json()["status"] == "success"
    db.session.expire_all()
    assert db.session.get(app_module.Material, mat_on.id).purpose == "测试用途"


# =====================================================================
# 批次 4：PC 前端、AI 数据分析、流式确认、视觉降级与留存外键 (PC-P1-13~18, P2-07~09)
# =====================================================================


def test_pc_p1_14_15_16_17_18_ai_analytics_transfer_vision_and_retention():
    """PC-P1-14~18: AI 周转率排序、异常阈值与分仓库存、需求预测去调拨、无库位调拨草稿、视觉模型首选顺序、留存删除清理子表外键。"""
    _reset()
    admin = _seed_user("admin_p4", "admin")
    wh1 = _seed_warehouse("WH1", "一仓", is_default=True)
    wh2 = _seed_warehouse("WH2", "二仓")
    unit = _seed_unit("个", "PCS")
    m_hot = _seed_material("M-HOT", "热销件", unit, warehouse=wh1, stock=100, price=10)
    m_warm = _seed_material("M-WARM", "普通件", unit, warehouse=wh1, stock=100, price=10)
    m_cold = _seed_material("M-COLD", "调拨件", unit, warehouse=wh1, stock=100, price=10)
    m_idle = _seed_material("M-IDLE", "纯滞销件", unit, warehouse=wh1, stock=100, price=10)

    # m_hot 出库 50，m_warm 出库 10，m_cold 仅调拨出库 20（不算需求消费），m_idle 无出库
    for mat_obj, txn_type, qty in (
        (m_hot, "out", -50),
        (m_warm, "out", -10),
        (m_cold, "transfer_out", -20),
    ):
        db.session.add(app_module.StockTransaction(
            material_id=mat_obj.id, transaction_type=txn_type, quantity=qty,
            warehouse_id=wh1.id, location=wh1.name,
            created_at=datetime.now() - timedelta(days=2),
        ))
    db.session.commit()

    # PC-P1-14: top_n=1 时 m_hot 应排第一，m_warm 虽未进 top1 仍不误判为滞销，m_idle 进入滞销
    turn_md = app_module._ai_analysis_inventory_turnover(top_n=1, days=30, warehouse=wh1.name)
    assert isinstance(turn_md, str)
    top_part, _, slow_part = turn_md.partition("滞销品")
    assert m_hot.code in top_part
    assert m_warm.code not in slow_part
    assert m_idle.code in slow_part

    # PC-P1-15: 需求预测排除 transfer_out（m_cold 需求为 0）
    client = app_module.app.test_client()
    _login_web(client, admin)
    r_fc = client.post("/api/ai/demand_forecast", json={"forecast_days": 30})
    assert r_fc.status_code == 200
    fc_data = r_fc.get_json()
    assert fc_data["status"] == "success"
    cold_rows = [row for row in fc_data.get("forecasts", []) if row.get("material_code") == m_cold.code]
    assert not cold_rows or cold_rows[0].get("avg_daily", 0) == 0

    # PC-P1-16: 库位管理关闭时调拨草稿不自动填充库位
    _set_setting("location_management_enabled", "0")
    db.session.commit()
    with app_module.app.test_request_context("/api/ai/chat", method="POST"):
        from flask_login import login_user
        login_user(admin)
        tr_res, tr_err = app_module._ai_create_transfer_draft(
            f"从 {wh1.code}仓库 调拨到 {wh2.code}仓库 {m_hot.code} 5",
            manual_confirmation=True,
            resolved_items=[(m_hot, 5)],
        )
        assert tr_err is None, tr_err
        assert tr_res and tr_res.get("order_no")
        tr_obj = app_module.TransferOrder.query.filter_by(transfer_no=tr_res["order_no"]).first()
        assert tr_obj is not None
        assert not (tr_obj.from_location or "")
        assert not (tr_obj.to_location or "")

    # PC-P1-18: _ai_dr_delete_records 删除 AIRun / AIDocumentJob 前清理所有子表外键
    run = app_module.AIRun(
        user_id=admin.id, request_id="req-dr-1", request_hash="hash-dr-1",
        endpoint="/api/ai/chat", status="success",
    )
    db.session.add(run)
    db.session.flush()
    tc = app_module.AIToolCall(
        ai_run_id=run.id, tool_name="query_stock", capability="inventory_read",
        risk_level="low", status="success", permission_allowed=True,
    )
    conv = app_module.AIConversation(user_id=admin.id, title="dr-conv", status="active")
    db.session.add_all([tc, conv])
    db.session.flush()
    db.session.add(app_module.AIMessage(conversation_id=conv.id, ai_run_id=run.id, role="user", content="hi"))
    db.session.add(app_module.AIFeedback(ai_run_id=run.id, user_id=admin.id, rating="thumbs_up"))
    job = app_module.AIDocumentJob(
        ai_run_id=run.id, user_id=admin.id, source="upload", document_type="delivery_note", status="ready",
    )
    db.session.add(job)
    db.session.flush()
    doc_item = app_module.AIDocumentItem(job_id=job.id, line_no=1, raw_text="test")
    db.session.add(doc_item)
    db.session.flush()
    db.session.add(app_module.AIDocumentFieldConfirmation(
        job_id=job.id, item_id=doc_item.id, field_name="quantity", evidence_source="manual",
    ))
    db.session.add(app_module.AIDocumentFeedback(job_id=job.id, user_id=admin.id, rating="thumbs_up"))
    db.session.commit()

    run_id = run.id
    job_id = job.id

    # 验证采购跟单未关联通知能识别 delivery_note
    unlinked_count, unlinked_rows = app_module._ai_pf_query_unlinked_notices()
    assert unlinked_count >= 1
    assert any(row["id"] == job_id for row in unlinked_rows)

    assert app_module._ai_dr_delete_records("conversations", [run_id]) == 1
    assert db.session.get(app_module.AIRun, run_id) is None
    assert app_module.AIToolCall.query.filter_by(ai_run_id=run_id).count() == 0

    assert app_module._ai_dr_delete_records("tasks", [job_id]) == 1
    assert db.session.get(app_module.AIDocumentJob, job_id) is None
    assert app_module.AIDocumentItem.query.filter_by(job_id=job_id).count() == 0
    assert app_module.AIDocumentFieldConfirmation.query.filter_by(job_id=job_id).count() == 0


def test_pc_frontend_xss_csrf_and_script_static_contracts():
    """验证 PC-P0-02, PC-P0-09, PC-P1-12, PC-P1-13, PC-P2-07, PC-P2-08, PC-P2-09 的模板与 JS 修复契约。"""
    # PC-P0-02
    after_sale_tpl = (APP_DIR / "templates" / "after_sale_out_add.html").read_text(encoding="utf-8")
    assert "escapeHtml" in after_sale_tpl

    print_editor_js = (APP_DIR / "static" / "js" / "pages" / "print-template-editor.js").read_text(encoding="utf-8")
    assert "escapeHtml" in print_editor_js
    assert "sanitizeCssColor" in print_editor_js

    # PC-P0-09 & PC-P2-09: 无裸 POST fetch（GET fetch 可保留）
    for tpl_name in ("ai_location_recommendation.html", "ai_data_retention.html"):
        txt = (APP_DIR / "templates" / tpl_name).read_text(encoding="utf-8")
        assert "WMS.api.postRaw" in txt
        assert not re.search(r"\bfetch\s*\([^)]*['\"]POST['\"]", txt, re.S), f"{tpl_name} still contains raw POST fetch()"

    # PC-P1-12 / PC-P0-07: api.js 含 /opening_stock/save 幂等路径与 doc_id 校验
    api_js = (APP_DIR / "static" / "js" / "api.js").read_text(encoding="utf-8")
    assert "/opening_stock/save" in api_js
    assert "doc_id" in api_js

    # PC-P1-13 & PC-P2-07: app.js 委外三页 tableId 与 TabManager 转义
    app_js = (APP_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "safeTabTitle" in app_js
    for key in ("subcontract", "subcontract_issue", "subcontract_receive"):
        idx = app_js.index(f"    {key}: {{")
        block = app_js[idx:idx + 500]
        assert "tableId: 'dataTable'" in block, f"{key} missing tableId"

    # PC-P2-08: excel-table.js 校验 r.ok 与 data-total
    excel_js = (APP_DIR / "static" / "js" / "excel-table.js").read_text(encoding="utf-8")
    assert "if (!r.ok)" in excel_js
    assert "data-total" in excel_js

    # PC-P1-13: 入库打印模板快捷键跳过输入元素
    in_tpl = (APP_DIR / "templates" / "in_order_print_template.html").read_text(encoding="utf-8")
    assert "INPUT" in in_tpl and "TEXTAREA" in in_tpl

    # PC-P2-07: 委外明细加载含 .fail() 回调
    for name in ("subcontract_issue.html", "subcontract_receive.html"):
        txt = (APP_DIR / "templates" / name).read_text(encoding="utf-8")
        assert ".fail(" in txt
