# -*- coding: utf-8 -*-
"""BUG-2026-11-27-006 回归测试：采购入库第三批导入、编辑/复制/批反审、权限与价格维度收口及同类点排查。

Part A（纯 AST / 静态契约，本地与 Linux CI 均执行，支持 R8 文件备份回退验证）：
- P1-BIZ-1 + R6：import_in_order / import_out_order 补齐 total_amount 重算、空单清理、
  BadZipFile/InvalidFileException 拦截、import_max_rows、未来日期拒绝、负单价/负金额跳过、
  主数据自动建档净化与长度预检、log_operation + log_audit 审计、去除重复工程名称分支及
  其他入库仅客供必填客户口径对齐
- P1-BIZ-2/3/4：update_in_order 先全量校验再写回并统一 rollback；copy_in_order 四业务类型前缀与
  停用物料拦截；add_in_order 表单 items_json 编辑替换不翻倍且批量预加载物料去 N+1；
  update_in_order_item / copy_in_order_to_out / batch_revert_in_order 补操作日志；
  batch_revert_in_order 去异常泄漏且 reverted==0 不再假成功；print_in_order_labels 预加载消除 N+1
- P1-BIZ-5 + R6：in_order_add_page / out_order_add_page 补 @require_role('warehouse')；
  export_in_order / export_single_in_order / export_out_order / export_single_out_order 补角色门禁；
  7 处入出库导出与打印遵循 price_dimension_enabled()

Part B（完整 Flask + SQLite 端到端集成测试，于隔离 Linux CI 运行）。
"""
from __future__ import annotations

import ast
import io
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
IN_ORDER_PY = ROOT / "app" / "routes" / "in_order.py"
OUT_ORDER_PY = ROOT / "app" / "routes" / "out_order.py"
EXPORT_PY = ROOT / "app" / "routes" / "export.py"
BATCH_IMPORT_PY = ROOT / "app" / "routes" / "batch_import.py"

_IS_LINUX_ISOLATED = sys.platform.startswith("linux") or os.environ.get("WMS_RUN_FULL_INTEGRATION") == "1"


def _get_func(path: Path, name: str) -> tuple[ast.FunctionDef, str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = src.splitlines()
            body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
            return node, body
    raise AssertionError(f"Function {name} not found in {path}")


def _decorator_calls(func: ast.FunctionDef) -> list[str]:
    calls = []
    for dec in func.decorator_list:
        if isinstance(dec, ast.Call):
            calls.append(ast.unparse(dec))
        else:
            calls.append(ast.unparse(dec))
    return calls


# ==================== Part A: 纯静态 / AST 回归 ====================


def test_p1_biz_1_batch_import_guards_totals_and_audit_ast():
    """P1-BIZ-1 + R6: import_in_order and import_out_order enforce totals, limits, dates, nonneg prices, and audit."""
    for fn_name in ("import_in_order", "import_out_order"):
        _, body = _get_func(BATCH_IMPORT_PY, fn_name)
        assert "InvalidFileException" in body and "zipfile.BadZipFile" in body, f"{fn_name} missing .xls guard"
        assert "import_max_rows()" in body, f"{fn_name} missing import_max_rows limit"
        assert "is_future_date(date_val)" in body, f"{fn_name} missing future date rejection"
        assert "recalculate_order_total(current_order)" in body, f"{fn_name} missing total_amount recalc"
        assert "db.session.delete(current_order)" in body, f"{fn_name} missing empty order cleanup"
        assert "log_operation(" in body and "log_audit(" in body, f"{fn_name} missing audit logging"
        assert "sanitize_text_input(" in body, f"{fn_name} missing master data text sanitization"
        assert "max(0, prc)" not in body and "max(0, amt)" not in body, f"{fn_name} must skip negative price/amount, not clamp"

    _, in_body = _get_func(BATCH_IMPORT_PY, "import_in_order")
    assert in_body.count("elif '工程名称' in h:") == 1, "Duplicate 工程名称 elif branch must be removed"
    assert "if business_type == '其他入库' and row_customer_supplied and not customer_name:" in in_body
    assert "if business_type == '其他入库' and not customer_name:" not in in_body

    # Direct behavioral verification of _parse_nonneg_import_number (failure & boundary cases)
    import math as _math
    _, helper_src = _get_func(BATCH_IMPORT_PY, "_parse_nonneg_import_number")
    ns = {"math": _math, "round_to_2_decimals": lambda v: round(float(v), 2)}
    exec(compile(helper_src, str(BATCH_IMPORT_PY), "exec"), ns)
    parse_fn = ns["_parse_nonneg_import_number"]
    assert parse_fn({"price": 0}, [-5], "price", "单价") == (None, "单价不能小于 0")
    assert parse_fn({"price": 0}, ["nan"], "price", "单价") == (None, "单价不能小于 0")
    assert parse_fn({"price": 0}, ["inf"], "price", "单价") == (None, "单价不能小于 0")
    assert parse_fn({"price": 0}, ["abc"], "price", "单价") == (None, "单价格式不正确")
    assert parse_fn({"price": 0}, [""], "price", "单价") == (0.0, None)
    assert parse_fn({"price": 0}, [12.345], "price", "单价") == (12.35, None)


def test_p1_biz_2_3_4_update_copy_add_batch_revert_and_n_plus_1_ast():
    """P1-BIZ-2/3/4: atomic update_in_order, 4-prefix copy + inactive guard, form items_json replace, N+1 & audit."""
    _, upd_body = _get_func(IN_ORDER_PY, "update_in_order")
    assert "def fail(message, code=400):" in upd_body and "db.session.rollback()" in upd_body
    # All validation (including assert_warehouse_active) must occur before mutating order.supplier_id
    assert upd_body.index("assert_warehouse_active(warehouse") < upd_body.index("order.supplier_id = new_supplier_id")

    _, copy_body = _get_func(IN_ORDER_PY, "copy_in_order")
    assert "'其他入库': 'OI'" in copy_body and "'销售退货入库': 'SR'" in copy_body
    assert "getattr(item.material, 'status', None) == 'inactive'" in copy_body

    _, add_body = _get_func(IN_ORDER_PY, "add_in_order")
    assert "Material.code.in_(requested_codes)" in add_body, "add_in_order should batch-preload materials"
    assert "if items_data and order.id:" in add_body
    assert "if request.is_json and items_data and order.id:" not in add_body

    _, upd_item_body = _get_func(IN_ORDER_PY, "update_in_order_item")
    assert "log_operation(" in upd_item_body

    _, copy_out_body = _get_func(IN_ORDER_PY, "copy_in_order_to_out")
    assert "log_operation(" in copy_out_body

    _, rev_body = _get_func(IN_ORDER_PY, "batch_revert_in_order")
    assert "log_operation('批量反提交入库单'" in rev_body
    assert "错误: {e}" not in rev_body, "batch_revert_in_order must not leak raw exception strings"
    assert "if not orders:" in rev_body and "'status': 'error'" in rev_body

    _, lbl_body = _get_func(IN_ORDER_PY, "print_in_order_labels")
    assert "joinedload(InOrderItem.material)" in lbl_body
    assert "price_dimension_enabled()" in lbl_body


def test_p1_biz_5_roles_and_price_dimension_gates_ast():
    """P1-BIZ-5 + R6: add pages gate viewer/user; exports require proper roles and honor price_dimension_enabled."""
    in_add_fn, _ = _get_func(IN_ORDER_PY, "in_order_add_page")
    assert any("require_role('warehouse', 'production')" in d for d in _decorator_calls(in_add_fn))

    out_add_fn, _ = _get_func(OUT_ORDER_PY, "out_order_add_page")
    assert any("require_role('warehouse', 'production')" in d for d in _decorator_calls(out_add_fn))

    exp_in_fn, exp_in_body = _get_func(EXPORT_PY, "export_in_order")
    assert "from utils import require_role" in EXPORT_PY.read_text(encoding="utf-8")
    assert any("require_role('warehouse', 'finance', 'purchase')" in d for d in _decorator_calls(exp_in_fn))
    assert "price_dimension_enabled()" in exp_in_body

    exp_single_in_fn, exp_single_in_body = _get_func(IN_ORDER_PY, "export_single_in_order")
    assert any("require_role('warehouse', 'finance', 'purchase')" in d for d in _decorator_calls(exp_single_in_fn))
    assert "price_dimension_enabled()" in exp_single_in_body

    _, batch_exp_body = _get_func(IN_ORDER_PY, "batch_export_in_order")
    assert "price_dimension_enabled()" in batch_exp_body

    _, build_xl_body = _get_func(IN_ORDER_PY, "_build_in_order_excel")
    assert "price_dimension_enabled" in build_xl_body

    exp_out_fn, _ = _get_func(OUT_ORDER_PY, "export_out_order")
    assert any("require_role('warehouse', 'finance', 'sales', 'purchase')" in d for d in _decorator_calls(exp_out_fn))

    exp_single_out_fn, exp_single_out_body = _get_func(OUT_ORDER_PY, "export_single_out_order")
    assert any("require_role('warehouse', 'finance', 'sales', 'purchase')" in d for d in _decorator_calls(exp_single_out_fn))
    assert "price_dimension_enabled()" in exp_single_out_body
    assert "selectinload(OutOrder.items)" in exp_single_out_body


# ==================== Part B: 完整隔离 Flask + SQLite 端到端回归 ====================


def _make_xlsx(rows: list[list]) -> io.BytesIO:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _setup_env():
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import app as w

    w.app.config["TESTING"] = True
    w.app.config["WTF_CSRF_ENABLED"] = False
    w.db.session.remove()
    w.db.drop_all()
    w.db.create_all()

    users = {}
    for role in ("admin", "warehouse", "finance", "viewer"):
        u = w.User(username=f"b3_{role}", role=role, password_hash="unused", must_change_password=False)
        w.db.session.add(u)
        w.db.session.flush()
        users[role] = u.id

    wh = w.Warehouse(code="B3-WH", name="三批仓", status="active", is_default=True)
    unit = w.Unit(code="B3-U", name="个")
    sup = w.Supplier(code="B3-S", name="三批供应商")
    cust = w.Customer(code="B3-C", name="三批客户")
    w.db.session.add_all([wh, unit, sup, cust])
    w.db.session.flush()

    m_ok = w.Material(code="B3-M1", name="有效物料", unit_id=unit.id, stock=0, price=11, status="active")
    m_off = w.Material(code="B3-MOFF", name="停用物料", unit_id=unit.id, stock=0, price=9, status="inactive")
    w.db.session.add_all([m_ok, m_off])
    w.db.session.commit()

    def client_as(role="admin"):
        from flask import g
        g.pop("_login_user", None)
        c = w.app.test_client()
        with c.session_transaction() as sess:
            sess["_user_id"] = str(users[role])
            sess["_fresh"] = True
        return c

    return w, client_as, {
        "wh": wh.id, "wh_name": wh.name, "sup": sup.id, "cust": cust.id,
        "m_ok": m_ok.id, "m_off": m_off.id,
    }


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask+SQLite integration runs in isolated Linux CI")
def test_import_in_and_out_orders_totals_guards_and_audit():
    """P1-BIZ-1 + R6 integration: import_in_order & import_out_order totals, guards, other-in rule, .xls & audit."""
    with _setup_ctx() as (w, client_as, ids):
        c = client_as("admin")
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # 1. Corrupt / legacy .xls returns friendly 400
        r_xls = c.post(
            "/import/in_order",
            data={"file": (io.BytesIO(b"not-a-zip-legacy-xls"), "old.xlsx")},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )
        assert r_xls.status_code == 400 and "另存为 .xlsx" in r_xls.get_json()["msg"]

        # 2. Valid purchase_in + valid self-owned other_in + invalid rows (future date, negative price, supplied w/o cust)
        buf = _make_xlsx([
            ["单据编号", "日期", "业务类型", "仓库", "供应商", "客户", "物料编码", "物料名称", "数量", "单价", "客供"],
            ["IMP-IN-1", today, "采购入库", ids["wh_name"], "三批供应商", "", "B3-M1", "有效物料", 5, 11, "否"],
            ["IMP-IN-2", today, "其他入库", ids["wh_name"], "", "", "B3-M1", "有效物料", 2, 10, "否"],
            ["IMP-IN-FUT", tomorrow, "采购入库", ids["wh_name"], "三批供应商", "", "B3-M1", "有效物料", 1, 5, "否"],
            ["IMP-IN-NEG", today, "采购入库", ids["wh_name"], "三批供应商", "", "B3-M1", "有效物料", 1, -3, "否"],
            ["IMP-IN-SUP", today, "其他入库", ids["wh_name"], "", "", "B3-M1", "有效物料", 1, 5, "是"],
        ])
        r_in = c.post("/import/in_order", data={"file": (buf, "in.xlsx")}, headers={"X-Requested-With": "XMLHttpRequest"})
        assert r_in.status_code == 200 and r_in.get_json()["count"] == 2, r_in.get_json()
        o1 = w.InOrder.query.filter_by(order_no="IMP-IN-1").one()
        o2 = w.InOrder.query.filter_by(order_no="IMP-IN-2").one()
        assert o1.total_amount == 55.0
        assert o2.total_amount == 20.0 and o2.customer_id is None
        assert w.InOrder.query.filter_by(order_no="IMP-IN-FUT").first() is None
        assert w.InOrder.query.filter_by(order_no="IMP-IN-NEG").first() is None
        assert w.InOrder.query.filter_by(order_no="IMP-IN-SUP").first() is None
        assert w.OperationAudit.query.filter_by(operation="batch_import_in_order").count() == 1
        assert w.OperationLog.query.filter_by(operation_type="批量导入入库单").count() == 1

        # 3. R6 peer: import_out_order recalculates total_amount, skips negative price & cleans up empty orphan order
        out_buf = _make_xlsx([
            ["单据编号", "日期", "仓库", "物料编码", "物料名称", "数量", "单价"],
            ["IMP-OUT-1", today, ids["wh_name"], "B3-M1", "有效物料", 3, 12],
            ["IMP-OUT-BAD", today, ids["wh_name"], "B3-M1", "有效物料", 2, -4],
        ])
        r_out = c.post("/import/out_order", data={"file": (out_buf, "out.xlsx")}, headers={"X-Requested-With": "XMLHttpRequest"})
        assert r_out.status_code == 200 and r_out.get_json()["count"] == 1, r_out.get_json()
        oo1 = w.OutOrder.query.filter_by(order_no="IMP-OUT-1").one()
        assert oo1.total_amount == 36.0
        assert w.OutOrder.query.filter_by(order_no="IMP-OUT-BAD").first() is None
        assert w.OperationAudit.query.filter_by(operation="batch_import_out_order").count() == 1


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask+SQLite integration runs in isolated Linux CI")
def test_update_copy_form_edit_and_batch_revert_behaviors():
    """P1-BIZ-2/3/4 integration: atomic update, 4-prefix copy + inactive block, form items_json, batch_revert."""
    import json as _json
    from tests.document_revision_client import document_post

    with _setup_ctx() as (w, client_as, ids):
        c = client_as("admin")
        today = date.today().isoformat()

        # Create draft via JSON, then edit via form items_json -> must replace, not duplicate
        r_create = c.post("/in_order/add", json={
            "business_type": "采购入库", "warehouse_id": ids["wh"], "supplier_id": ids["sup"], "date": today,
            "items": [{"code": "B3-M1", "quantity": 2, "price": 10}],
        })
        oid = r_create.get_json()["id"]
        r_form_edit = document_post(c, "/in_order/add", data={
            "order_id": str(oid), "business_type": "采购入库", "warehouse_id": str(ids["wh"]),
            "supplier_id": str(ids["sup"]), "date": today,
            "items_json": _json.dumps([{"code": "B3-M1", "quantity": 4, "price": 15}]),
        })
        assert r_form_edit.status_code == 200, r_form_edit.get_json()
        w.db.session.expire_all()
        order = w.db.session.get(w.InOrder, oid)
        assert len(order.items) == 1 and order.items[0].quantity == 4 and order.total_amount == 60.0

        # update_in_order with invalid warehouse rolls back and keeps original remark/supplier
        order.remark = "ORIG-REMARK"
        w.db.session.commit()
        r_bad_upd = document_post(c, f"/in_order/{oid}/update", json={
            "date": today, "supplier_id": None, "warehouse": "不存在仓库", "remark": "MUTATED",
        })
        assert r_bad_upd.status_code == 400
        w.db.session.expire_all()
        reloaded = w.db.session.get(w.InOrder, oid)
        assert reloaded.supplier_id == ids["sup"] and reloaded.remark == "ORIG-REMARK"

        # copy_in_order uses OI for 其他入库 and blocks inactive materials
        oi = w.InOrder(order_no="OI-SRC-1", date=date.today(), business_type="其他入库", warehouse=ids["wh_name"], status="pending")
        w.db.session.add(oi)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=oi.id, material_id=ids["m_ok"], quantity=2, price=5, amount=10))
        w.db.session.commit()
        r_copy = c.post(f"/in_order/{oi.id}/copy")
        assert r_copy.status_code == 200 and r_copy.get_json()["order_no"].startswith("OI")

        inact_order = w.InOrder(order_no="IN-OFF-1", date=date.today(), business_type="采购入库", supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending")
        w.db.session.add(inact_order)
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=inact_order.id, material_id=ids["m_off"], quantity=1, price=5, amount=5))
        w.db.session.commit()
        r_copy_off = c.post(f"/in_order/{inact_order.id}/copy")
        assert r_copy_off.status_code == 400 and "已停用" in r_copy_off.get_json()["msg"]

        # batch_revert_in_order: nonexistent -> 400 error; pending skipped -> 200 reverted=0 w/ skipped; completed -> success + log
        r_none = c.post("/in_order/batch_revert", json={"ids": [999999]})
        assert r_none.status_code == 400 and r_none.get_json()["status"] == "error"
        r_skip = c.post("/in_order/batch_revert", json={"ids": [oid]})
        assert r_skip.status_code == 200 and r_skip.get_json()["reverted"] == 0 and r_skip.get_json()["skipped"]
        assert c.post(f"/in_order/{oid}/complete?force=1").get_json()["status"] == "success"
        r_rev = c.post("/in_order/batch_revert", json={"ids": [oid]})
        assert r_rev.status_code == 200 and r_rev.get_json()["status"] == "success" and r_rev.get_json()["reverted"] == 1
        assert w.OperationLog.query.filter_by(operation_type="批量反提交入库单", target_id=oid).count() == 1


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask+SQLite integration runs in isolated Linux CI")
def test_roles_and_price_dimension_on_exports():
    """P1-BIZ-5 + R6 integration: viewer blocked on add/exports; finance allowed on exports; price toggle enforced."""
    from openpyxl import load_workbook

    with _setup_ctx() as (w, client_as, ids):
        in_o = w.InOrder(order_no="IN-P5-1", date=date.today(), business_type="采购入库", supplier_id=ids["sup"], warehouse=ids["wh_name"], status="pending")
        out_o = w.OutOrder(order_no="OU-P5-1", date=date.today(), business_type="领料单", warehouse=ids["wh_name"], status="pending")
        w.db.session.add_all([in_o, out_o])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=in_o.id, material_id=ids["m_ok"], quantity=2, price=11, amount=22))
        w.db.session.add(w.OutOrderItem(out_order_id=out_o.id, material_id=ids["m_ok"], quantity=2, price=11, amount=22))
        w.db.session.commit()

        viewer = client_as("viewer")
        for url in ("/in_order/add", "/out_order/add", f"/in_order/export?warehouse_id={ids['wh']}",
                    f"/in_order/{in_o.id}/export", f"/out_order/export?warehouse_id={ids['wh']}", f"/out_order/{out_o.id}/export"):
            assert viewer.get(url).status_code in (302, 403), f"viewer must be blocked on {url}"

        finance = client_as("finance")
        assert finance.post("/in_order/add", json={"business_type": "采购入库"}).status_code in (302, 403)
        assert finance.post("/out_order/add", json={"business_type": "领料单"}).status_code in (302, 403)
        for url in (f"/in_order/export?warehouse_id={ids['wh']}", f"/in_order/{in_o.id}/export",
                    f"/out_order/export?warehouse_id={ids['wh']}", f"/out_order/{out_o.id}/export"):
            assert finance.get(url).status_code == 200, f"finance must be allowed on {url}"

        from flask import g
        admin = client_as("admin")
        # price_dimension_enabled = 0 (default): /in_order/export omits price/amount headers; single/batch blank cells
        w.set_system_setting("price_dimension_enabled", "0")
        w.db.session.commit()
        g.pop("_system_setting_cache", None)
        ws_list_off = load_workbook(io.BytesIO(admin.get(f"/in_order/export?warehouse_id={ids['wh']}").data)).active
        hdr_off = [c.value for c in ws_list_off[1]]
        assert "单价" not in hdr_off and "金额" not in hdr_off
        ws_single_off = load_workbook(io.BytesIO(admin.get(f"/in_order/{in_o.id}/export").data)).active
        s_hdr = [c.value for c in ws_single_off[1]]
        assert ws_single_off.cell(2, s_hdr.index("单价") + 1).value in (None, "")
        assert ws_single_off.cell(2, s_hdr.index("金额") + 1).value in (None, "")

        # price_dimension_enabled = 1: headers & numeric price/amount appear
        w.set_system_setting("price_dimension_enabled", "1")
        w.db.session.commit()
        g.pop("_system_setting_cache", None)
        ws_list_on = load_workbook(io.BytesIO(admin.get(f"/in_order/export?warehouse_id={ids['wh']}").data)).active
        hdr_on = [c.value for c in ws_list_on[1]]
        assert "单价" in hdr_on and "金额" in hdr_on
        ws_single_on = load_workbook(io.BytesIO(admin.get(f"/in_order/{in_o.id}/export").data)).active
        assert float(ws_single_on.cell(2, s_hdr.index("单价") + 1).value) == 11.0
        assert float(ws_single_on.cell(2, s_hdr.index("金额") + 1).value) == 22.0


from contextlib import contextmanager


@contextmanager
def _setup_ctx():
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import app as w

    with w.app.app_context():
        yield _setup_env()
