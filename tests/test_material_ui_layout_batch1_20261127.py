# -*- coding: utf-8 -*-
"""Regression suite for Material Management Batch 1 UI/UX & layout fixes (2026-11-27).

Covers:
1. Single streamlined toolbar (`wms-no-global-actionbar` opt-out) with identical direct
   and embedded capabilities (add / import / filtered export / download template /
   label designer / batch print / inventory alert / column settings / maintenance).
2. Contextual selection bar (`#materialSelectionBar`) hidden at 0 selection and shown
   with live count & grouped actions (preserving all 8 button IDs) on selection, plus
   one-click clear selection (`clearMaterialSelection`).
3. Single-row desktop search bar (`flex: 1 1 260px; width: auto`), narrowed 240px
   category tree, reordered daily core columns, badge-only `status` column, dedicated
   inline `actions` column (`编辑` + `更多 ▾`), cell tooltips, double-click row edit,
   and print/mobile CSS hygiene.
4. Global R6 fixes in `app/static/js/app.js`:
   - `WmsFieldSettings` (`columnsOf` / `setHeaderLabel`) ignores `.visually-hidden`
     children when recognizing checkbox-only headers (eliminates `选择□` overlap).
   - `WmsFieldSettings` and `setupDynamicDetailColumnControls` respect
     `data-disable-field-settings="true"` so `#materialTable` avoids dual-column-config
     collisions.
   - `setupSortableHeaders()` sets `data-sort-active="1"` whenever an active caret icon
     is present (eliminates `▲⇅` double sort arrows across list pages).
5. `material-list.js` column settings convergence: `min_stock` omitted when alerts are
   disabled, locked `select` + `actions`, and `resetMaterialColumns()` clearing all 4
   storage keys plus resetting `materialColumnController`.
6. `button-theme.css` `.bi-pencil-square` SVG icon mask & contextual danger distinction.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MATERIAL_HTML = ROOT / "app" / "templates" / "material.html"
MATERIAL_JS = ROOT / "app" / "static" / "js" / "pages" / "material-list.js"
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
BUTTON_CSS = ROOT / "app" / "static" / "css" / "button-theme.css"


class _HtmlInspector(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.nodes: list[tuple[str, dict[str, str], str | None]] = []
        self._form: str | None = None
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr_map = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._form = attr_map.get("id") or "form"
        self.nodes.append((tag, attr_map, self._form))

    def handle_endtag(self, tag: str):
        if tag == "form":
            self._form = None


def _run_node(script: str, payload: dict) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for frontend runtime verification")
    result = subprocess.run(
        [node, "-e", script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=25,
    )
    assert result.returncode == 0, f"Node check failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1]) if lines else {}


# ---------------------------------------------------------------------------
# Pure static & Node runtime checks (no app import required)
# ---------------------------------------------------------------------------

def test_static_template_css_and_csp_contracts():
    """Verify Batch 1 template markup, CSS rules, and strict-CSP hygiene."""
    html = MATERIAL_HTML.read_text(encoding="utf-8")
    css = BUTTON_CSS.read_text(encoding="utf-8")
    js = MATERIAL_JS.read_text(encoding="utf-8")

    # 1. Single-toolbar opt-out
    assert "{% block body_class %}wms-no-global-actionbar{% endblock %}" in html

    # 2. Streamlined top header anchors (direct & embedded parity)
    for token in (
        'id="toolbarAddBtn"',
        'data-bs-target="#addModal"',
        'id="toolbarImportExportBtn"',
        'href="/batch_import?type=material"',
        "url_for('export_material'",
        "url_for('download_material_template')",
        'id="toolbarLabelMenuBtn"',
        'data-material-action="openLabelTemplate"',
        "url_for('print_batch_labels')",
        'href="/alert"',
        'id="toolbarColumnBtn"',
        'id="toolbarMaintenanceBtn"',
        'data-bs-target="#repairMaterialFields"',
    ):
        assert token in html, f"Missing top toolbar token: {token}"

    # 3. Contextual selection bar & all 8 preserved action IDs
    assert 'id="materialSelectionBar" hidden' in html
    assert 'id="materialSelectionCount"' in html
    assert 'id="materialClearSelectionBtn"' in html
    assert 'data-material-action="clearMaterialSelection"' in html
    for btn_id in (
        "toolbarEditBtn",
        "toolbarBatchEditBtn",
        "toolbarCopyBtn",
        "toolbarFindImageBtn",
        "toolbarPrintBtn",
        "toolbarRemotePrintBtn",
        "toolbarMergeBtn",
        "toolbarDeleteBtn",
    ):
        assert f'id="{btn_id}"' in html, f"Missing preserved button #{btn_id}"

    # 4. Table setup: field-settings opt-out, active sort attribute, column order, pure status + actions column
    assert 'id="materialTable" data-disable-field-settings="true"' in html
    for sort_field in ("code", "name", "brand", "spec", "storage_location", "stock", "price", "category_id", "supplier_id"):
        assert f"if sort_by=='{sort_field}' %}} data-sort-active=\"1\"" in html, f"Missing data-sort-active for {sort_field}"

    thead = html[html.index("<thead>"):html.index("</thead>")]
    col_keys = re.findall(r'data-column-key="([^"]+)"', thead)
    assert col_keys[:11] == [
        "select", "code", "name", "brand", "spec", "storage_location",
        "stock", "unit", "price", "status", "actions",
    ], f"Core columns should come first: {col_keys}"
    assert col_keys[11:] == ["category", "supplier", "purpose", "min_stock", "remark", "image"]

    # Status td must only render badges; actions td holds edit + dropdown
    tbody = html[html.index("<tbody>"):html.index("</tbody>")]
    status_td = re.search(r'<td data-column-key="status">([\s\S]*?)</td>', tbody)
    assert status_td is not None
    assert "<button" not in status_td.group(1), "Status cell should be badge-only"
    actions_td = re.search(r'<td data-column-key="actions"[^>]*>([\s\S]*?)</td>', tbody)
    assert actions_td is not None
    for action_name in ("editMaterialRow", "copyMaterialRow", "findMaterialImage", "toggleMaterialStatus", "mergeMaterialInto"):
        assert f'data-material-action="{action_name}"' in actions_td.group(1), f"Missing row action {action_name}"

    # 5. Layout & print/mobile CSS
    assert ".material-search-form .material-search-input" in html
    assert "flex: 1 1 260px;" in html and "width: auto;" in html
    assert "grid-template-columns: 240px minmax(0, 1fr);" in html
    assert ".material-selection-bar" in html[html.index("@media print"):]
    assert '#materialTable th[data-column-key="actions"]' in html[html.index("@media print"):]
    assert "px-3 pb-3" in html
    assert '"inventoryAlertEnabled":' in html

    # 6. Unified icon family & danger cues in button-theme.css
    assert "body .btn .bi-pencil-square {" in css
    assert "body .btn .bi-pencil-square::before," in css
    assert "body .material-selection-bar .btn.btn-outline-danger:not(:disabled):not(.disabled)" in css

    # 7. Strict CSP checks on template & JS
    assert not re.search(r'\bon[a-z]+\s*=', html, re.I), "Inline on* event handler violates /material strict CSP"
    assert "{{" not in js and "{%" not in js
    assert not re.search(r'\bon(?:click|change|input|error)\s*=\s*["\']', js)


def test_app_js_checkbox_visually_hidden_disable_and_sortable_active_runtime():
    """Execute real app.js WmsFieldSettings, setupDynamicDetailColumnControls & setupSortableHeaders in Node."""
    app_src = APP_JS.read_text(encoding="utf-8")
    field_settings_src = app_src[
        app_src.index("// Unified document-grid field settings,"):
        app_src.index("// Global fill-down controls")
    ]
    dynamic_src = app_src[
        app_src.index("function setupDynamicDetailColumnControls("):
        app_src.index("function autoSetupResizableTables(")
    ]
    sortable_start = app_src.index("function setupSortableHeaders()")
    sortable_src = app_src[sortable_start:app_src.index("\n// 单个删除", sortable_start)]
    helper_start = app_src.index("function rememberWmsColumnDefaults(")
    helper_src = app_src[helper_start:app_src.index("\n}", helper_start) + 2]
    escape_start = app_src.index("function escapeHtml(")
    escape_src = app_src[escape_start:app_src.index("\n}", escape_start) + 2]

    program = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));

class El {
  constructor(tag, opts = {}) {
    this.tagName = tag.toUpperCase();
    this.nodeType = 1;
    this.type = opts.type || '';
    this.id = opts.id || '';
    this.children = [];
    this.childNodes = [];
    this.parentElement = null;
    this.dataset = Object.assign({}, opts.dataset || {});
    this.attrs = {};
    this.style = {};
    this.handlers = {};
    this.classes = new Set(opts.classes || []);
    this.classList = {
      contains: c => this.classes.has(c),
      add: c => this.classes.add(c),
      remove: c => this.classes.delete(c),
      toggle: (c, force) => (force === undefined ? (this.classes.has(c) ? this.classes.delete(c) : this.classes.add(c)) : (force ? this.classes.add(c) : this.classes.delete(c))),
    };
  }
  get cells() { return this.children; }
  get firstChild() { return this.childNodes[0] || this.children[0] || null; }
  appendChild(node) {
    if (node.fragment) { [...node.children].forEach(c => this.appendChild(c)); return node; }
    if (node.parentElement) {
      const idx = node.parentElement.children.indexOf(node);
      if (idx >= 0) node.parentElement.children.splice(idx, 1);
    }
    if (node.nodeType === 1) this.children.push(node);
    this.childNodes.push(node);
    node.parentElement = this;
    return node;
  }
  insertBefore(node, ref) {
    const idx = this.childNodes.indexOf(ref);
    if (idx >= 0) this.childNodes.splice(idx, 0, node);
    else this.childNodes.unshift(node);
    return node;
  }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  closest() { return null; }
  querySelector(sel) {
    if (sel === '.bi-caret-up-fill, .bi-caret-down-fill') {
      return this.children.find(c => c.classes.has('bi-caret-up-fill') || c.classes.has('bi-caret-down-fill')) || null;
    }
    if (sel === 'thead tr') return this._headerRow || null;
    if (sel === 'tbody') return this._tbody || null;
    if (sel.startsWith('thead th[data-column-key="')) {
      const key = sel.match(/="([^"]+)"/)[1];
      return (this._headerRow?.children || []).find(c => c.dataset.columnKey === key) || null;
    }
    return null;
  }
  querySelectorAll(sel) {
    if (sel === 'thead th[data-column-key]') return (this._headerRow?.children || []).filter(c => c.dataset.columnKey);
    if (sel === 'tbody tr, tfoot tr') return this._tbody ? this._tbody.children : [];
    if (sel === 'thead th .col-resize') return [];
    if (sel.startsWith('[data-column-key="')) {
      const key = sel.match(/="([^"]+)"/)[1];
      return this.rows.flatMap(r => r.children).filter(c => c.dataset.columnKey === key);
    }
    return [];
  }
}

function makeTable(id, disableFieldSettings) {
  const table = new El('table', { id, dataset: disableFieldSettings ? { disableFieldSettings: 'true' } : {} });
  const headerRow = new El('tr');
  // Checkbox th WITH .visually-hidden span (exact pattern from material.html)
  const thSelect = new El('th', { dataset: { columnKey: 'select', defaultLabel: '选择' } });
  const srSpan = new El('span', { classes: ['visually-hidden'] });
  srSpan.childNodes.push({ nodeType: 3, textContent: '选择' });
  const checkbox = new El('input', { type: 'checkbox', id: 'checkAll' });
  thSelect.appendChild(srSpan);
  thSelect.appendChild(checkbox);
  // Active sortable th (has caret icon, no data-sort-active yet)
  const thCode = new El('th', { classes: ['sortable-header'], dataset: { columnKey: 'code', sortable: 'code' } });
  thCode.childNodes.push({ nodeType: 3, textContent: '物料编码 ' });
  thCode.appendChild(new El('i', { classes: ['bi', 'bi-caret-up-fill'] }));
  // Inactive sortable th (no caret icon)
  const thName = new El('th', { classes: ['sortable-header'], dataset: { columnKey: 'name', sortable: 'name' } });
  thName.childNodes.push({ nodeType: 3, textContent: '物料名称 ' });

  headerRow.appendChild(thSelect);
  headerRow.appendChild(thCode);
  headerRow.appendChild(thName);

  const tbody = new El('tbody');
  const row = new El('tr');
  for (const key of ['select', 'code', 'name']) {
    const td = new El('td', { dataset: { columnKey: key } });
    row.appendChild(td);
  }
  tbody.appendChild(row);
  table._headerRow = headerRow;
  table._tbody = tbody;
  table.tHead = { rows: [headerRow] };
  table.tBodies = [tbody];
  Object.defineProperty(table, 'rows', { get: () => [headerRow, ...tbody.children] });
  return { table, thSelect, thCode, thName };
}

const normal = makeTable('normalTable', false);
const optedOut = makeTable('materialTable', true);
const store = new Map([
  ['wms:field-settings:v3:/material:materialTable', JSON.stringify({ order: ['select', 'name', 'code'], hidden: ['name'], labels: { select: '选择' } })],
  ['wms:field-settings:v3:/material:normalTable', JSON.stringify({ order: ['select', 'code', 'name'], hidden: [], labels: { select: '选择' } })],
]);
const listeners = {};
const document = {
  body: new El('body'),
  head: new El('head'),
  querySelectorAll(sel) {
    if (sel === 'table') return [normal.table, optedOut.table];
    if (sel === '.sortable-header[data-sortable]') return [normal.thCode, normal.thName, optedOut.thCode, optedOut.thName];
    return [];
  },
  querySelector(sel) { return sel === '#materialTable' ? optedOut.table : null; },
  getElementById(id) { return id === 'wms-detail-column-style' ? {} : null; },
  createElement(tag) { return new El(tag); },
  createDocumentFragment() { return Object.assign(new El('fragment'), { fragment: true }); },
  createTextNode(text) { return { nodeType: 3, textContent: text }; },
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
};

const ctx = {
  document,
  location: { pathname: '/material', href: 'http://localhost/material' },
  CSS: { escape: v => v },
  Node: { ELEMENT_NODE: 1 },
  URL,
  console,
  localStorage: {
    getItem: k => store.has(k) ? store.get(k) : null,
    setItem: (k, v) => store.set(k, v),
    removeItem: k => store.delete(k),
  },
  MutationObserver: class { observe() {} },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(
  payload.escape_src + '\n' + payload.helper_src + '\n' + payload.dynamic_src + '\n' +
  payload.sortable_src + '\n' + payload.field_settings_src,
  ctx
);

// Trigger DOMContentLoaded for WmsFieldSettings.initializeTables()
(listeners.DOMContentLoaded || []).forEach(fn => fn());

// 1. Normal table initialized by WmsFieldSettings, checkbox header has NO visible text node injected!
assert.equal(normal.table.dataset.fieldSettingsReady, '1');
const visibleTextInSelect = normal.thSelect.childNodes
  .filter(n => n.nodeType === 3)
  .map(n => n.textContent.trim())
  .join('');
assert.equal(visibleTextInSelect, '', 'visually-hidden checkbox header must not get visible text injected');
assert.equal(normal.thSelect.dataset.defaultLabel, '', 'checkbox column defaultLabel must normalize to empty string');

// 2. Opted-out table (#materialTable) completely skipped by WmsFieldSettings (no legacy hidden classes)
assert.equal(optedOut.table.dataset.fieldSettingsReady, undefined);
assert.equal(optedOut.thName.classes.has('wms-field-column-hidden'), false);

// 3. setupDynamicDetailColumnControls respects data-disable-field-settings="true" and ignores legacy shared order
ctx.setupDynamicDetailColumnControls({
  tableSelector: '#materialTable',
  orderKey: 'material_col_order_v1',
  widthKey: 'material_col_widths_v1',
  lockedColumns: ['select'],
});
const orderAfterInit = optedOut.table._headerRow.children.map(th => th.dataset.columnKey);
assert.deepEqual(orderAfterInit, ['select', 'code', 'name'], 'opted-out table must ignore legacy wms:field-settings order');

// 4. setupSortableHeaders sets data-sort-active="1" only on active sorted headers across all tables
ctx.setupSortableHeaders();
assert.equal(normal.thCode.dataset.sortActive, '1');
assert.equal(normal.thName.dataset.sortActive, undefined);
assert.equal(optedOut.thCode.dataset.sortActive, '1');
assert.equal(optedOut.thName.dataset.sortActive, undefined);

console.log(JSON.stringify({ ok: true, orderAfterInit }));
"""
    out = _run_node(program, {
        "escape_src": escape_src,
        "helper_src": helper_src,
        "dynamic_src": dynamic_src,
        "sortable_src": sortable_src,
        "field_settings_src": field_settings_src,
    })
    assert out == {"ok": True, "orderAfterInit": ["select", "code", "name"]}


def test_material_list_js_selection_bar_column_reset_and_dblclick_runtime():
    """Execute real material-list.js selection bar, column settings, reset, and dblclick handlers in Node."""
    js_src = MATERIAL_JS.read_text(encoding="utf-8")
    toolbar_slice = js_src[
        js_src.index("var materialDeleteBusy = false;"):
        js_src.index("// 2026-09-25：物料停用")
    ]
    col_start = js_src.index("// ==================== 列设置（显示/隐藏字段） ====================")
    col_end = js_src.index("initQuickSelects();", col_start)
    col_slice = js_src[col_start:col_end] + "\n});"

    program = r"""
const vm = require('node:vm');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));

class El {
  constructor(id, tag = 'div', opts = {}) {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.disabled = false;
    this.checked = false;
    this.indeterminate = false;
    this.hidden = !!opts.hidden;
    this.value = opts.value || '';
    this.textContent = '';
    this.innerHTML = '';
    this.dataset = Object.assign({}, opts.dataset || {});
    this.handlers = {};
    this.classes = new Set(opts.classes || []);
    this.classList = {
      contains: c => this.classes.has(c),
      add: c => this.classes.add(c),
      remove: c => this.classes.delete(c),
      toggle: (c, force) => (force === undefined ? (this.classes.has(c) ? this.classes.delete(c) : this.classes.add(c)) : (force ? this.classes.add(c) : this.classes.delete(c))),
    };
  }
  addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
  closest(sel) {
    if (this._closestMap && this._closestMap[sel] !== undefined) return this._closestMap[sel];
    return null;
  }
  querySelectorAll() { return []; }
  contains() { return false; }
}

const nodes = new Map();
for (const id of [
  'toolbarEditBtn', 'toolbarBatchEditBtn', 'toolbarCopyBtn', 'toolbarPrintBtn',
  'toolbarRemotePrintBtn', 'toolbarFindImageBtn', 'toolbarDeleteBtn', 'toolbarMergeBtn',
  'toolbarColumnBtn', 'materialColSettingsPanel', 'materialColOptions', 'checkAll',
]) nodes.set(id, new El(id));
nodes.set('materialSelectionBar', new El('materialSelectionBar', 'div', { hidden: true }));
nodes.set('materialSelectionCount', new El('materialSelectionCount', 'strong'));

const thSelect = new El('th_sel', 'th', { dataset: { columnKey: 'select' } });
const thActions = new El('th', 'th', { dataset: { columnKey: 'actions' } });
const thBrand = new El('th', 'th', { dataset: { columnKey: 'brand' }, classes: ['wms-field-column-hidden'] });
const tdSelect = new El('td', 'td', { dataset: { columnKey: 'select' } });
const tdActions = new El('td', 'td', { dataset: { columnKey: 'actions' } });
const tdBrand = new El('td', 'td', { dataset: { columnKey: 'brand' }, classes: ['wms-field-column-hidden'] });
const row1 = new El('tr', 'tr', { dataset: { materialId: '42' } });
row1.querySelectorAll = sel => sel === 'td[data-column-key]' ? [tdSelect, tdActions, tdBrand] : [];

const checks = ['101', '102', '103'].map(v => new El('cb_' + v, 'input', { value: v, classes: ['check-item'] }));
const table = new El('materialTable', 'table');
table.querySelectorAll = sel => {
  if (sel === '.wms-field-column-hidden') return [thBrand, tdBrand].filter(n => n.classes.has('wms-field-column-hidden'));
  if (sel === 'thead th[data-column-key]') return [thSelect, thActions, thBrand];
  if (sel === 'tbody tr') return [row1];
  if (sel === '.material-row-more-btn') return [];
  return [];
};
nodes.set('materialTable', table);

const store = new Map([
  ['material_col_visibility_v1', JSON.stringify(['brand', 'select', 'actions'])],
  ['material_col_order_v1', JSON.stringify(['select', 'brand', 'actions'])],
  ['material_col_widths_v1', JSON.stringify({ brand: 199 })],
  ['wms:field-settings:v3:/material:materialTable', JSON.stringify({ hidden: ['brand'] })],
]);

let docListeners = {};
const toasts = [];
let controllerResets = 0;
let dynamicSetupConfig = null;
const editedIds = [];

const ctx = {
  materialPageData: { canDelete: true, inventoryAlertEnabled: false, urls: {} },
  document: {
    getElementById: id => nodes.get(id) || null,
    querySelectorAll: sel => sel === '#materialTable .check-item:checked' ? checks.filter(c => c.checked) : [],
    addEventListener: (type, fn) => (docListeners[type] ||= []).push(fn),
  },
  localStorage: {
    getItem: k => store.has(k) ? store.get(k) : null,
    setItem: (k, v) => store.set(k, v),
    removeItem: k => store.delete(k),
  },
  initCheckAll() {},
  setupDynamicDetailColumnControls(cfg) {
    dynamicSetupConfig = cfg;
    return { reset() { controllerResets++; } };
  },
  showToast(msg, type) { toasts.push({ msg, type }); },
  editMaterial(id) { editedIds.push(id); },
  console, JSON, Set, Array, Number, String, Object,
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(payload.toolbar_slice + '\n' + payload.col_slice, ctx);

// Trigger DOMContentLoaded
(docListeners.DOMContentLoaded || []).forEach(fn => fn());

// 1. Selection bar hidden at 0 selection
assert.equal(nodes.get('materialSelectionBar').hidden, true);
assert.equal(nodes.get('materialSelectionCount').textContent, '0');

// 2. Legacy wms-field-column-hidden removed on load; locked select/actions never hidden even if in saved visibility
assert.equal(thBrand.classes.has('wms-field-column-hidden'), false);
assert.equal(tdBrand.classes.has('wms-field-column-hidden'), false);
assert.equal(thBrand.classes.has('cb-detail-hidden'), true);
assert.equal(thSelect.classes.has('cb-detail-hidden'), false);
assert.equal(thActions.classes.has('cb-detail-hidden'), false);
assert.deepEqual(Array.from(dynamicSetupConfig.lockedColumns), ['select', 'actions']);
assert.equal(typeof dynamicSetupConfig.minWidths.brand, 'number');
assert.equal(typeof dynamicSetupConfig.minWidths.status, 'number');
assert.equal(typeof dynamicSetupConfig.minWidths.actions, 'number');

// 3. inventoryAlertEnabled=false omits min_stock from column defaults
const keysDisabled = ctx.getMaterialColDefaults().map(c => c.key);
assert.equal(keysDisabled.includes('min_stock'), false);
ctx.materialPageData.inventoryAlertEnabled = true;
const keysEnabled = ctx.getMaterialColDefaults().map(c => c.key);
assert.equal(keysEnabled.includes('min_stock'), true);

// 4. Selecting 2 rows reveals bar & updates count; clearMaterialSelection resets everything
checks[0].checked = true;
checks[1].checked = true;
nodes.get('checkAll').indeterminate = true;
ctx.updateToolbarButtons();
assert.equal(nodes.get('materialSelectionBar').hidden, false);
assert.equal(nodes.get('materialSelectionCount').textContent, '2');
assert.equal(nodes.get('toolbarEditBtn').disabled, true);
assert.equal(nodes.get('toolbarBatchEditBtn').disabled, false);
assert.equal(nodes.get('toolbarMergeBtn').disabled, false);

ctx.clearMaterialSelection();
assert.equal(checks.some(c => c.checked), false);
assert.equal(nodes.get('checkAll').checked, false);
assert.equal(nodes.get('checkAll').indeterminate, false);
assert.equal(nodes.get('materialSelectionBar').hidden, true);
assert.equal(nodes.get('materialSelectionCount').textContent, '0');

// 5. resetMaterialColumns clears all 4 storage keys, calls controller.reset(), and unhides columns
ctx.resetMaterialColumns();
assert.equal(store.has('material_col_visibility_v1'), false);
assert.equal(store.has('material_col_order_v1'), false);
assert.equal(store.has('material_col_widths_v1'), false);
assert.equal(store.has('wms:field-settings:v3:/material:materialTable'), false);
assert.equal(controllerResets, 1);
assert.equal(thBrand.classes.has('cb-detail-hidden'), false);
assert.equal(tdBrand.classes.has('cb-detail-hidden'), false);

// 6. Double-click on data cell edits material; double-click on interactive element is ignored
const dataTarget = new El('cell', 'td');
dataTarget._closestMap = {
  'input, button, a, img, select, textarea, label, .dropdown, .dropdown-menu': null,
  'tbody tr[data-material-id]': row1,
};
const btnTarget = new El('btn', 'button');
btnTarget._closestMap = {
  'input, button, a, img, select, textarea, label, .dropdown, .dropdown-menu': btnTarget,
  'tbody tr[data-material-id]': row1,
};
(table.handlers.dblclick || []).forEach(fn => {
  fn({ target: btnTarget });
  fn({ target: dataTarget });
});
assert.deepEqual(editedIds, [42]);

console.log(JSON.stringify({ ok: true, editedIds, controllerResets }));
"""
    out = _run_node(program, {"toolbar_slice": toolbar_slice, "col_slice": col_slice})
    assert out == {"ok": True, "editedIds": [42], "controllerResets": 1}


# ---------------------------------------------------------------------------
# Full Flask isolated-app render checks (executed in CI isolated container)
# ---------------------------------------------------------------------------

@pytest.fixture
def material_ui_client(monkeypatch):
    import app as wms
    from config import ProductionConfig
    from werkzeug.security import generate_password_hash

    monkeypatch.setitem(wms.app.config, "SECURITY_HEADERS", dict(ProductionConfig.SECURITY_HEADERS))
    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "WTF_CSRF_ENABLED", False)
    with wms.app.app_context():
        assert str(wms.db.engine.url) == "sqlite:///:memory:"
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(
            username="admin",
            password_hash=generate_password_hash("secret"),
            role="admin",
            must_change_password=False,
        )
        cat = wms.MaterialCategory(code="CAT-1", name="电气元件")
        unit = wms.Unit(code="PCS", name="个")
        sup = wms.Supplier(code="SUP-1", name="测试供应商")
        wms.db.session.add_all([user, cat, unit, sup])
        wms.db.session.flush()
        mat = wms.Material(
            code="UI-001",
            name="交流接触器 LC1D25",
            brand="施耐德",
            spec="25A 220V",
            storage_location="A-02-01",
            category_id=cat.id,
            unit_id=unit.id,
            supplier_id=sup.id,
            stock=12,
            min_stock=5,
            price=88.5,
            remark="批量优化测试物料",
        )
        wms.db.session.add(mat)
        wms.set_system_setting("inventory_alert_enabled", "1")
        wms.db.session.commit()
        uid = user.id
        cat_id = cat.id
    client = wms.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
    yield client, wms, cat_id
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


@pytest.mark.parametrize("embedded", [False, True])
def test_rendered_material_page_parity_csp_and_layout(material_ui_client, embedded):
    """Both direct /material and embedded /material?embedded=1 render complete single-toolbar UI with strict CSP."""
    client, _, cat_id = material_ui_client
    url = f"/material?search=UI&category_id={cat_id}&status=all&sort=name&order=desc"
    if embedded:
        url += "&embedded=1"
    resp = client.get(url)
    assert resp.status_code == 200
    policies = resp.headers.getlist("Content-Security-Policy")
    assert len(policies) == 2 and "script-src-attr 'none'" in policies[1]

    html = resp.get_data(as_text=True)
    assert 'class="wms-no-global-actionbar' in html
    assert 'id="toolbarAddBtn"' in html
    assert '/material/export?' in html
    assert f"category_id={cat_id}" in html
    assert "sort=name" in html and "order=desc" in html
    assert 'id="materialSelectionBar" hidden' in html
    assert 'id="materialTable" data-disable-field-settings="true"' in html

    # Active sort header gets data-sort-active="1"; inactive code header does not
    name_th = re.search(r'<th[^>]*data-column-key="name"[^>]*>', html)
    code_th = re.search(r'<th[^>]*data-column-key="code"[^>]*>', html)
    assert name_th and 'data-sort-active="1"' in name_th.group(0)
    assert code_th and 'data-sort-active="1"' not in code_th.group(0)

    # Strict CSP & accessible form controls
    nodes = _HtmlInspector(html).nodes
    assert not [(t, k) for t, a, _ in nodes for k in a if re.fullmatch(r"on[a-z]+", k)]
    assert not [a["href"] for _, a, _ in nodes if a.get("href", "").lower().startswith("javascript:")]
    labels = {a.get("for") for t, a, _ in nodes if t == "label" and a.get("for")}
    for tag, attrs, form in nodes:
        if not form or tag not in {"input", "select", "textarea"}:
            continue
        if attrs.get("type") in {"hidden", "submit", "button", "checkbox", "radio"}:
            continue
        assert attrs.get("id") in labels or attrs.get("aria-label") or attrs.get("aria-labelledby"), (form, attrs)

    # JSON payload exposes inventoryAlertEnabled
    match = re.search(r'<script type="application/json" id="material-list-data">([\s\S]*?)</script>', html)
    assert match is not None
    data = json.loads(match.group(1))
    assert data["inventoryAlertEnabled"] is True


def test_rendered_material_page_when_inventory_alert_disabled(material_ui_client):
    """When inventory alerts are disabled, /alert link and min_stock column hide and JSON passes false."""
    client, wms, _ = material_ui_client
    with wms.app.app_context():
        wms.set_system_setting("inventory_alert_enabled", "0")
        wms.db.session.commit()
    resp = client.get("/material")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'href="/alert"' not in html
    assert 'data-column-key="min_stock"' not in html
    match = re.search(r'<script type="application/json" id="material-list-data">([\s\S]*?)</script>', html)
    assert match is not None
    assert json.loads(match.group(1))["inventoryAlertEnabled"] is False
