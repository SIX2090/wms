# -*- coding: utf-8 -*-
"""Regression suite for BUG-2026-11-28-004:
1. Dedicated 领料明细报表 (requisition_detail) and 其他出库明细报表 (other_out_detail)
   with explicit 全部仓库 (warehouse_id=0), 领料部门/领料人 filters, clickable order links,
   multi-unit summaries, and preserved out_detail/CSP contracts.
2. out_order_add.html: price_dimension_enabled hides 单价/金额/合计 ¥0.00 via d-none
   and skips hidden price on Enter; header 合同编号/工程名称 syncs to filled material rows
   without tainting blank rows and submits with payload.
3. out_order.html / out_order.py: 领料人 column, filter, search, sort, export/pagination
   follow-through, and price_dimension_enabled column toggle with exact empty colspan.

Part A runs without Flask/DB (AST, Jinja rendering, Node-VM).
Part B runs full isolated Flask + in-memory SQLite integration tests on Linux CI.
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
APP_PY = ROOT / "app" / "app.py"
REPORT_PY = ROOT / "app" / "routes" / "report.py"
OUT_ORDER_PY = ROOT / "app" / "routes" / "out_order.py"
DOC_PRINT_PY = ROOT / "app" / "doc_print_excel.py"
BASE_HTML = ROOT / "app" / "templates" / "base.html"
REPORT_VIEW_HTML = ROOT / "app" / "templates" / "report_view.html"
OUT_LIST_HTML = ROOT / "app" / "templates" / "out_order.html"
OUT_ADD_HTML = ROOT / "app" / "templates" / "out_order_add.html"


def _extract_js_function(source: str, name: str) -> str:
    matches = re.findall(r"^function " + re.escape(name) + r"\b[\s\S]*?^\}", source, re.M)
    assert len(matches) == 1, f"Expected 1 top-level JS function {name}, found {len(matches)}"
    return matches[0]


def _jinja_env() -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(ROOT / "app" / "templates")),
        autoescape=True,
    )
    env.globals["csrf_token"] = lambda: "test-csrf"
    env.globals["config"] = {"STATIC_VERSION": "test"}
    env.globals["STATIC_VERSION"] = "test"
    env.globals["url_for"] = (
        lambda ep, **kw: ("/static/" + kw["filename"])
        if ep == "static"
        else ("/" + ep + (f"/{kw['id']}" if "id" in kw else ""))
    )
    env.globals["current_user"] = SimpleNamespace(
        is_authenticated=True, role="admin", username="qa", id=1, get_id=lambda: "1"
    )
    env.globals["request"] = SimpleNamespace(args={}, path="/out_order")
    env.globals["inline_shell_actions"] = False
    env.globals["location_management_enabled"] = False
    env.globals["inventory_alert_enabled"] = False
    env.globals["runtime_external_paused"] = False
    env.globals["ai_menu_capabilities"] = {}
    return env


# ============================================================================
# Part A: Pure static / Jinja / Node-VM verification (runs locally + CI)
# ============================================================================


def test_a1_dedicated_report_definitions_menu_and_csp_hashes():
    """Dedicated requisition_detail & other_out_detail definitions, menu links, and intact CSP hashes."""
    app_src = APP_PY.read_text(encoding="utf-8")
    assert "'requisition_detail':" in app_src
    assert "'other_out_detail':" in app_src
    assert "'title': '领料明细报表'" in app_src
    assert "'title': '其他出库明细报表'" in app_src
    assert "'requisition_detail': _build_requisition_detail_report" in app_src
    assert "'other_out_detail': _build_other_out_detail_report" in app_src
    assert "'requisition_detail': _sql_paged_requisition_detail_report" in app_src
    assert "'other_out_detail': _sql_paged_other_out_detail_report" in app_src

    doc_print_src = DOC_PRINT_PY.read_text(encoding="utf-8")
    assert doc_print_src.count("'requisition_detail', 'other_out_detail'") >= 4

    env = _jinja_env()
    for role in ("admin", "warehouse", "finance"):
        html = env.get_template("base.html").render(
            current_user=SimpleNamespace(is_authenticated=True, role=role, username="u", id=1),
            price_dimension_enabled=False,
        )
        soup = BeautifulSoup(html, "html.parser")
        hrefs = {a.get("href"): a.get_text(strip=True) for a in soup.select("a[href]")}
        assert hrefs.get("/report/view/requisition_detail") == "领料明细报表", (role, hrefs)
        assert hrefs.get("/report/view/other_out_detail") == "其他出库明细报表", (role, hrefs)
        assert "/report/view/out_detail" in hrefs

    # CSP hash integrity on base.html
    sys.path.insert(0, str(ROOT / "app"))
    from services.material_form_policy import SHARED_SCRIPT_HASHES

    rendered = env.get_template("base.html").render(price_dimension_enabled=False)
    actual = [
        base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
        for attrs, body in re.findall(r"<script\b([^>]*)>([\s\S]*?)</script>", rendered)
        if not re.search(r"\bsrc\s*=", attrs) and "application/json" not in attrs and body.strip()
    ]
    assert actual == list(SHARED_SCRIPT_HASHES)


def test_a2_report_view_dedicated_filters_and_all_warehouses():
    """report_view.html renders tailored filters, explicit 全部仓库 option, and unit-total support."""
    env = _jinja_env()
    warehouses = [
        SimpleNamespace(id=1, code="WH01", name="主仓", status="active"),
        SimpleNamespace(id=2, code="WH02", name="旧仓", status="inactive"),
    ]
    departments = [
        SimpleNamespace(id=10, code="D01", name="装配部", status="active"),
        SimpleNamespace(id=11, code="D02", name="旧部门", status="inactive"),
    ]
    common = dict(
        warehouses=warehouses,
        default_warehouse=warehouses[0],
        departments=departments,
        category_rows=[],
        summary_labels={"count": "记录数", "quantity": "领料数量", "amount": "领料金额"},
        summary_types={"count": "integer", "quantity": "number", "amount": "money"},
        price_dimension_enabled=False,
    )

    # 1) requisition_detail
    html_req = env.get_template("report_view.html").render(
        report_type="requisition_detail",
        title="领料明细报表",
        filters_config={
            "date": True, "material": True, "supplier": False,
            "customer": False, "department": True, "picker": True, "status": True,
        },
        **common,
    )
    soup_req = BeautifulSoup(html_req, "html.parser")
    assert soup_req.select_one("#reportHeading").get_text(strip=True) == "领料明细报表"
    assert soup_req.select_one("select#department_id") is not None
    assert "旧部门（已停用）" in soup_req.select_one("select#department_id").get_text()
    picker_req = soup_req.select_one("input#picker")
    assert picker_req is not None and picker_req.get("data-ks") == "employee"
    assert soup_req.select_one("select#business_type") is None
    assert soup_req.select_one("input#customer") is None
    wh_opts_req = {opt.get("value"): opt.get_text(strip=True) for opt in soup_req.select("#warehouse_id option")}
    assert wh_opts_req.get("0") == "全部仓库"
    assert soup_req.select_one('#warehouse_id option[value="1"]').has_attr("selected")
    assert soup_req.select_one("#contract_no").get("data-ks") == "contract_no"
    assert soup_req.select_one("#project_name").get("data-ks") == "project"
    assert soup_req.select_one("#detail_material_id") is not None
    assert soup_req.select_one("#reportAmountCard").has_attr("hidden")
    assert "material-movement-report.js" in html_req
    assert soup_req.select_one("#reportTable.detail-report-table") is not None

    # 2) other_out_detail
    html_other = env.get_template("report_view.html").render(
        report_type="other_out_detail",
        title="其他出库明细报表",
        filters_config={
            "date": True, "material": True, "supplier": False,
            "customer": True, "department": False, "picker": True, "status": True,
        },
        **common,
    )
    soup_other = BeautifulSoup(html_other, "html.parser")
    assert soup_other.select_one("#reportHeading").get_text(strip=True) == "其他出库明细报表"
    assert soup_other.select_one("select#business_type") is None
    assert soup_other.select_one("select#department_id") is None
    cust_other = soup_other.select_one("input#customer")
    assert cust_other is not None and cust_other.get("data-ks") == "customer"
    assert "客户 / 领用单位" in soup_other.select_one('label[for="customer"]').get_text()
    assert "领用人 / 经办人" in soup_other.select_one('label[for="picker"]').get_text()
    assert soup_other.select_one('#warehouse_id option[value="0"]').get_text(strip=True) == "全部仓库"


def test_a3_out_order_add_price_hide_enter_skip_and_header_contract_vm():
    """out_order_add.html hides price/amount/total when price_dimension_enabled=False,
    skips hidden price on Enter, and syncs header contract/project cleanly."""
    env = _jinja_env()
    render_ctx = dict(
        materials=[], units=[], customers=[], departments=[],
        warehouses=[SimpleNamespace(id=1, name="项目仓")],
        default_warehouse=SimpleNamespace(id=1, name="项目仓"),
        is_sale_order=False, is_other_out=False, is_purchase_return=False,
        purchase_return_requires_order=False, sales_outbound_requires_order=False,
        default_business_type="领料单", page_title="新增领料单",
        party_label="领料部门", return_list_url="/out_order",
        return_add_url="/out_order/add",
        prefill={"contract_id": "9", "contract_no": "HT-2026-01", "project_name": "一号工程"},
        order_id=None, order_no="OUT-TEST-1", order_date="2026-11-28",
        edit_items=[], today=date(2026, 11, 28),
    )

    html_off = env.get_template("out_order_add.html").render(price_dimension_enabled=False, **render_ctx)
    soup_off = BeautifulSoup(html_off, "html.parser")
    assert "d-none" in (soup_off.select_one('th[data-column-key="price"]').get("class") or [])
    assert "d-none" in (soup_off.select_one('th[data-column-key="amount"]').get("class") or [])
    assert "d-none" in (soup_off.select_one("tr.total-row").get("class") or [])
    assert soup_off.select_one("#totalAmount") is not None
    assert soup_off.select_one("#headerContractNo").get("value") == "HT-2026-01"
    assert soup_off.select_one("#headerContractId").get("value") == "9"
    assert soup_off.select_one("#headerProjectName").get("value") == "一号工程"

    html_on = env.get_template("out_order_add.html").render(price_dimension_enabled=True, **render_ctx)
    soup_on = BeautifulSoup(html_on, "html.parser")
    assert "d-none" not in (soup_on.select_one('th[data-column-key="price"]').get("class") or [])
    assert "d-none" not in (soup_on.select_one('th[data-column-key="amount"]').get("class") or [])
    assert "d-none" not in (soup_on.select_one("tr.total-row").get("class") or [])

    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")

    src = OUT_ADD_HTML.read_text(encoding="utf-8")
    fns = "\n".join(
        _extract_js_function(src, name)
        for name in (
            "fillMaterialFields",
            "applyHeaderContractToRow",
            "syncHeaderContractToMaterialRows",
            "_initOutOrderRow",
            "outboundRowHasDetails",
            "findEmptyRow",
            "submitForm",
        )
    )
    vm_script = r"""
const assert = require('node:assert/strict');
const vm = require('node:vm');
const { fns, decimalJs } = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

function runScenario(priceEnabled) {
  const focusLog = [];
  const posted = [];
  const headerContractNo = { value: 'HT-2026-01', dataset: {} };
  const headerContractId = { value: '9', dataset: {} };
  const headerProjectName = { value: '一号工程', dataset: {} };

  function makeInput(cls, initVal = '') {
    return {
      cls, value: initVal, dataset: {}, style: {}, listeners: {},
      addEventListener(ev, fn) { (this.listeners[ev] ||= []).push(fn); },
      focus() { focusLog.push(cls); },
      select() {},
    };
  }

  const rows = [];
  function makeRow() {
    const els = {};
    const row = {
      dataset: {},
      innerHTML: '',
      nextElementSibling: null,
      querySelector(sel) {
        if (!els[sel]) els[sel] = makeInput(sel);
        return els[sel];
      },
    };
    if (rows.length) rows[rows.length - 1].nextElementSibling = row;
    rows.push(row);
    return row;
  }

  const fields = {
    order_id: { value: '' },
    order_no: { value: 'OUT-1' },
    date: { value: '2026-11-28' },
    business_type: { value: '领料单' },
    department_id: { value: '' },
    customer: { value: '' },
    picker: { value: '张三' },
    warehouse_id: { value: '1' },
    purpose: { value: '' },
    remark: { value: '' },
  };
  const document = {
    getElementById(id) {
      if (id === 'headerContractNo') return headerContractNo;
      if (id === 'headerContractId') return headerContractId;
      if (id === 'headerProjectName') return headerProjectName;
      if (id === 'materialTableBody') return { lastElementChild: rows[rows.length - 1] };
      return null;
    },
    querySelector(sel) {
      if (sel === '#materialTableBody tr:last-child') return rows[rows.length - 1];
      const m = sel.match(/name="([^"]+)"/);
      return m ? (fields[m[1]] || null) : null;
    },
    querySelectorAll(sel) {
      if (sel === '#materialTableBody tr') return rows;
      return [];
    },
  };

  const ctx = {
    document,
    window: null,
    location: { href: '' },
    isSaleOrder: false,
    isOtherOut: false,
    isPurchaseReturn: false,
    purchaseReturnRequiresOrder: false,
    returnAddUrl: '/out_order/add',
    priceDimensionEnabled: priceEnabled,
    outOrderSubmitting: false,
    getMaterialUnit: () => '个',
    formatStock: v => Number(v).toFixed(2),
    calcAmount() {},
    handleMaterialCodeInput() {},
    handleKeydown() {},
    showToast(msg, type) { if (type === 'danger') throw new Error('unexpected error toast: ' + msg); },
    showDocumentCompletionIssue(url, err) { throw new Error('unexpected completion issue: ' + err); },
    confirm: () => true,
    ensureIssueEntryRow() {},
    addNewRow() {
      const r = makeRow();
      ctx._initOutOrderRow(r, rows.length);
      return r;
    },
    WMS: {
      api: {
        postRaw(url, payload) {
          posted.push({ url, payload });
          return Promise.resolve({ status: 'success', id: 1, order_no: 'OUT-1' });
        },
      },
    },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(decimalJs + '\n' + fns, ctx);

  const r1 = ctx.addNewRow();
  const r2 = ctx.addNewRow();

  // Check price/amount d-none in generated row HTML
  assert.equal(r1.innerHTML.includes('data-column-key="price" class="d-none"'), !priceEnabled);
  assert.equal(r1.innerHTML.includes('data-column-key="amount" class="amount-col d-none"'), !priceEnabled);

  // Blank trailing row r2 must NOT be tainted by header contract sync
  ctx.syncHeaderContractToMaterialRows();
  assert.equal(ctx.outboundRowHasDetails(r2), false);
  assert.equal(ctx.findEmptyRow(), r1);

  // Fill material on r1 -> inherits header contract/project; r2 remains blank
  ctx.fillMaterialFields(r1, { code: 'M01', brand: '', name: '轴承', spec: '', unit: '个', stock: 10, price: 5 });
  assert.equal(r1.querySelector('.line-contract-no').value, 'HT-2026-01');
  assert.equal(r1.querySelector('.line-project-name').value, '一号工程');
  assert.equal(r2.querySelector('.line-contract-no').value, '');
  assert.equal(ctx.outboundRowHasDetails(r2), false);

  // Changing header updates header-synced r1, but NOT manually edited rows
  headerContractNo.value = 'HT-2026-02';
  ctx.syncHeaderContractToMaterialRows();
  assert.equal(r1.querySelector('.line-contract-no').value, 'HT-2026-02');
  r1.querySelector('.line-contract-no').value = 'MANUAL-99';
  r1.querySelector('.line-contract-no').listeners.input[0].call(r1.querySelector('.line-contract-no'));
  headerContractNo.value = 'HT-2026-03';
  ctx.syncHeaderContractToMaterialRows();
  assert.equal(r1.querySelector('.line-contract-no').value, 'MANUAL-99');

  // Qty Enter key behavior
  r1.querySelector('.material-qty').value = '3';
  focusLog.length = 0;
  r1.querySelector('.material-qty').listeners.keydown[0]({ key: 'Enter', preventDefault() {} });
  assert.deepEqual(focusLog, [priceEnabled ? '.material-price' : '.material-code']);

  // submitForm sends header contract_id/contract_no/project_name
  ctx.submitForm(false, false);
  assert.equal(posted.length, 1);
  assert.equal(posted[0].payload.contract_id, '9');
  assert.equal(posted[0].payload.contract_no, 'HT-2026-03');
  assert.equal(posted[0].payload.project_name, '一号工程');
  assert.equal(posted[0].payload.items.length, 1);
  assert.equal(posted[0].payload.items[0].contract_no, 'MANUAL-99');
}

runScenario(false);
runScenario(true);
"""
    res = subprocess.run(
        [node, "-e", vm_script],
        input=json.dumps({
            "fns": fns,
            "decimalJs": (ROOT / "app/static/js/decimal-input.js").read_text(encoding="utf-8"),
        }),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def test_a4_out_order_list_picker_column_and_price_toggle():
    """out_order.html exposes picker column/filter/export/pagination and toggles price columns cleanly."""
    env = _jinja_env()
    pagination = SimpleNamespace(
        page=1, per_page=20, pages=2, total=25,
        has_prev=False, has_next=True, prev_num=None, next_num=2,
        iter_pages=lambda **kw: [1, 2],
    )
    filters = {
        "warehouse_id": 1, "status": "", "search": "", "date_start": "", "date_end": "",
        "business_type": "", "picker": "张三", "contract_no": "", "project_name": "",
    }
    base_ctx = dict(
        items=[], pagination=pagination, sort_by="created_at", sort_order="desc",
        per_page=20, filters=filters, page_title="领料明细表", list_base_path="/out_order",
        warehouses=[SimpleNamespace(id=1, code="WH01", name="主仓")],
        default_warehouse=SimpleNamespace(id=1, code="WH01", name="主仓"),
    )

    for role, price_on, expected_cols in [
        ("admin", True, 18),
        ("finance", True, 17),
        ("admin", False, 18),
        ("finance", False, 17),
    ]:
        html = env.get_template("out_order.html").render(
            current_user=SimpleNamespace(is_authenticated=True, role=role, username="u", id=1, get_id=lambda: "1"),
            price_dimension_enabled=price_on,
            **base_ctx,
        )
        soup = BeautifulSoup(html, "html.parser")
        ths = soup.select("#outOrderTable thead th")
        assert len(ths) == expected_cols, (role, price_on, len(ths))
        empty_td = soup.select_one("#outOrderTable tbody tr td[colspan]")
        assert int(empty_td["colspan"]) == expected_cols
        col_keys = [th.get("data-column-key") for th in ths]
        assert "picker" in col_keys
        assert "price" in col_keys and "amount" in col_keys
        price_th = soup.select_one('#outOrderTable thead th[data-column-key="price"]')
        amount_th = soup.select_one('#outOrderTable thead th[data-column-key="amount"]')
        assert ("d-none" in (price_th.get("class") or [])) is (not price_on)
        assert ("d-none" in (amount_th.get("class") or [])) is (not price_on)
        assert soup.select_one('input[name="picker"]').get("value") == "张三"
        export_link = soup.select_one('a[href^="/out_order/export"]')
        assert "picker=%E5%BC%A0%E4%B8%89" in export_link["href"]
        next_link = soup.select_one('a.page-link[href*="page=2"]')
        assert "picker=%E5%BC%A0%E4%B8%89" in next_link["href"]


# ============================================================================
# Part B: Isolated Flask + in-memory SQLite integration tests (Linux CI)
# ============================================================================


@pytest.fixture
def isolated_env(monkeypatch):
    if sys.platform != "linux":
        pytest.skip("Full Flask DB integration runs in Linux CI sandbox")
    if str(ROOT / "app") not in sys.path:
        sys.path.insert(0, str(ROOT / "app"))
    import app as w

    monkeypatch.setitem(w.app.config, "TESTING", True)
    monkeypatch.setitem(w.app.config, "WTF_CSRF_ENABLED", False)
    with w.app.app_context():
        assert str(w.db.engine.url) == "sqlite:///:memory:"
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        user = w.User(username="ux_admin", password_hash="unused", role="admin", must_change_password=False)
        wh_a = w.Warehouse(code="WHA", name="项目仓", status="active", is_default=True)
        wh_b = w.Warehouse(code="WHB", name="备件仓", status="active", is_default=False)
        dept_a = w.Department(code="DA", name="装配部", status="active")
        dept_b = w.Department(code="DB", name="研发部", status="active")
        u_pcs = w.Unit(code="PCS", name="个")
        u_m = w.Unit(code="M", name="米")
        contract = w.Contract(contract_no="HT-2026-01", project_name="一号工程")
        w.db.session.add_all([user, wh_a, wh_b, dept_a, dept_b, u_pcs, u_m, contract])
        w.db.session.flush()
        mat_pcs = w.Material(code="M-PCS", name="轴承", unit_id=u_pcs.id, price=10.0, stock=100.0)
        mat_m = w.Material(code="M-M", name="电缆", unit_id=u_m.id, price=20.0, stock=100.0)
        w.db.session.add_all([mat_pcs, mat_m])
        w.db.session.commit()

        ids = dict(
            user=user.id, wh_a=wh_a.id, wh_b=wh_b.id,
            dept_a=dept_a.id, dept_b=dept_b.id,
            mat_pcs=mat_pcs.id, mat_m=mat_m.id,
            contract_id=contract.id,
        )
    client = w.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(ids["user"])
        sess["_fresh"] = True
    yield w, client, ids
    with w.app.app_context():
        w.db.session.remove()
        w.db.drop_all()


def test_b1_requisition_detail_and_other_out_detail_isolation_and_all_warehouses(isolated_env):
    """End-to-end verification of requisition_detail, other_out_detail, warehouse_id=0,
    department/picker filters, unit_totals, clickable links, and print endpoints."""
    w, client, ids = isolated_env
    with w.app.app_context():
        # 1. Requisition in wh_a (装配部, 张三, 5 个)
        o_req_a = w.OutOrder(
            order_no="OUT-REQ-A", date=date(2026, 11, 20), business_type="领料单",
            warehouse="项目仓", department_id=ids["dept_a"], picker="张三",
            contract_no="HT-2026-01", project_name="一号工程",
            status="completed", operator_id=ids["user"], total_amount=50.0,
        )
        # 2. Requisition in wh_b (研发部, 李四, 3 米)
        o_req_b = w.OutOrder(
            order_no="OUT-REQ-B", date=date(2026, 11, 21), business_type="领料单",
            warehouse="备件仓", department_id=ids["dept_b"], picker="李四",
            contract_no="HT-2026-02", project_name="二号工程",
            status="completed", operator_id=ids["user"], total_amount=60.0,
        )
        # 3. Other out in wh_a (客户甲, 王五, 9 个)
        o_other = w.OutOrder(
            order_no="OO-A", date=date(2026, 11, 22), business_type="其他出库",
            warehouse="项目仓", customer="客户甲", picker="王五",
            status="completed", operator_id=ids["user"], total_amount=90.0,
        )
        # 4. Sales out & purchase return in wh_a (must NEVER leak into either dedicated report)
        o_sale = w.OutOrder(
            order_no="SO-A", date=date(2026, 11, 23), business_type="销售出库",
            warehouse="项目仓", customer="销售客户", status="completed", operator_id=ids["user"], total_amount=120.0,
        )
        o_ret = w.OutOrder(
            order_no="PR-A", date=date(2026, 11, 24), business_type="采购退货出库",
            warehouse="项目仓", customer="供应商甲", status="completed", operator_id=ids["user"], total_amount=40.0,
        )
        w.db.session.add_all([o_req_a, o_req_b, o_other, o_sale, o_ret])
        w.db.session.flush()
        w.db.session.add_all([
            w.OutOrderItem(out_order_id=o_req_a.id, material_id=ids["mat_pcs"], quantity=5, price=10, amount=50, contract_no="HT-2026-01", project_name="一号工程"),
            w.OutOrderItem(out_order_id=o_req_b.id, material_id=ids["mat_m"], quantity=3, price=20, amount=60, contract_no="HT-2026-02", project_name="二号工程"),
            w.OutOrderItem(out_order_id=o_other.id, material_id=ids["mat_pcs"], quantity=9, price=10, amount=90),
            w.OutOrderItem(out_order_id=o_sale.id, material_id=ids["mat_pcs"], quantity=12, price=10, amount=120),
            w.OutOrderItem(out_order_id=o_ret.id, material_id=ids["mat_pcs"], quantity=4, price=10, amount=40),
        ])
        w.db.session.add(w.SystemSetting(key="price_dimension_enabled", value="0"))
        w.db.session.commit()
        req_a_id = o_req_a.id

    # Missing warehouse_id -> 400 (R2 preserved)
    r_missing = client.get("/report/api/requisition_detail")
    assert r_missing.status_code == 400

    # Single warehouse requisition_detail ignores business_type override, strips price when disabled
    r_single = client.get(
        "/report/api/requisition_detail",
        query_string={"warehouse_id": ids["wh_a"], "business_type": "其他出库"},
    )
    assert r_single.status_code == 200
    d_single = r_single.get_json()
    assert d_single["title"] == "领料明细报表"
    assert [row["order_no"] for row in d_single["data"]] == ["OUT-REQ-A"]
    assert d_single["data"][0]["order_url"] == f"/out_order/{req_a_id}"
    col_map = {c["field"]: c for c in d_single["columns"]}
    assert col_map["order_no"]["title"] == "领料单号"
    assert col_map["order_no"]["link_field"] == "order_url"
    assert col_map["customer"]["title"] == "领料部门"
    assert "price" not in col_map and "amount" not in col_map
    assert "amount" not in d_single["summary"]

    # Explicit 全部仓库 (warehouse_id=0) aggregates both warehouses + multi-unit totals
    r_all = client.get("/report/api/requisition_detail", query_string={"warehouse_id": "0"})
    assert r_all.status_code == 200
    d_all = r_all.get_json()
    assert sorted(row["order_no"] for row in d_all["data"]) == ["OUT-REQ-A", "OUT-REQ-B"]
    unit_map = {u["unit"]: u["quantity"] for u in d_all["summary"]["unit_totals"]}
    assert unit_map == {"个": 5.0, "米": 3.0}

    # Filter by department_id & picker across all warehouses
    r_dept = client.get(
        "/report/api/requisition_detail",
        query_string={"warehouse_id": "0", "department_id": ids["dept_a"]},
    )
    assert [row["order_no"] for row in r_dept.get_json()["data"]] == ["OUT-REQ-A"]

    r_picker = client.get(
        "/report/api/requisition_detail",
        query_string={"warehouse_id": "0", "picker": "李四"},
    )
    assert [row["order_no"] for row in r_picker.get_json()["data"]] == ["OUT-REQ-B"]

    # Dedicated other_out_detail: strictly 其他出库 even if business_type=领料单 passed
    r_other = client.get(
        "/report/api/other_out_detail",
        query_string={"warehouse_id": "0", "business_type": "领料单", "picker": "王五"},
    )
    assert r_other.status_code == 200
    d_other = r_other.get_json()
    assert d_other["title"] == "其他出库明细报表"
    assert [row["order_no"] for row in d_other["data"]] == ["OO-A"]
    other_cols = {c["field"]: c["title"] for c in d_other["columns"]}
    assert other_cols["order_no"] == "其他出库单号"
    assert other_cols["customer"] == "客户/领用单位"
    assert other_cols["picker"] == "领用人/经办人"

    # Print preview & excel download with warehouse_id=0
    prev = client.get("/report/requisition_detail/print_preview", query_string={"warehouse_id": "0"})
    assert prev.status_code == 200
    assert "仓库：全部仓库" in prev.get_data(as_text=True)
    xl = client.get("/report/other_out_detail/print_excel", query_string={"warehouse_id": "0"})
    assert xl.status_code == 200


def test_b2_out_order_add_header_contract_and_list_picker_filter_search(isolated_env):
    """POST /out_order/add inherits header contract/project onto blank rows while keeping
    row-level overrides; /out_order list & export filter/search/sort by picker."""
    w, client, ids = isolated_env
    r_add = client.post(
        "/out_order/add",
        json={
            "date": "2026-11-28",
            "business_type": "领料单",
            "department_id": ids["dept_a"],
            "picker": "赵六",
            "warehouse_id": ids["wh_a"],
            "contract_id": ids["contract_id"],
            "contract_no": "HT-2026-01",
            "project_name": "一号工程",
            "items": [
                {"code": "M-PCS", "quantity": 2, "price": 10, "contract_no": "", "project_name": ""},
                {"code": "M-M", "quantity": 4, "price": 20, "contract_no": "CUSTOM-99", "project_name": "自定义工程"},
            ],
        },
    )
    assert r_add.status_code == 200, r_add.get_data(as_text=True)
    order_id = r_add.get_json()["id"]

    with w.app.app_context():
        order = w.db.session.get(w.OutOrder, order_id)
        assert order.contract_id == ids["contract_id"]
        assert order.contract_no == "HT-2026-01"
        assert order.project_name == "一号工程"
        by_code = {item.material.code: item for item in order.items}
        assert by_code["M-PCS"].contract_no == "HT-2026-01"
        assert by_code["M-PCS"].project_name == "一号工程"
        assert by_code["M-M"].contract_no == "CUSTOM-99"
        assert by_code["M-M"].project_name == "自定义工程"

        # Add a second order with another picker to prove isolation
        other_order = w.OutOrder(
            order_no="OUT-OTHER-PICKER", date=date(2026, 11, 28), business_type="领料单",
            warehouse="项目仓", picker="钱七", status="pending", operator_id=ids["user"],
        )
        w.db.session.add(other_order)
        w.db.session.flush()
        w.db.session.add(w.OutOrderItem(out_order_id=other_order.id, material_id=ids["mat_pcs"], quantity=1, price=10, amount=10))
        w.db.session.commit()
        target_no = order.order_no

    # Filter by picker
    r_list = client.get("/out_order", query_string={"warehouse_id": ids["wh_a"], "picker": "赵六", "sort": "picker", "order": "asc"})
    assert r_list.status_code == 200
    html_list = r_list.get_data(as_text=True)
    assert target_no in html_list and "OUT-OTHER-PICKER" not in html_list

    # Search by picker keyword
    r_search = client.get("/out_order", query_string={"warehouse_id": ids["wh_a"], "search": "赵六"})
    assert r_search.status_code == 200
    html_search = r_search.get_data(as_text=True)
    assert target_no in html_search and "OUT-OTHER-PICKER" not in html_search

    # Export filtered by picker
    r_exp = client.get("/out_order/export", query_string={"warehouse_id": ids["wh_a"], "picker": "赵六"})
    assert r_exp.status_code == 200
    import io
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(r_exp.data))
    exported_nos = [row[0] for row in list(wb.active.iter_rows(min_row=2, values_only=True))]
    wb.close()
    assert exported_nos == [target_no, target_no]
