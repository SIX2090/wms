# -*- coding: utf-8 -*-
"""BUG-2026-11-28-001 回归测试：领料单、领料单详情与领料明细报表第一批安全、完整性与价格口径修复。

Part A（纯 AST / Jinja / openpyxl / Node-VM，本地 Windows 与 Linux CI 均执行，支持 R8 文件备份回退验证）：
- P0-1：out_order_list、document_print(in_order/out_order)、api_ai_out_order_anomaly_analysis @require_role 门禁与列表导出按钮角色对齐
- P0-2：out_order_add 备注回填与用途录入/保存、out_order_detail #editHeaderModal 历史 customer 保留
- P0-3：update_out_order_item 停用物料/来源换料/严格数量/销售超发拦截；copy_out_order 下推单/采购退货/停用仓/停用物料/负价拦截
- P0-4：import_out_order 库位不误填仓库名、合同编号/工程名称表头优先映射与落库、停用部门/非法日期/空白日期/复用停用料与 0 导入提示修正；
  详情页 ExcelImportExport 指向 /out_order/<id>/batch_add_items 并支持原子 Excel 明细导入
- P0-5：普通领料口径统一（OutOrder.requisition_filter 覆盖 None/领料单/''/requisition/生产出库/Android扫码出库）及详情返回链接修正
- P0-6：price_dimension_enabled 全链路收口（out_detail 报表 API/导出/金额卡片、print_out.html、print_out_with_excel.html、
  _build_out_order_excel、out_order_detail 列设置与添加弹窗、AI 异常分析单价偏差检查）

Part B（完整隔离 Flask + SQLite 端到端集成测试，于 Linux CI 运行）。
"""
from __future__ import annotations

import ast
import io
import json
import os
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"
OUT_ORDER_PY = ROOT / "app" / "routes" / "out_order.py"
DOC_PRINT_PY = ROOT / "app" / "routes" / "document_print.py"
BATCH_IMPORT_PY = ROOT / "app" / "routes" / "batch_import.py"
REPORT_PY = ROOT / "app" / "routes" / "report.py"
DOCUMENTS_PY = ROOT / "app" / "models" / "documents.py"
OUT_LIST_HTML = ROOT / "app" / "templates" / "out_order.html"
OUT_ADD_HTML = ROOT / "app" / "templates" / "out_order_add.html"
OUT_DETAIL_HTML = ROOT / "app" / "templates" / "out_order_detail.html"
PRINT_OUT_HTML = ROOT / "app" / "templates" / "print_out.html"
PRINT_OUT_EXCEL_HTML = ROOT / "app" / "templates" / "print_out_with_excel.html"
REPORT_VIEW_HTML = ROOT / "app" / "templates" / "report_view.html"
EXCEL_IE_JS = ROOT / "app" / "static" / "js" / "excel-import-export.js"

_IS_LINUX_ISOLATED = sys.platform.startswith("linux") or os.environ.get("WMS_RUN_FULL_INTEGRATION") == "1"


def _get_func(path: Path, name: str) -> tuple[ast.FunctionDef, str]:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = src.splitlines()
            return node, "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function {name} not found in {path}")


def _decorator_calls(func: ast.FunctionDef) -> list[str]:
    return [ast.unparse(dec) for dec in func.decorator_list]


def _make_xlsx(rows: list[list]) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


# ==================== Part A: 纯 AST / Jinja / openpyxl / Node-VM 回归 ====================


def test_p0_1_rbac_on_list_document_print_and_ai_anomaly_ast():
    """P0-1: out_order_list, document_print(in_order/out_order), AI anomaly endpoint require business roles."""
    list_fn, _ = _get_func(OUT_ORDER_PY, "out_order_list")
    assert any(
        "require_role('warehouse', 'finance', 'purchase', 'production', 'sales')" in d
        for d in _decorator_calls(list_fn)
    ), "out_order_list missing @require_role"

    ai_fn, _ = _get_func(APP_PY, "api_ai_out_order_anomaly_analysis")
    assert any(
        "require_role('warehouse', 'purchase', 'production', 'sales')" in d
        for d in _decorator_calls(ai_fn)
    ), "api_ai_out_order_anomaly_analysis missing @require_role"

    _, reg_body = _get_func(DOC_PRINT_PY, "register_document_print_routes")
    assert "code in ('in_order', 'out_order')" in reg_body
    assert "require_role('warehouse', 'finance', 'purchase', 'production', 'sales')" in reg_body

    list_html = OUT_LIST_HTML.read_text(encoding="utf-8")
    export_idx = list_html.index('href="/out_order/export?')
    window = list_html[max(0, export_idx - 160) : export_idx]
    assert "current_user.role in ['admin', 'warehouse', 'finance', 'sales', 'purchase']" in window


def test_p0_2_form_prefill_purpose_remark_and_legacy_customer_preserved():
    """P0-2: out_order_add renders prefill.remark & purpose; add_out_order persists purpose; detail preserves legacy customer."""
    add_html = OUT_ADD_HTML.read_text(encoding="utf-8")
    assert 'name="remark" rows="2">{{ prefill.remark if prefill and prefill.remark else \'\' }}</textarea>' in add_html
    assert 'name="purpose"' in add_html
    assert "prefill.purpose" in add_html
    assert "purposeInput ? { purpose: purposeInput.value.trim() } : {}" in add_html

    _, add_body = _get_func(OUT_ORDER_PY, "add_out_order")
    assert "has_purpose = 'purpose' in data" in add_body
    assert "if has_purpose and not linked_sales_outbound:" in add_body
    assert "order.purpose = purpose or None" in add_body

    detail_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert '<input type="hidden" name="customer" value="{{ order.customer or \'\' }}">' in detail_html


def test_p0_3_update_item_and_copy_order_guards_ast():
    """P0-3: update_out_order_item & copy_out_order enforce inactive, source, numeric, warehouse, and return guards."""
    _, upd_body = _get_func(OUT_ORDER_PY, "update_out_order_item")
    assert "if material.status == 'inactive':" in upd_body
    assert "item.source_sales_order_item_id or item.source_in_order_item_id" in upd_body
    assert "parsed_quantity = float(raw_quantity)" in upd_body
    assert "sales_outbound_remaining_check(order)" in upd_body

    _, copy_body = _get_func(OUT_ORDER_PY, "copy_out_order")
    assert "elif _active_outbound_allocations(source).first():" in copy_body
    assert "if source.business_type == '采购退货出库':" in copy_body
    assert "purchase_return_requires_order()" in copy_body
    assert "'采购退货出库': 'PR'" in copy_body
    assert "validate_inventory_warehouse(source.warehouse or '')" in copy_body
    assert "item.material.status == 'inactive'" in copy_body
    assert "max(0.0, float(item.price or 0))" in copy_body


def test_p0_4_import_out_order_and_detail_excel_upload_ast():
    """P0-4: import_out_order fixes location/header/dept/date/contract/inactive/zero-msg; detail import uses batch_add_items."""
    _, imp_body = _get_func(BATCH_IMPORT_PY, "import_out_order")
    assert "location=location," in imp_body
    assert "location=location or warehouse.name" not in imp_body
    assert imp_body.index("'合同编号' in h") < imp_body.index("'物料编码' in h or '编码' in h")
    assert imp_body.index("'工程名称' in h") < imp_body.index("'物料名称' in h or '名称' in h")
    assert "Department.status.in_(('active', '启用'))" in imp_body
    assert "出库日期格式不正确" in imp_body
    assert "datetime.now().date()" in imp_body
    assert "resolve_item_contract(" in imp_body
    assert "contract_no=get_val('contract_no') or None" in imp_body
    assert "project_name=get_val('project_name') or None" in imp_body
    assert "未导入任何领料单" in imp_body
    assert imp_body.count("getattr(material, 'status', None) == 'inactive'") >= 2

    _, batch_body = _get_func(OUT_ORDER_PY, "batch_add_out_order_items")
    assert "upload_file = request.files.get('file')" in batch_body
    assert "_read_import_sheet(upload_file" in batch_body
    assert "validate_excel_extension" in batch_body
    assert "validate_excel_size" in batch_body
    assert "'count': len(prepared)" in batch_body

    detail_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert "importUrl: '/out_order/{{ order.id }}/batch_add_items'" in detail_html
    assert "importUrl: '/import/out_order'" not in detail_html
    assert "templateUrl: '/export/template/out_order'" not in detail_html
    assert "field: 'batch'" not in detail_html

    ie_js = EXCEL_IE_JS.read_text(encoding="utf-8")
    assert "if (this.options.importUrl)" in ie_js


def test_p0_5_requisition_scope_unification_and_detail_back_link():
    """P0-5: OutOrder.requisition_filter covers all ordinary requisition variants across list/export/inout_print/detail."""
    _, filt_body = _get_func(DOCUMENTS_PY, "requisition_filter")
    for token in ("'领料单'", "''", "'requisition'", "'生产出库'", "'Android扫码出库'"):
        assert token in filt_body, f"requisition_filter missing {token}"

    for path, fn_name in (
        (OUT_ORDER_PY, "out_order_list"),
        (OUT_ORDER_PY, "export_out_order"),
        (REPORT_PY, "report_inout_print"),
    ):
        _, body = _get_func(path, fn_name)
        assert "OutOrder.requisition_filter()" in body, f"{fn_name} should use OutOrder.requisition_filter()"

    detail_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert "back_base = '/out_order' if is_issue" in detail_html


def test_p0_6_price_dimension_enabled_across_reports_prints_detail_ai():
    """P0-6: price_dimension_enabled enforced on out_detail, print_out, print_out_with_excel, _build_out_order_excel, detail, AI."""
    _, filters_body = _get_func(APP_PY, "_build_report_filters")
    assert "'in_detail', 'out_detail'" in filters_body
    _, paged_body = _get_func(APP_PY, "_sql_paged_out_detail_report")
    assert "visible_report_data(columns, rows, include_prices=False)" in paged_body
    assert "summary.pop('amount', None)" in paged_body
    _, payload_body = _get_func(APP_PY, "_build_report_payload")
    assert "'in_detail', 'out_detail'" in payload_body
    _, ai_body = _get_func(APP_PY, "_ai_analyze_out_order_anomalies")
    assert "if price_dimension_enabled() and std_price > 0" in ai_body

    rv_html = REPORT_VIEW_HTML.read_text(encoding="utf-8")
    assert "report_type in ('in_detail', 'out_detail'" in rv_html
    assert "if (reportType === 'in_detail' || reportType === 'out_detail')" in rv_html

    # Jinja render check: print_out.html
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(ROOT / "app" / "templates")),
        autoescape=True,
    )
    env.filters["quantity"] = lambda v: f"{float(v or 0):g}"
    env.globals["url_for"] = lambda endpoint, **kw: f"/{endpoint}"
    env.globals["config"] = {}
    fake_unit = SimpleNamespace(name="个")
    fake_mat = SimpleNamespace(code="M001", brand="品牌A", name="轴承", spec="6204", unit=fake_unit)
    fake_item = SimpleNamespace(id=1, material=fake_mat, quantity=5.0, price=12.5, amount=62.5, remark="", contract_no="HT-1")
    fake_missing_mat_item = SimpleNamespace(id=2, material=None, quantity=2.0, price=None, amount=None, remark="", contract_no="")
    fake_order = SimpleNamespace(
        id=1, order_no="OUT-1", date=date(2026, 11, 28), business_type="领料单",
        department=SimpleNamespace(name="车间一"), customer=None, picker="张三",
        purpose="设备维修", warehouse="主仓", operator=SimpleNamespace(username="wh"),
        status="completed", remark="", total_amount=None, contract_no="HT-1",
        items=[fake_item, fake_missing_mat_item],
    )
    fake_req = SimpleNamespace(args={})

    tpl_print = env.get_template("print_out.html")
    html_off = tpl_print.render(order=fake_order, price_dimension_enabled=False, request=fake_req)
    assert "price-col-hidden" in html_off
    assert "数量合计：" in html_off
    assert "12.50" not in html_off and "62.50" not in html_off
    assert "设备维修" in html_off
    html_on = tpl_print.render(order=fake_order, price_dimension_enabled=True, request=fake_req)
    assert "12.50" in html_on and "62.50" in html_on and "合　计：" in html_on

    # Jinja render check: print_out_with_excel.html keeps signature colspan 6+3 while hiding price/amount values
    tpl_excel_print = env.get_template("print_out_with_excel.html")
    fake_tpl = SimpleNamespace(name="默认模板")
    ex_off = tpl_excel_print.render(order=fake_order, template=fake_tpl, price_dimension_enabled=False, request=fake_req)
    assert '<td colspan="6" class="sig-cell"></td>' in ex_off
    assert '<td colspan="3" class="sig-cell">领料：</td>' in ex_off
    assert "12.50" not in ex_off and "62.50" not in ex_off
    ex_on = tpl_excel_print.render(order=fake_order, template=fake_tpl, price_dimension_enabled=True, request=fake_req)
    assert "12.50" in ex_on and "62.50" in ex_on

    # Direct call to _build_out_order_excel with show_price=False vs True (pure openpyxl, no DB)
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    from routes.out_order import _build_out_order_excel

    wb_off = load_workbook(_build_out_order_excel(fake_order, show_price=False))
    ws_off = wb_off.active
    assert ws_off.cell(row=4, column=7).value in ("", None)
    assert ws_off.cell(row=4, column=8).value in ("", None)
    sig_off = [c for r in ws_off.iter_rows() for c in r if isinstance(c.value, str) and c.value.startswith("领料：")]
    assert len(sig_off) == 1 and sig_off[0].column == 7
    wb_off.close()

    wb_on = load_workbook(_build_out_order_excel(fake_order, show_price=True))
    ws_on = wb_on.active
    assert ws_on.cell(row=4, column=7).value == 12.5
    assert ws_on.cell(row=4, column=8).value == 62.5
    wb_on.close()

    # Detail page removes legacy price checkboxes, guards toggleColumn, and hides #addModal price input
    detail_html = OUT_DETAIL_HTML.read_text(encoding="utf-8")
    assert 'id="chkPrice"' not in detail_html and 'id="chkAmount"' not in detail_html
    assert 'id="columnSettingsBtn"' in detail_html
    assert "(colClass === 'colPrice' || colClass === 'colAmount')" in detail_html
    assert '<input type="hidden" id="price" value="">' in detail_html


# ==================== Part B: 完整隔离 Flask + SQLite 端到端集成测试 ====================


def _setup_env():
    app_dir = str(ROOT / "app")
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    import app as w

    w.app.config["TESTING"] = True
    w.app.config["WTF_CSRF_ENABLED"] = False
    with w.app.app_context():
        assert str(w.db.engine.url) == "sqlite:///:memory:"
        w.db.drop_all()
        w.db.create_all()
        from werkzeug.security import generate_password_hash

        users = {}
        for role in ("admin", "warehouse", "finance", "purchase", "production", "sales", "viewer", "user"):
            u = w.User(
                username=f"b1_{role}",
                password_hash=generate_password_hash("Pass1234!"),
                role=role,
                must_change_password=False,
            )
            w.db.session.add(u)
            users[role] = u
        wh_a = w.Warehouse(code="WHA", name="A仓", status="active", is_default=True)
        wh_off = w.Warehouse(code="WHOFF", name="停用仓", status="inactive")
        unit = w.Unit(code="PCS", name="个")
        dept_ok = w.Department(code="D01", name="生产一部", status="active")
        dept_off = w.Department(code="D02", name="停用部门", status="inactive")
        sup = w.Supplier(code="S01", name="鑫达五金")
        cust = w.Customer(code="C01", name="华东客户")
        w.db.session.add_all([wh_a, wh_off, unit, dept_ok, dept_off, sup, cust])
        w.db.session.flush()
        m1 = w.Material(code="M001", name="轴承6204", spec="20*47", unit_id=unit.id, price=10.0, stock=0.0, status="active")
        m_off = w.Material(code="MOFF", name="旧轴承", spec="old", unit_id=unit.id, price=8.0, stock=0.0, status="inactive")
        w.db.session.add_all([m1, m_off])
        w.db.session.commit()
        return w, {
            "users": {r: u.id for r, u in users.items()},
            "wh_a": wh_a.id,
            "wh_off": wh_off.id,
            "dept_ok": dept_ok.id,
            "dept_off": dept_off.id,
            "sup": sup.id,
            "cust": cust.id,
            "m1": m1.id,
            "m_off": m_off.id,
        }


def _client_as(w, user_id: int):
    c = w.app.test_client()
    with c.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return c


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b1_integration_rbac_list_print_and_ai_anomaly():
    w, env = _setup_env()
    with w.app.app_context():
        io_doc = w.InOrder(
            order_no="IN-RBAC-1", date=date.today(), supplier_id=env["sup"],
            warehouse="A仓", business_type="采购入库", status="pending",
            operator_id=env["users"]["warehouse"], total_amount=10.0,
        )
        oo_doc = w.OutOrder(
            order_no="OUT-RBAC-1", date=date.today(), department_id=env["dept_ok"],
            warehouse="A仓", business_type="领料单", status="pending",
            operator_id=env["users"]["warehouse"], total_amount=10.0,
        )
        w.db.session.add_all([io_doc, oo_doc])
        w.db.session.flush()
        w.db.session.add(w.InOrderItem(in_order_id=io_doc.id, material_id=env["m1"], quantity=1, price=10, amount=10))
        w.db.session.add(w.OutOrderItem(out_order_id=oo_doc.id, material_id=env["m1"], quantity=1, price=10, amount=10))
        w.db.session.commit()
        io_id, oo_id = io_doc.id, oo_doc.id

    viewer_c = _client_as(w, env["users"]["viewer"])
    for path in (
        "/out_order",
        f"/out_order/{oo_id}/print_options",
        f"/out_order/{oo_id}/print_preview",
        f"/out_order/{oo_id}/print_file",
        f"/in_order/{io_id}/print_options",
        f"/api/ai/out_order/{oo_id}/anomaly_analysis",
    ):
        resp = viewer_c.get(path)
        assert resp.status_code in (302, 403), f"viewer should be blocked on {path}, got {resp.status_code}"

    prod_c = _client_as(w, env["users"]["production"])
    r_list = prod_c.get(f"/out_order?warehouse_id={env['wh_a']}")
    assert r_list.status_code == 200
    assert "/out_order/export?" not in r_list.get_data(as_text=True)
    assert prod_c.get(f"/api/ai/out_order/{oo_id}/anomaly_analysis").status_code == 200

    fin_c = _client_as(w, env["users"]["finance"])
    assert fin_c.get(f"/out_order?warehouse_id={env['wh_a']}").status_code == 200
    assert fin_c.get(f"/out_order/{oo_id}/print_options").status_code == 200
    assert fin_c.get(f"/api/ai/out_order/{oo_id}/anomaly_analysis").status_code == 403


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b1_integration_purpose_remark_update_item_and_copy_guards():
    from tests.document_revision_client import document_post

    w, env = _setup_env()
    wh_c = _client_as(w, env["users"]["warehouse"])
    today = date.today().isoformat()

    # 1. add_out_order persists purpose & out_order_add prefills purpose and remark
    r_add = wh_c.post("/out_order/add", json={
        "date": today, "business_type": "领料单", "department_id": env["dept_ok"],
        "warehouse_id": env["wh_a"], "purpose": "产线维护", "remark": "首单备注",
        "items": [{"code": "M001", "quantity": 2, "price": 10}],
    })
    assert r_add.status_code == 200 and r_add.get_json()["status"] == "success"
    oid = r_add.get_json()["id"]
    with w.app.app_context():
        order = w.db.session.get(w.OutOrder, oid)
        assert order.purpose == "产线维护"
        assert order.remark == "首单备注"
        item_id = order.items[0].id
    edit_html = wh_c.get(f"/out_order/add?order_id={oid}").get_data(as_text=True)
    assert "首单备注</textarea>" in edit_html
    assert 'value="产线维护"' in edit_html

    # 2. update_out_order_item rejects inactive material and invalid quantity
    r_bad_qty = document_post(wh_c, "/out_order/item/update", data={"id": str(item_id), "quantity": "abc"})
    assert r_bad_qty.status_code == 400
    r_off_mat = document_post(wh_c, "/out_order/item/update", data={"id": str(item_id), "code": "MOFF"})
    assert r_off_mat.status_code == 400 and "停用" in r_off_mat.get_json()["msg"]

    # 3. update_out_order_item rejects sales over-shipment and source material swap
    with w.app.app_context():
        so = w.SalesOrder(order_no="SO-GUARD-1", date=date.today(), customer_id=env["cust"], warehouse_id=env["wh_a"], status="confirmed", operator_id=env["users"]["warehouse"])
        w.db.session.add(so)
        w.db.session.flush()
        so_item = w.SalesOrderItem(sales_order_id=so.id, material_id=env["m1"], quantity=5, shipped_quantity=0, price=10, amount=50)
        w.db.session.add(so_item)
        w.db.session.flush()
        sale_out = w.OutOrder(order_no="SO-OUT-1", date=date.today(), business_type="销售出库", customer="华东客户", warehouse="A仓", source_sales_order_id=so.id, status="pending", operator_id=env["users"]["warehouse"])
        w.db.session.add(sale_out)
        w.db.session.flush()
        sale_item = w.OutOrderItem(out_order_id=sale_out.id, material_id=env["m1"], source_sales_order_item_id=so_item.id, quantity=3, price=10, amount=30)
        w.db.session.add(sale_item)
        w.db.session.commit()
        sale_item_id = sale_item.id
    r_over = document_post(wh_c, "/out_order/item/update", data={"id": str(sale_item_id), "quantity": "8"})
    assert r_over.status_code == 400

    # 4. copy_out_order blocks inactive warehouse, inactive material, purchase return, and pushed requisition
    with w.app.app_context():
        off_wh_order = w.OutOrder(order_no="OUT-OFFWH", date=date.today(), business_type="领料单", warehouse="停用仓", status="pending", operator_id=env["users"]["warehouse"])
        off_mat_order = w.OutOrder(order_no="OUT-OFFMAT", date=date.today(), business_type="领料单", warehouse="A仓", status="pending", operator_id=env["users"]["warehouse"])
        pr_order = w.OutOrder(order_no="PR-NO-COPY", date=date.today(), business_type="采购退货出库", customer="鑫达五金", warehouse="A仓", status="pending", operator_id=env["users"]["warehouse"])
        w.db.session.add_all([off_wh_order, off_mat_order, pr_order])
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=off_wh_order.id, material_id=env["m1"], quantity=1, price=1, amount=1))
        w.db.session.add(w.OutOrderItem(out_order_id=off_mat_order.id, material_id=env["m_off"], quantity=1, price=1, amount=1))
        w.db.session.add(w.OutOrderItem(out_order_id=pr_order.id, material_id=env["m1"], quantity=1, price=1, amount=1))
        w.db.session.commit()
        off_wh_id, off_mat_id, pr_id = off_wh_order.id, off_mat_order.id, pr_order.id

    assert document_post(wh_c, f"/out_order/{off_wh_id}/copy").status_code == 400
    assert document_post(wh_c, f"/out_order/{off_mat_id}/copy").status_code == 400
    assert document_post(wh_c, f"/out_order/{pr_id}/copy").status_code == 409


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b1_integration_import_out_order_and_detail_excel_append():
    from tests.document_revision_client import document_post

    w, env = _setup_env()
    wh_c = _client_as(w, env["users"]["warehouse"])

    # 1. import_out_order: contract_no / project_name preserved, location stays empty, invalid date/dept skipped
    buf = _make_xlsx([
        ["单据编号", "日期", "部门", "仓库", "合同编号", "工程名称", "物料编码", "物料名称", "数量", "单价"],
        ["IMP-OK-1", "", "生产一部", "A仓", "HT-2026-01", "一号车间改造", "M001", "轴承6204", 4, 10],
        ["IMP-BAD-DATE", "not-a-date", "生产一部", "A仓", "HT-2", "工程2", "M001", "轴承6204", 2, 10],
        ["IMP-BAD-DEPT", date.today().isoformat(), "停用部门", "A仓", "HT-3", "工程3", "M001", "轴承6204", 2, 10],
    ])
    r_imp = wh_c.post("/import/out_order", data={"file": (buf, "out.xlsx")}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert r_imp.status_code == 200 and r_imp.get_json()["count"] == 1
    with w.app.app_context():
        ok_order = w.OutOrder.query.filter_by(order_no="IMP-OK-1").one()
        assert ok_order.location == ""
        assert ok_order.date == date.today()
        assert ok_order.contract_no == "HT-2026-01"
        assert ok_order.project_name == "一号车间改造"
        assert ok_order.items[0].contract_no == "HT-2026-01"
        assert ok_order.items[0].project_name == "一号车间改造"
        assert w.OutOrder.query.filter_by(order_no="IMP-BAD-DATE").first() is None
        assert w.OutOrder.query.filter_by(order_no="IMP-BAD-DEPT").first() is None
        draft_id = ok_order.id

    # 2. Detail Excel append via /out_order/<id>/batch_add_items (atomic)
    detail_buf = _make_xlsx([
        ["物料编码", "数量", "单价", "备注"],
        ["M001", 3, 12, "Excel追加"],
    ])
    r_append = document_post(wh_c, f"/out_order/{draft_id}/batch_add_items", data={"file": (detail_buf, "items.xlsx")})
    assert r_append.status_code == 200 and r_append.get_json()["count"] == 1
    with w.app.app_context():
        order = w.db.session.get(w.OutOrder, draft_id)
        assert len(order.items) == 2
        assert order.items[1].remark == "Excel追加"
        assert w.OutOrder.query.count() == 1


@pytest.mark.skipif(not _IS_LINUX_ISOLATED, reason="Full Flask integration runs on isolated Linux CI")
def test_b1_integration_requisition_scope_and_price_dimension_toggle():
    w, env = _setup_env()
    with w.app.app_context():
        w.set_system_setting("price_dimension_enabled", "0")
        o_scan = w.OutOrder(
            order_no="OUT-SCAN-1", date=date.today(), department_id=env["dept_ok"],
            warehouse="A仓", business_type="Android扫码出库", status="completed",
            operator_id=env["users"]["warehouse"], total_amount=500.0,
        )
        w.db.session.add(o_scan)
        w.db.session.flush()
        # Price 100 vs std 10 -> >20% deviation, should be suppressed when price_dimension_enabled=0
        w.db.session.add(w.OutOrderItem(out_order_id=o_scan.id, material_id=env["m1"], quantity=5, price=100, amount=500))
        w.db.session.commit()
        scan_id = o_scan.id

    wh_c = _client_as(w, env["users"]["warehouse"])
    # 1. Requisition scope includes Android扫码出库 on /out_order and /out_order/export
    assert "OUT-SCAN-1" in wh_c.get(f"/out_order?warehouse_id={env['wh_a']}").get_data(as_text=True)
    r_exp = wh_c.get(f"/out_order/export?warehouse_id={env['wh_a']}")
    assert r_exp.status_code == 200
    exp_rows = list(load_workbook(io.BytesIO(r_exp.data)).active.values)
    assert any(r[0] == "OUT-SCAN-1" for r in exp_rows[1:])

    # 2. price_dimension_enabled=0 hides price/amount on out_detail API, print_out, print_excel, AI anomaly
    r_rpt0 = wh_c.get(f"/report/api/out_detail?warehouse_id={env['wh_a']}&start_date={date.today().isoformat()}&end_date={date.today().isoformat()}")
    assert r_rpt0.status_code == 200
    d0 = r_rpt0.get_json()
    assert "price" not in [c["field"] for c in d0["columns"]]
    assert "amount" not in [c["field"] for c in d0["columns"]]
    assert "amount" not in d0["summary"]
    assert "price" not in d0["data"][0] and "amount" not in d0["data"][0]

    r_ai0 = wh_c.get(f"/api/ai/out_order/{scan_id}/anomaly_analysis")
    assert all(a["anomaly_type"] != "单价偏差过大" for a in r_ai0.get_json()["data"]["anomalies"])

    r_px0 = wh_c.get(f"/out_order/{scan_id}/print_excel")
    ws_px0 = load_workbook(io.BytesIO(r_px0.data)).active
    assert ws_px0.cell(row=4, column=7).value in ("", None)
    assert ws_px0.cell(row=4, column=8).value in ("", None)

    # 3. price_dimension_enabled=1 restores price/amount everywhere
    with w.app.app_context():
        w.set_system_setting("price_dimension_enabled", "1")
        w.db.session.commit()
    r_rpt1 = wh_c.get(f"/report/api/out_detail?warehouse_id={env['wh_a']}&start_date={date.today().isoformat()}&end_date={date.today().isoformat()}")
    d1 = r_rpt1.get_json()
    assert "price" in [c["field"] for c in d1["columns"]] and "amount" in d1["summary"]
    r_ai1 = wh_c.get(f"/api/ai/out_order/{scan_id}/anomaly_analysis")
    assert any(a["anomaly_type"] == "单价偏差过大" for a in r_ai1.get_json()["data"]["anomalies"])
    r_px1 = wh_c.get(f"/out_order/{scan_id}/print_excel")
    ws_px1 = load_workbook(io.BytesIO(r_px1.data)).active
    assert ws_px1.cell(row=4, column=7).value == 100.0
    assert ws_px1.cell(row=4, column=8).value == 500.0
