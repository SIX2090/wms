# -*- coding: utf-8 -*-
"""2026-11-26 全量审计 P1 轻量防误判修复与仓库卫生回归测试。

遵守 A12 / R7：禁止模块顶层裸 app_context().push()；全部在函数级隔离内存库夹具中运行。
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import sys
from types import SimpleNamespace as NS

from flask import g
from jinja2 import Environment, FileSystemLoader
import pytest
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def _login_as(wms, user):
    client = wms.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
    return client


@pytest.fixture
def env():
    import app as wms

    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    with wms.app.app_context():
        assert str(wms.db.engine.url) == "sqlite:///:memory:"
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()

        users = {}
        for role in ("admin", "warehouse", "purchase", "finance", "viewer", "user"):
            u = wms.User(
                username=f"audit_p1_{role}",
                password_hash=generate_password_hash("fixture-only"),
                role=role,
                must_change_password=False,
            )
            wms.db.session.add(u)
            users[role] = u
        wh1 = wms.Warehouse(code="WH-A1", name="审计测试一仓", status="active", is_default=True)
        unit = wms.Unit(code="PCS", name="个")
        dept = wms.Department(code="D01", name="生产部")
        supplier = wms.Supplier(code="SUP-A1", name="测试供应商甲")
        wms.db.session.add_all([wh1, unit, dept, supplier])
        wms.db.session.flush()

        mat = wms.Material(
            code="MAT-A1",
            name="审计测试物料",
            spec="S-01",
            unit_id=unit.id,
            price=10.0,
            stock=0.0,
        )
        wms.db.session.add(mat)
        wms.db.session.commit()

        ctx = {
            "users": users,
            "wh1": wh1,
            "unit": unit,
            "dept": dept,
            "supplier": supplier,
            "mat": mat,
            "client": _login_as(wms, users["admin"]),
        }
        yield wms, ctx
        wms.db.session.remove()


def test_d01_summary_excludes_pending_drafts_by_default(env):
    """D-01：/report/api/summary 默认仅统计已完成单据，显式 status=all 才包含草稿；前端下拉对齐。"""
    wms, ctx = env
    wh1, mat, admin, dept = ctx["wh1"], ctx["mat"], ctx["users"]["admin"], ctx["dept"]

    completed_in = wms.InOrder(
        order_no="IN-D01-DONE",
        date=date(2026, 11, 20),
        warehouse=wh1.name,
        business_type="采购入库",
        status="completed",
        operator_id=admin.id,
    )
    pending_in = wms.InOrder(
        order_no="IN-D01-DRAFT",
        date=date(2026, 11, 20),
        warehouse=wh1.name,
        business_type="采购入库",
        status="pending",
        operator_id=admin.id,
    )
    pending_out = wms.OutOrder(
        order_no="OUT-D01-DRAFT",
        date=date(2026, 11, 20),
        warehouse=wh1.name,
        business_type="领料单",
        status="pending",
        operator_id=admin.id,
        department_id=dept.id,
    )
    wms.db.session.add_all([completed_in, pending_in, pending_out])
    wms.db.session.flush()
    wms.db.session.add_all([
        wms.InOrderItem(in_order_id=completed_in.id, material_id=mat.id, quantity=10, price=10.0, amount=100.0),
        wms.InOrderItem(in_order_id=pending_in.id, material_id=mat.id, quantity=50, price=10.0, amount=500.0),
        wms.OutOrderItem(out_order_id=pending_out.id, material_id=mat.id, quantity=30, price=10.0, amount=300.0),
    ])
    wms.db.session.commit()

    resp_default = ctx["client"].get("/report/api/summary", query_string={"warehouse_id": wh1.id})
    assert resp_default.status_code == 200
    body_default = resp_default.get_json()
    assert body_default["status"] == "success"
    assert body_default["summary"]["quantity"] == pytest.approx(10.0)
    assert body_default["summary"]["amount"] == pytest.approx(100.0)

    resp_all = ctx["client"].get("/report/api/summary", query_string={"warehouse_id": wh1.id, "status": "all"})
    assert resp_all.status_code == 200
    body_all = resp_all.get_json()
    assert body_all["summary"]["quantity"] == pytest.approx(90.0)
    assert body_all["summary"]["amount"] == pytest.approx(900.0)

    resp_pending = ctx["client"].get("/report/api/summary", query_string={"warehouse_id": wh1.id, "status": "pending"})
    assert resp_pending.status_code == 200
    assert resp_pending.get_json()["summary"]["quantity"] == pytest.approx(80.0)

    resp_bad = ctx["client"].get("/report/api/summary", query_string={"warehouse_id": wh1.id, "status": "invalid"})
    assert resp_bad.status_code == 400

    daily_html = ctx["client"].get("/report/view/summary?summary_view=daily").get_data(as_text=True)
    assert '<option value="completed" selected>已完成</option>' in daily_html
    assert '<option value="all">全部（含草稿）</option>' in daily_html


def test_b02_revert_po_linked_in_order_returns_reservation_hint(env):
    """B-02：采购关联入库单反提交/批量反提交返回预留未释放提示；无采购来源不误报预留。"""
    wms, ctx = env
    wh1, mat, admin, supplier = ctx["wh1"], ctx["mat"], ctx["users"]["admin"], ctx["supplier"]

    po = wms.PurchaseOrder(
        order_no="PO-B02-001",
        date=date(2026, 11, 20),
        supplier_id=supplier.id,
        status="partial",
        operator_id=admin.id,
    )
    wms.db.session.add(po)
    wms.db.session.flush()
    po_item = wms.PurchaseOrderItem(
        purchase_order_id=po.id,
        material_id=mat.id,
        quantity=20.0,
        received_quantity=10.0,
        price=10.0,
        amount=200.0,
    )
    wms.db.session.add(po_item)
    wms.db.session.flush()

    linked_order = wms.InOrder(
        order_no="IN-B02-LINKED",
        date=date(2026, 11, 21),
        warehouse=wh1.name,
        business_type="采购入库",
        supplier_id=supplier.id,
        source_purchase_order_id=po.id,
        status="pending",
        operator_id=admin.id,
    )
    plain_order = wms.InOrder(
        order_no="IN-B02-PLAIN",
        date=date(2026, 11, 21),
        warehouse=wh1.name,
        business_type="其他入库",
        status="pending",
        operator_id=admin.id,
    )
    wms.db.session.add_all([linked_order, plain_order])
    wms.db.session.flush()
    wms.db.session.add_all([
        wms.InOrderItem(
            in_order_id=linked_order.id,
            material_id=mat.id,
            quantity=10.0,
            price=10.0,
            amount=100.0,
            source_purchase_order_item_id=po_item.id,
        ),
        wms.InOrderItem(
            in_order_id=plain_order.id,
            material_id=mat.id,
            quantity=5.0,
            price=10.0,
            amount=50.0,
        ),
    ])
    wms.db.session.commit()

    assert ctx["client"].post(f"/in_order/{linked_order.id}/complete", json={"force": True}).get_json()["status"] == "success"
    assert ctx["client"].post(f"/in_order/{plain_order.id}/complete", json={"force": True}).get_json()["status"] == "success"

    rev_linked = ctx["client"].post(f"/in_order/{linked_order.id}/revert", json={}).get_json()
    assert rev_linked["status"] == "success", rev_linked
    assert "收货预留" in rev_linked["msg"] and "删除草稿" in rev_linked["msg"], rev_linked["msg"]

    rev_plain = ctx["client"].post(f"/in_order/{plain_order.id}/revert", json={}).get_json()
    assert rev_plain["status"] == "success", rev_plain
    assert "收货预留" not in rev_plain["msg"], rev_plain["msg"]

    # 重新完成后验证批量反提交同样返回采购预留提示
    assert ctx["client"].post(f"/in_order/{linked_order.id}/complete", json={"force": True}).get_json()["status"] == "success"
    batch_rev = ctx["client"].post("/in_order/batch_revert", json={"ids": [linked_order.id]}).get_json()
    assert batch_rev["status"] == "success", batch_rev
    assert "收货预留" in batch_rev["msg"] and "删除草稿" in batch_rev["msg"], batch_rev["msg"]


def test_d02_report_view_displays_opening_scope_comparison_note(env):
    """D-02：物料收发存、仓库月报、库存台账页面均明确展示期间内期初建账口径对照说明。"""
    _, ctx = env
    for report_type in ("ledger", "material_movement", "warehouse_monthly"):
        resp = ctx["client"].get(f"/report/view/{report_type}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'id="openingScopeComparisonNotice"' in html, f"{report_type} 缺少期初建账口径对照提示"
        assert "期初建账口径对照" in html
        assert "物料收发存" in html and "仓库月报" in html and "库存台账" in html
        assert 'id="balanceRoundingFootnote"' in html


def test_a01_material_add_displays_opening_stock_hint(env):
    """A-01：新增物料页面初始库存字段旁明确引导通过【期初库存】建账。"""
    _, ctx = env
    resp = ctx["client"].get("/material/add")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'id="material-add-stock-7"' in html
    assert 'id="initialStockOpeningHint"' in html
    assert "期初库存" in html


def test_e02_batch_labels_warns_on_loopback_qr_origin_only(env):
    """E-02：批量标签打印页在二维码网址指向本机回环地址时显示醒目提醒，公网/局域网地址不误报。"""
    _, ctx = env
    mat = ctx["mat"]

    loopback_resp = ctx["client"].get(
        "/label/batch_print",
        query_string={"ids": mat.id, "qr_base_url": "http://127.0.0.1:8080"},
    )
    assert loopback_resp.status_code == 200
    loopback_html = loopback_resp.get_data(as_text=True)
    assert 'id="qrLoopbackWarning"' in loopback_html
    assert "手机扫码将无法打开" in loopback_html
    assert "WMS_PUBLIC_URL" in loopback_html

    for safe_origin in ("https://wms.example", "http://192.168.1.50:8080"):
        safe_resp = ctx["client"].get(
            "/label/batch_print",
            query_string={"ids": mat.id, "qr_base_url": safe_origin},
        )
        assert safe_resp.status_code == 200
        assert 'id="qrLoopbackWarning"' not in safe_resp.get_data(as_text=True)

    jinja_env = Environment(loader=FileSystemLoader(ROOT / "app/templates"), autoescape=True)
    material_row = dict(id=7, code="M1", name="测试", spec="S1", qrcode_png="iVBOR", qrcode="http://localhost:8080/mobile/material?code=M1")
    for base, expect_warn in [
        ("http://localhost:8080", True),
        ("http://[::1]:8080", True),
        ("https://wms.example", False),
        ("", False),
    ]:
        rendered = jinja_env.get_template("print_batch_labels.html").render(
            materials=[material_row],
            materials_data=[material_row],
            default_material_qr=True,
            qr_public_base=base,
            request=NS(args={}),
            current_user=NS(is_authenticated=True),
            config={},
            url_for=lambda *a, **kw: "/fixture",
        )
        assert ('id="qrLoopbackWarning"' in rendered) is expect_warn, f"base={base}"


def test_e01_role_hygiene_and_ai_insights_gate(env):
    """E-01：隐藏无定义角色 user/viewer 下拉、移除死角色 manager、收口 /report/dashboard/ai_insights。"""
    wms, ctx = env
    wh1, users = ctx["wh1"], ctx["users"]

    user_html = ctx["client"].get("/user").get_data(as_text=True)
    add_form = re.search(r'id="addForm"(.*?)</form>', user_html, re.S).group(1)
    edit_form = re.search(r'id="editForm"(.*?)</form>', user_html, re.S).group(1)
    for fragment in (add_form, edit_form):
        assert 'value="user"' not in fragment
        assert 'value="viewer"' not in fragment
        for role in ("warehouse", "purchase", "sales", "production", "finance", "admin"):
            assert f'value="{role}"' in fragment, f"缺少有效角色 {role}"

    approval_roles = getattr(wms.app.view_functions["approval_list"], "_required_roles", set())
    assert "manager" not in approval_roles
    assert {"admin", "purchase"}.issubset(approval_roles)

    ai_roles = getattr(wms.app.view_functions["report_dashboard_ai_insights"], "_required_roles", set())
    assert ai_roles == frozenset({"admin", "warehouse", "purchase", "sales", "production"})

    headers = {"X-Requested-With": "XMLHttpRequest"}
    for blocked_role in ("viewer", "user", "finance"):
        g.pop("_login_user", None)
        c = _login_as(wms, users[blocked_role])
        post_resp = c.post(f"/report/dashboard/ai_insights?warehouse_id={wh1.id}", json={}, headers=headers)
        assert post_resp.status_code == 403, f"{blocked_role} 应被拒绝，实际 {post_resp.status_code}"
        dash_html = c.get(f"/report/dashboard?warehouse_id={wh1.id}").get_data(as_text=True)
        assert "aiInsightsBtn" not in dash_html, f"{blocked_role} 不应看到 AI解读按钮"
        assert "function requestAiInsights" not in dash_html, f"{blocked_role} 按钮与函数同隐不变量"

    for allowed_role in ("admin", "warehouse"):
        g.pop("_login_user", None)
        c = _login_as(wms, users[allowed_role])
        post_resp = c.post(f"/report/dashboard/ai_insights?warehouse_id={wh1.id}", json={}, headers=headers)
        assert post_resp.status_code != 403, f"{allowed_role} 不应被 403 拒绝"
        dash_html = c.get(f"/report/dashboard?warehouse_id={wh1.id}").get_data(as_text=True)
        assert "aiInsightsBtn" in dash_html and "function requestAiInsights" in dash_html


def test_f04_no_leftover_backup_or_probe_files():
    """F-04：路由目录下无历史 .bak_* 备份残留，app/logs 下无一次性调试探针脚本。"""
    leftovers = [
        ROOT / "app/routes/customer.py.bak_p2b",
        ROOT / "app/routes/stock_query.py.bak_p1",
        ROOT / "app/routes/supplier.py.bak_p2b",
        ROOT / "app/routes/unit_supplier_import.py.bak_p2b",
        ROOT / "app/logs/flow_logic_probe.py",
        ROOT / "app/logs/run_toolbar_audit_server.py",
    ]
    existing = [str(p.relative_to(ROOT)) for p in leftovers if p.exists()]
    assert existing == [], f"存在未清理残留文件：{existing}"
