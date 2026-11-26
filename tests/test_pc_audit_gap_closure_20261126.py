# -*- coding: utf-8 -*-
"""BUG-2026-11-26-006 纯单元与源码契约回归测试（不导入 app，可在本地受限环境与 CI 双跑）。

覆盖 4 项审计遗漏子项补齐：
1. PC-P1-05：batch_delete_opening_stock_lines 纳入 document_edit_guard.EDIT_ENDPOINTS
2. PC-P1-06：sales_report_print 与 sales.py 默认口径排除 draft 销售订单
3. PC-P2-01：print_fill / report_print_preview / doc_print_excel 订单级与标题单元格防公式注入
4. PC-P2-07：委外三页及同类列表页移除重复内联 .sortable-header 排序监听
"""
from __future__ import annotations

import ast
import io
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))


def test_pc_p1_05_opening_stock_batch_delete_lines_in_edit_endpoints():
    tree = ast.parse((APP_DIR / "services" / "document_edit_guard.py").read_text(encoding="utf-8-sig"))
    endpoints = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "EDIT_ENDPOINTS":
                    endpoints = ast.literal_eval(node.value.args[0])
    assert endpoints is not None
    assert "batch_delete_opening_stock_lines" in endpoints


def test_pc_p2_01_print_fill_order_level_cells_stay_literal_text_and_keep_template_formulas():
    from print_fill import _Filler

    # 1) 纯订单级模板：订单头字段含 =CMD|... 必须写为 data_type='s'，且模板自身 =SUM 公式保持 data_type='f'
    order = SimpleNamespace(
        order_no="IN-SEC-1",
        remark="=CMD|' /C calc'!A0",
        customer=SimpleNamespace(name="=HYPERLINK(\"https://evil.test\")"),
        total_amount=10,
    )
    wb_order_only = Workbook()
    ws = wb_order_only.active
    ws["A1"] = "{order.customer.name}"
    ws["B1"] = "备注：{order.remark}"
    ws["C1"] = 10
    ws["D1"] = "=SUM(C1:C1)"
    _Filler(order, [], "2026-11-26").fill(ws)

    assert ws["A1"].value == '=HYPERLINK("https://evil.test")'
    assert ws["A1"].data_type == "s"
    assert ws["B1"].value == "备注：=CMD|' /C calc'!A0"
    assert ws["B1"].data_type == "s"
    assert ws["D1"].value == "=SUM(C1:C1)"
    assert ws["D1"].data_type == "f"

    buf = io.BytesIO()
    wb_order_only.save(buf)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        xml = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert "<f>HYPERLINK" not in xml
    assert "<f>SUM(C1:C1)</f>" in xml

    # 2) 含明细行的模板：表头订单字段与明细行字段均保持 data_type='s'
    wb_with_items = Workbook()
    ws2 = wb_with_items.active
    ws2["A1"] = "{order.remark}"
    ws2["A2"] = "{item.remark}"
    ws2["B2"] = "{item.quantity}"
    ws2["B3"] = "=SUM(B2:B2)"
    _Filler(order, [SimpleNamespace(remark="=1+1", quantity=3)], "2026-11-26").fill(ws2)

    assert ws2["A1"].value == "=CMD|' /C calc'!A0" and ws2["A1"].data_type == "s"
    assert ws2["A2"].value == "=1+1" and ws2["A2"].data_type == "s"
    assert ws2["B3"].value == "=SUM(B2:B2)" and ws2["B3"].data_type == "f"

    # 3) preserve_layout 的 _fill_sheet 同样把订单级占位符标为 data_type='s'
    from services.report_print_preview import _fill_sheet

    wb_preserve = Workbook()
    ws3 = wb_preserve.active
    ws3["A1"] = "{order.remark}"
    ws3["A2"] = "{item.remark}"
    ws3["B2"] = "{order.customer.name}"
    _fill_sheet(ws3, _Filler(order, [SimpleNamespace(remark="=2+2", quantity=1)], "2026-11-26"))
    assert ws3["A1"].data_type == "s"
    assert ws3["A2"].data_type == "s"
    assert ws3["B2"].data_type == "s"


def test_pc_p2_01_doc_print_excel_report_title_and_columns_stay_literal_text(tmp_path, monkeypatch):
    import doc_print_excel as dpe

    if "app" not in sys.modules:
        monkeypatch.setitem(
            sys.modules,
            "app",
            SimpleNamespace(_get_report_definition=lambda rt: {"title": "内置报表"}),
        )
    monkeypatch.setattr(dpe, "resolve_excel_template", lambda *a, **k: None)
    columns = [{"field": "code", "title": "=COLUMN_FORMULA()"}, {"field": "qty", "title": "数量"}]
    rows = [{"code": "=CMD|' /C calc'!A0", "qty": 5}]
    result_in = dpe.render_report_excel_print(
        "in_detail", "=TITLE_FORMULA()", columns, rows, static_folder=str(tmp_path),
    )
    assert result_in is not None
    wb_in = load_workbook(result_in[0])
    try:
        ws = wb_in.active
        assert ws["A1"].value == "=TITLE_FORMULA()" and ws["A1"].data_type == "s"
        assert all(cell.data_type != "f" for row in ws.iter_rows() for cell in row)
    finally:
        wb_in.close()

    result_req = dpe.render_report_excel_print(
        "requisition", "领料汇总", columns, rows, static_folder=str(tmp_path),
    )
    assert result_req is not None
    wb_req = load_workbook(result_req[0])
    try:
        ws = wb_req.active
        assert ws["A2"].value == "=COLUMN_FORMULA()" and ws["A2"].data_type == "s"
        assert all(cell.data_type != "f" for row in ws.iter_rows() for cell in row)
    finally:
        wb_req.close()


def test_pc_p2_07_no_duplicate_inline_sortable_header_listeners():
    for rel in (
        "templates/subcontract.html",
        "templates/subcontract_issue.html",
        "templates/subcontract_receive.html",
        "templates/adjustment.html",
        "templates/check.html",
        "templates/requisition.html",
        "templates/transfer.html",
        "static/js/pages/after-sale-out-list.js",
    ):
        text = (APP_DIR / rel).read_text(encoding="utf-8")
        assert "querySelectorAll('.sortable-header')" not in text, (
            f"{rel} 存在与 app.js setupSortableHeaders() 重复的内联排序绑定"
        )
    app_js = (APP_DIR / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "function setupSortableHeaders()" in app_js
    assert "setupSortableHeaders();" in app_js


def test_bug_2026_11_26_007_read_only_roles_include_viewer_and_user():
    tree = ast.parse((APP_DIR / "utils.py").read_text(encoding="utf-8-sig"))
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("READ_ONLY_ROLES", "WRITE_RESTRICTED_ROLES"):
                    constants[target.id] = ast.literal_eval(node.value.args[0])
    assert constants.get("READ_ONLY_ROLES") == {"finance"}
    assert {"viewer", "user"}.issubset(constants.get("WRITE_RESTRICTED_ROLES", set()))
    app_src = (APP_DIR / "app.py").read_text(encoding="utf-8-sig")
    app_tree = ast.parse(app_src)
    hook = next(
        ast.get_source_segment(app_src, n)
        for n in app_tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "enforce_read_only_role"
    )
    assert "WRITE_RESTRICTED_ROLES" in hook
    assert "WRITE_RESTRICTED_SELF_GATED_ENDPOINTS" in hook


def test_bug_2026_11_26_007_closed_po_and_sqlite_coalesce_source_contracts():
    src = (APP_DIR / "app.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(src)
    targets = {"build_purchase_request_execution", "sync_sales_order_shipment"}
    funcs = {
        n.name: ast.get_source_segment(src, n)
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name in targets
    }

    po_exec = funcs["build_purchase_request_execution"]
    assert "PurchaseOrder.status != 'closed'" not in po_exec
    assert "PurchaseOrder.status == 'closed'" in po_exec

    sync_fn = funcs["sync_sales_order_shipment"]
    assert "func.max(" not in sync_fn
    assert "func.coalesce(SalesOrderItem.shipped_quantity, 0)" in sync_fn
    assert "sa_case(" in sync_fn
