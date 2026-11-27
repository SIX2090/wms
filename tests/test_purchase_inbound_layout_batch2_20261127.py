# -*- coding: utf-8 -*-
"""BUG-2026-11-27-005 回归测试：采购入库第二批页面布局重构、工具栏去噪、自动草稿及详情页交互修复。

覆盖：
- P1-UI-1：app.js insertGlobalActionBar/createDocumentNavigationGroup 在 /add 新增页隐藏
  无效/危险按钮（打印/打印设置/导入/导出/导入导出模板/首张~末张），保留新增/保存/查找单据及无打印模板模块的栏目设置
- P1-UI-2/3/4/5：30→6 初始空行（in_order_add/out_order_add）、吸底栏同显行数+数量+金额并避让通知铃铛、
  只读格透明底不击穿斑马纹、flatpickr 可编辑日期白底区分、孤立单标签隐藏、表头紧凑与操作提示折叠、行模板去重
- P1-UI-6/7 & P1-BIZ-6：自动草稿改绑 #addForm、脏状态触发、按业务类型/单号分键、完整保存/恢复
  supplier_id/location/auto_push_requisition/行级合同与采购来源、全局 clearDraft、供应商改字即清旧 ID、
  exportDetailRows 动态文件名与公式注入中和
- P1-UI-9 + R6：in_order_detail 移除冲突旧版内联列设置；in_order_detail 与 out_order_detail
  批量删除明细改为严格串行 Promise 链以消除乐观锁 409 竞态
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
CUSTOM_CSS = ROOT / "app" / "static" / "css" / "custom.css"
BASE_HTML = ROOT / "app" / "templates" / "base.html"
IN_ADD_HTML = ROOT / "app" / "templates" / "in_order_add.html"
IN_DETAIL_HTML = ROOT / "app" / "templates" / "in_order_detail.html"
OUT_ADD_HTML = ROOT / "app" / "templates" / "out_order_add.html"
OUT_DETAIL_HTML = ROOT / "app" / "templates" / "out_order_detail.html"


def _node() -> str:
    node = shutil.which("node")
    assert node, "Node.js is required for frontend runtime verification"
    return node


def _extract_js_function(source: str, signature_prefix: str) -> str:
    start = source.index(signature_prefix)
    brace_open = source.index(") {", start) + 2
    depth = 0
    for idx in range(brace_open, len(source)):
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start : idx + 1]
    raise AssertionError(f"Unclosed JS function: {signature_prefix}")


def test_p1_ui_1_global_actionbar_hides_invalid_buttons_on_add_form_node_vm():
    """P1-UI-1: /add forms hide invalid print/export/import/template/print-settings and prev/next nav."""
    script = r"""
const fs = require('node:fs');
const assert = require('node:assert/strict');
const src = fs.readFileSync(process.argv[1], 'utf8');

function extract(name) {
  const start = src.indexOf('function ' + name + '(');
  assert.ok(start >= 0, 'Missing ' + name);
  let depth = 0;
  for (let i = src.indexOf('{', start); i < src.length; i++) {
    if (src[i] === '{') depth++;
    if (src[i] === '}' && --depth === 0) return src.slice(start, i + 1);
  }
  throw new Error('Unbalanced ' + name);
}

function makeEl() {
  return {
    children: [], attrs: {}, title: '', innerHTML: '', className: '',
    classList: { add() {}, contains() { return false; } },
    setAttribute(k, v) { this.attrs[k] = String(v); },
    getAttribute(k) { return k === 'title' ? this.title : (this.attrs[k] ?? null); },
    appendChild(c) { this.children.push(c); },
    addEventListener() {},
    contains(c) { return this === c || this.children.includes(c); },
  };
}

function runScenario({ pathname, orderId, printTemplateUrl }) {
  let bar = null;
  const content = { firstChild: null, insertBefore(el) { bar = el; } };
  global.window = { location: { pathname } };
  global.document = {
    body: makeEl(),
    getElementById() { return null; },
    querySelector(sel) {
      if (sel === '.embedded-content') return content;
      if (sel === '[name="order_id"]') return orderId !== undefined ? { value: orderId } : null;
      return null;
    },
    querySelectorAll() { return []; },
    createElement() { return makeEl(); },
  };
  global.isWmsEmbeddedPage = () => true;
  global.isWmsListPage = () => false;
  global.isFormPage = () => true;
  global.getCurrentRecordId = () => (orderId ? Number(orderId) : null);
  global.getWmsActionModule = () => ({
    key: 'in_order', listUrl: '/in_order', addUrl: '/in_order/add',
    deleteUrl: '/in_order/batch_delete', navigator: true, printTemplateUrl,
  });
  global.saveCurrentPage = () => {};

  const code = ['escapeHtml', 'pageHasOwnButton', 'trimWmsActionbarDividers', 'pageHasOwnListAction', 'createDocumentNavigationGroup', 'insertGlobalActionBar']
    .map(extract).join('\n');
  eval(code);
  insertGlobalActionBar();
  const actionKeys = bar.children.filter(c => c.attrs['data-wms-action']).map(c => c.attrs['data-wms-action']);
  const navGroup = bar.children.find(c => c.className === 'cb-doc-nav');
  const navLabels = navGroup ? navGroup.children.map(c => c.title) : [];
  return { actionKeys, navLabels };
}

// 1. Unsaved /in_order/add: hides print, import, export, template, print-settings, delete, and first/prev/next/last
const addIn = runScenario({ pathname: '/in_order/add', orderId: '', printTemplateUrl: '/in_order_print_template' });
assert.deepEqual(addIn.actionKeys, ['add', 'save']);
assert.deepEqual(addIn.navLabels, ['查找单据']);

// 2. /check/add (no printTemplateUrl): keeps settings (栏目设置), hides print/import/export/template
const addCheck = runScenario({ pathname: '/check/add', orderId: '', printTemplateUrl: undefined });
assert.ok(addCheck.actionKeys.includes('settings'));
assert.ok(!addCheck.actionKeys.includes('print'));
assert.ok(!addCheck.actionKeys.includes('export'));

// 3. Saved detail /in_order/12: keeps full navigation group
const detail = runScenario({ pathname: '/in_order/12', orderId: '12', printTemplateUrl: '/in_order_print_template' });
assert.deepEqual(detail.navLabels, ['查找单据', '首张', '上一张', '下一张', '末张']);
"""
    proc = subprocess.run([_node(), "-e", script, str(APP_JS)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p1_ui_2_3_4_5_css_layout_and_sticky_totals():
    """P1-UI-2/3/4/5: CSS zebra/flatpickr fixes, 6 initial rows, sticky totals, collapsible hints, row dedupe."""
    css = CUSTOM_CSS.read_text(encoding="utf-8")
    base = BASE_HTML.read_text(encoding="utf-8")
    in_add = IN_ADD_HTML.read_text(encoding="utf-8")
    out_add = OUT_ADD_HTML.read_text(encoding="utf-8")

    # P1-UI-3: readonly grid cells transparent, not white
    m_ro = re.search(r"body #materialTable tbody td input\.form-control\[readonly\]\s*\{([^}]+)\}", css)
    assert m_ro and "background: transparent !important" in m_ro.group(1)

    # P1-UI-4: flatpickr editable date display keeps white background
    assert "altInputClass: 'form-control wms-date-display'" in base
    assert ".form-control.wms-date-display[readonly]" in css

    # P1-UI-5: hide single lone detail tab via CSS & collapsible hints & compact remark
    assert ".wms-doc-tabs:has(> .wms-doc-tab:only-child)" in css
    assert "wms-entry-hints" in in_add and "<details" in in_add
    assert 'name="remark" rows="1"' in in_add

    # P1-UI-2: 6 initial blank rows + sticky summary with line count, qty, amount & bell clearance
    assert "for (let i = 0; i < 6; i++) addNewRow();" in in_add
    assert "for (let i = 0; i < 30; i++) addNewRow();" not in in_add
    assert "for (var i = 0; i < 6; i++) { addNewRow(); }" in out_add
    assert "wms-sticky-summary" in in_add and "stickyTotalAmount" in in_add and "stickyLineCount" in in_add
    assert ".quantity-summary.wms-sticky-summary" in css

    # Row template deduplicated via populateMaterialRow
    assert "function populateMaterialRow(" in in_add
    assert in_add.count('<td data-column-key="row_no" class="row-num">') == 1


def test_p1_ui_6_7_auto_draft_supplier_reset_and_csv_export_node_vm():
    """P1-UI-6/7 & P1-BIZ-6: auto-draft binds #addForm, clears stale supplier_id, sanitizes CSV export."""
    html = IN_ADD_HTML.read_text(encoding="utf-8")
    assert "#inOrderForm" not in html, "Broken #inOrderForm selector must be completely removed"
    assert "window.clearDraft = clearDraft;" in html
    assert "hiddenInput.value = '';" in html

    draft_start = html.index("// ==================== 草稿自动保存 ====================")
    draft_end = html.index("</script>", draft_start)
    draft_js = html[draft_start:draft_end]
    export_js = _extract_js_function(html, "function exportDetailRows()")

    harness = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const payload = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

// --- Part 1: Auto-draft lifecycle ---
const storage = new Map();
const formListeners = {};
const winListeners = {};
let docReady = null;
let savedTips = 0;
let addedRows = [];

function makeRow(code, qty, price, contractNo, projectName, poItemId) {
  const fields = {
    '.material-code': { value: code },
    '.material-name': { value: code ? '物料' + code : '' },
    '.material-spec': { value: '' },
    '.material-unit': { value: '' },
    '.material-qty': { value: qty },
    '.material-price': { value: price },
    '.material-box-no': { value: '' },
    '.material-batch-no': { value: '' },
    '.material-expiry': { value: '' },
    '.line-contract-no': { value: contractNo },
    '.line-project-name': { value: projectName },
    '.line-customer-supplied': { checked: false },
    '.material-remark': { value: '' },
  };
  return { dataset: { sourcePurchaseOrderItemId: poItemId || '', sourcePurchaseOrderNo: '' }, querySelector: s => fields[s] || null };
}

const formEl = {
  dataset: {},
  addEventListener(type, fn) { formListeners[type] = fn; },
};
const inputs = {
  '[name="business_type"]': { value: '采购入库' },
  '[name="order_id"]': { value: '' },
  '#supplierSearch': { value: '' },
  '#supplierIdHidden': { value: '' },
  '[name="warehouse_id"]': { value: '3' },
  '[name="location"]': { value: 'A-01' },
  '[name="auto_push_requisition"]': { checked: true },
  '[name="remark"]': { value: '' },
};
let activeRows = [];
let intervalFn = null;

const ctx = {
  Date, JSON, String, Number, Array, Object,
  inOrderSubmitting: false,
  localStorage: {
    getItem(k) { return storage.has(k) ? storage.get(k) : null; },
    setItem(k, v) { storage.set(k, String(v)); },
    removeItem(k) { storage.delete(k); },
  },
  setInterval(fn) { intervalFn = fn; return 1; },
  clearInterval() {},
  setTimeout() {},
  addNewRow() { const r = makeRow('', '', '', '', '', ''); activeRows.push(r); addedRows.push(r); return r; },
  calcAmount() {},
  calcTotal() {},
  showToast() {},
  document: {
    body: { appendChild() { savedTips++; } },
    createElement() { return { className: '', innerHTML: '', style: {}, remove() {} }; },
    addEventListener(type, fn) { if (type === 'DOMContentLoaded') docReady = fn; },
    querySelector(sel) {
      if (sel === '#addForm') return formEl;
      if (sel === '#materialTable tbody') return { set innerHTML(_) { activeRows = []; } };
      if (sel === '#materialTable tbody tr:last-child') return activeRows[activeRows.length - 1] || null;
      return inputs[sel] || null;
    },
    querySelectorAll(sel) { return sel === '#materialTable tbody tr' ? activeRows : []; },
  },
  addEventListener(type, fn) { winListeners[type] = fn; },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(payload.draftJs, ctx);
docReady();

// Untouched blank form: 30s timer MUST NOT write localStorage or spam tip
intervalFn();
assert.equal(storage.size, 0, 'Blank untouched form must not auto-save');
assert.equal(savedTips, 0);

// User types supplier & row -> markDirty fires -> 30s timer saves full fields including supplier_id & contract_no
inputs['#supplierSearch'].value = '供应商甲';
inputs['#supplierIdHidden'].value = '42';
inputs['[name="remark"]'].value = '送货单123';
activeRows = [makeRow('M001', '5', '12', 'HT-001', '园区工程', '777')];
formListeners.input();
assert.equal(formEl.dataset.modified, 'true');
intervalFn();
assert.equal(storage.size, 1);
const key = [...storage.keys()][0];
assert.ok(key.includes('采购入库'), 'Draft key must be scoped by business_type');
const saved = JSON.parse(storage.get(key)).data;
assert.equal(saved.supplier_id, '42');
assert.equal(saved.location, 'A-01');
assert.equal(saved.auto_push_requisition, true);
assert.equal(saved.rows[0].contract_no, 'HT-001');
assert.equal(saved.rows[0].source_purchase_order_item_id, '777');

// beforeunload warns when dirty
let prevented = false;
winListeners.beforeunload({ preventDefault() { prevented = true; } });
assert.equal(prevented, true);

// window.clearDraft() clears storage and disarms beforeunload
ctx.clearDraft();
assert.equal(storage.size, 0);
assert.equal(formEl.dataset.modified, 'false');
prevented = false;
winListeners.beforeunload({ preventDefault() { prevented = true; } });
assert.equal(prevented, false);

// --- Part 2: exportDetailRows dynamic filename & formula neutralization ---
let downloaded = null;
let blobText = '';
const expCtx = {
  Blob: class { constructor(parts) { blobText = parts.join(''); } },
  URL: { createObjectURL() { return 'blob:1'; }, revokeObjectURL() {} },
  document: {
    querySelector(sel) { return sel === '[name="business_type"]' ? { value: '采购入库' } : null; },
    querySelectorAll() {
      return [{
        querySelector(sel) {
          const map = {
            '.material-code': { value: '=CMD|calc' },
            '.material-brand': { value: '品牌' },
            '.material-name': { value: '+SUM(1,2)' },
            '.material-spec': { value: '-12.5' },
            '.material-unit': { value: '个' },
            '.material-qty': { value: '2' },
            '.material-price': { value: '10' },
            '.material-amount': { value: '20.00' },
            '.line-contract-no': { value: '' },
            '.line-project-name': { value: '' },
            '.material-remark': { value: '@evil' },
          };
          return map[sel] || null;
        },
      }];
    },
    createElement() { return { href: '', download: '', click() { downloaded = this.download; } }; },
  },
  showToast() {},
};
vm.createContext(expCtx);
vm.runInContext(payload.exportJs, expCtx);
expCtx.exportDetailRows();
assert.equal(downloaded, '采购入库单明细.csv');
assert.ok(blobText.includes("\"'=CMD|calc\""));
assert.ok(blobText.includes("\"'+SUM(1,2)\""));
assert.ok(blobText.includes('"-12.5"'), 'Pure signed numeric string should stay intact');
assert.ok(blobText.includes("\"'@evil\""));
"""
    proc = subprocess.run(
        [_node(), "-e", harness],
        input=json.dumps({"draftJs": draft_js, "exportJs": export_js}),
        capture_output=True, text=True, encoding="utf-8", timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_p1_ui_9_detail_single_column_settings_and_sequential_batch_delete_node_vm():
    """P1-UI-9 + R6: in_order_detail drops legacy column panel; in/out batchDeleteBtn runs strictly sequentially."""
    in_detail = IN_DETAIL_HTML.read_text(encoding="utf-8")
    out_detail = OUT_DETAIL_HTML.read_text(encoding="utf-8")

    assert "toggleColumnSettings" not in in_detail
    assert "columnSettingsPanel" not in in_detail
    assert 'data-field-settings-table="itemTable"' in in_detail

    for label, src in (("in_order_detail", in_detail), ("out_order_detail", out_detail)):
        marker = src.index("document.getElementById('batchDeleteBtn')")
        fn_src = _extract_js_function(src[marker:], "function()")
        fn_src = re.sub(r"\{\{.*?\}\}", "7", fn_src)

        harness = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const fnSrc = require('node:fs').readFileSync(0, 'utf8');

let resolvers = [];
let urls = [];
let toasts = [];
let reloaded = 0;

const ctx = {
  Promise, Array,
  document: { querySelectorAll() { return [{ value: '101' }, { value: '102' }]; } },
  showConfirm: () => Promise.resolve(true),
  _showConfirm: () => Promise.resolve(true),
  showToast: (m, t) => toasts.push({ m, t }),
  _showToast: (m, t) => toasts.push({ m, t }),
  setTimeout: fn => fn(),
  location: { reload() { reloaded++; } },
  WMS: {
    api: {
      postRaw(url) {
        urls.push(url);
        return new Promise(resolve => resolvers.push(resolve));
      },
    },
  },
};
vm.createContext(ctx);
const handler = vm.runInContext('(' + fnSrc + ')', ctx);

(async () => {
  handler();
  await new Promise(r => setImmediate(r));
  // Strictly sequential: second delete MUST NOT fire until first resolves!
  assert.equal(urls.length, 1, 'Second request fired in parallel before first completed!');
  assert.ok(urls[0].endsWith('/delete_item/101'));
  resolvers[0]({ status: 'success' });
  await new Promise(r => setImmediate(r));
  assert.equal(urls.length, 2, 'Second request must fire after first completes');
  assert.ok(urls[1].endsWith('/delete_item/102'));
  resolvers[1]({ status: 'success' });
  await new Promise(r => setImmediate(r));
  assert.equal(toasts.length, 1);
  assert.equal(toasts[0].t, 'success');
  assert.equal(reloaded, 1);
})().catch(e => { console.error(e); process.exit(1); });
"""
        proc = subprocess.run([_node(), "-e", harness], input=fn_src, capture_output=True, text=True, encoding="utf-8", timeout=20)
        assert proc.returncode == 0, f"{label} failed: {proc.stdout}{proc.stderr}"
