# -*- coding: utf-8 -*-
"""BUG-2026-11-27-003 回归测试：物料管理第三批权限口径、筛选保活、标签设计器与入口收敛。

覆盖（按用户拍板口径）：
- P0-2：向 warehouse 开放「物料管理 / 物料分类 / 计量单位 / 供应商 / 客户」侧边栏入口，其余管理项仍限 admin，production 仍隔离
- P1-6：网上找图收紧 warehouse 角色 + 限流（429）；/material/export 对齐 warehouse+finance 且按 price_dimension_enabled 控制单价列；/mobile/material 按 price_dimension_enabled 控制单价行
- P1-7：搜索表单与分类树保活 per_page/sort/order；切停用/全部显示清除按钮并切 material_all 联想（含库位与停用徽章）
- P1-8：标签设计器补 brand 字段与示例数据、修 deleteCol 越界与误删合并格、修 cellColspan 同步邻格、原地更新同步保存模板名
- P1-9：/material/add 补齐用途/最大库存/有效期/预警天数/图片字段并保留初始库存兼容
- P1-11：清理 /label_template 无效批量导入链接与被忽略的 cell_width/cell_height 字段
- P2-1/P2-3：表单 min=0/maxlength/不可改编码只读提示、合并两份物料导入模板实现、Modal 复用与 doPrint 弹窗拦截保护
"""
from __future__ import annotations

import ast
import io
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE_HTML = ROOT / "app" / "templates" / "base.html"
MATERIAL_HTML = ROOT / "app" / "templates" / "material.html"
MATERIAL_ADD_HTML = ROOT / "app" / "templates" / "material_add.html"
MOBILE_DETAIL_HTML = ROOT / "app" / "templates" / "mobile_material_detail.html"
LABEL_TPL_HTML = ROOT / "app" / "templates" / "label_template.html"
MATERIAL_ROUTE = ROOT / "app" / "routes" / "material.py"
EXPORT_ROUTE = ROOT / "app" / "routes" / "export.py"
OPTIONS_ROUTE = ROOT / "app" / "routes" / "options_api.py"
LABEL_ROUTE = ROOT / "app" / "routes" / "label_barcode.py"
MATERIAL_JS = ROOT / "app" / "static" / "js" / "pages" / "material-list.js"
QUICK_SELECT_JS = ROOT / "app" / "static" / "js" / "quick-select.js"


def _extract_func_source(path: Path, func_name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            lines = src.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function {func_name} not found in {path}")


# =============================================================================
# Part A: Pure static / AST / Jinja / Node-VM tests (no DB or app import)
# =============================================================================

def test_p0_2_warehouse_sidebar_five_master_links_jinja():
    """P0-2: base.html opens 5 master-data entries to warehouse in both menus while isolating admin-only & production."""
    base_src = BASE_HTML.read_text(encoding="utf-8")
    flyout_match = re.search(
        r'<div class="flyout-title">基础资料</div>(.*?)</div>\s*</li>',
        base_src,
        re.S,
    )
    submenu_match = re.search(
        r'基础资料</span>.*?<ul class="submenu-list">(.*?)</ul>',
        base_src,
        re.S,
    )
    assert flyout_match and submenu_match
    for menu_block in (flyout_match.group(1), submenu_match.group(1)):
        wh_block = re.search(
            r"\{% if current_user\.role in \['admin', 'warehouse'\] %\}(.*?)\{% endif %\}",
            menu_block,
            re.S,
        )
        admin_block = re.search(
            r"\{% if current_user\.role == 'admin' %\}(.*?)\{% endif %\}",
            menu_block,
            re.S,
        )
        assert wh_block is not None and admin_block is not None
        for href in ("/material", "/category", "/unit", "/supplier", "/customer"):
            assert f'href="{href}"' in wh_block.group(1), f"{href} missing in warehouse block"
        for href in ("/contract", "/opening_stock", "/warehouse", "/department", "/employee"):
            assert f'href="{href}"' in admin_block.group(1), f"{href} must remain admin-only"
            assert f'href="{href}"' not in wh_block.group(1), f"{href} leaked into warehouse block"


def test_p1_6_image_search_and_export_contracts_ast():
    """P1-6 + P2-3: Role/rate-limit/price-dimension guards and single template builder."""
    mat_src = MATERIAL_ROUTE.read_text(encoding="utf-8")
    assert "def build_material_import_template_stream():" in mat_src

    img_cand_block = re.search(
        r"@app\.route\('/material/<int:id>/image_candidates'\)(.*?)def material_image_select",
        mat_src,
        re.S,
    )
    assert img_cand_block is not None
    img_cand_text = img_cand_block.group(1)
    assert "@require_role('warehouse')" in img_cand_text
    assert "is_rate_limited(" in img_cand_text and "record_failure(" in img_cand_text and "429" in img_cand_text

    exp_block = re.search(
        r"@app\.route\('/material/export'\)(.*?)def import_material",
        mat_src,
        re.S,
    )
    assert exp_block is not None
    exp_text = exp_block.group(1)
    assert "@require_role('warehouse', 'finance')" in exp_text
    assert "price_dimension_enabled" in exp_text
    assert "if include_price:" in exp_text

    dl_src = _extract_func_source(MATERIAL_ROUTE, "download_material_template")
    exp_tpl_src = _extract_func_source(EXPORT_ROUTE, "export_material_template")
    assert "build_material_import_template_stream()" in dl_src
    assert "build_material_import_template_stream()" in exp_tpl_src


def test_p1_6_mobile_detail_respects_price_dimension_jinja():
    """P1-6: mobile_material_detail.html hides 单价 when price_dimension_enabled is False and shows when True."""
    from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(ROOT / "app/templates"),
        ]),
        autoescape=True,
    )
    env.filters["quantity"] = lambda v: str(v or 0)
    tpl = env.get_template("mobile_material_detail.html")
    mat = NS(
        code="M-P", name="单价测试料", brand="B", spec="S", storage_location="",
        unit=NS(name="个"), category=NS(name="类"), supplier=NS(name="供"),
        purpose="", price=88.5, min_stock=0, max_stock=0, reorder_point=0,
        expiry_date=None, alert_days=30, status="active", remark="", created_at="2026-11-27",
        image=None,
    )
    common = dict(
        material=mat, images=[], warehouses=[], warehouse=None, stock=0,
        request=NS(args={}), current_user=NS(is_authenticated=True, role="warehouse"),
        url_for=lambda ep, **kw: f"/{ep}",
    )
    html_off = tpl.render(price_dimension_enabled=False, **common)
    html_on = tpl.render(price_dimension_enabled=True, **common)
    assert "<dt class=\"col-4 mb-2 text-muted\">单价</dt>" not in html_off
    assert "88.5" not in html_off
    assert "<dt class=\"col-4 mb-2 text-muted\">单价</dt>" in html_on
    assert "88.5" in html_on


def test_p1_7_p1_9_p1_11_p2_1_templates_and_options_contracts():
    """P1-7/P1-8/P1-9/P1-11/P2-1 static template and route contracts."""
    mat_html = MATERIAL_HTML.read_text(encoding="utf-8")
    assert 'name="per_page" value="{{ per_page }}"' in mat_html
    assert 'name="sort" value="{{ sort_by }}"' in mat_html
    assert 'name="order" value="{{ sort_order }}"' in mat_html
    assert "status_filter != 'active'" in mat_html
    assert "material_all" in mat_html
    assert "per_page=per_page, sort=sort_by, order=sort_order" in mat_html
    assert 'data-field="brand" data-label="品牌"' in mat_html
    assert '<option value="brand">品牌</option>' in mat_html
    assert "{% if not material_code_editable %}readonly{% endif %}" in mat_html
    for num_id in ("add_price", "add_min_stock", "add_max_stock", "add_reorder_point", "edit_price", "edit_min_stock", "edit_max_stock", "edit_reorder_point"):
        assert re.search(rf'id="{num_id}"[^>]*min="0"', mat_html), f"{num_id} missing min=0"

    opt_src = OPTIONS_ROUTE.read_text(encoding="utf-8")
    assert "'material_all'" in opt_src
    assert "_POOL_CACHE.pop('material_all', None)" in opt_src

    add_html = MATERIAL_ADD_HTML.read_text(encoding="utf-8")
    assert 'enctype="multipart/form-data"' in add_html
    for field_name in ('name="purpose"', 'name="max_stock"', 'name="expiry_date"', 'name="alert_days"', 'name="image"', 'name="stock"'):
        assert field_name in add_html, f"material_add.html missing {field_name}"

    lt_html = LABEL_TPL_HTML.read_text(encoding="utf-8")
    assert "/batch_import?type=label_template" not in lt_html
    assert 'name="cell_width"' not in lt_html and 'name="cell_height"' not in lt_html

    save_layout_src = _extract_func_source(LABEL_ROUTE, "save_label_template_layout")
    assert "payload.get('name')" in save_layout_src and "template.name = new_name" in save_layout_src


def test_p1_8_p1_7_p2_3_js_runtime_guards():
    """P1-8/P1-7/P2-3: Node VM tests for deleteCol, cellColspan, updateExistingTemplate, doPrint, and quick-select."""
    node = shutil.which("node")
    assert node, "Node is required"
    js_src = MATERIAL_JS.read_text(encoding="utf-8")
    qs_src = QUICK_SELECT_JS.read_text(encoding="utf-8")

    def take_fn(src: str, marker: str) -> str:
        start = src.index(marker)
        open_idx = src.index("{", start)
        depth, quote, esc = 0, None, False
        for i in range(open_idx, len(src)):
            ch = src[i]
            if quote:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return src[start : i + 1]
        raise AssertionError(marker)

    payload = {
        "reindex": take_fn(js_src, "function reindexLabelCells("),
        "applyColspan": take_fn(js_src, "function applyCellColspanChange("),
        "deleteCol": take_fn(js_src, "function deleteCol("),
        "updateExisting": take_fn(js_src, "function updateExistingTemplate("),
        "doPrint": take_fn(js_src, "function doPrint("),
        "sampleBlock": js_src[js_src.index("var labelSampleData = {") : js_src.index("var previewUseSample")],
        "qsRender": take_fn(qs_src, "function renderMaterialItem("),
        "qsEsc": take_fn(qs_src, "function esc("),
        "qsHighlight": take_fn(qs_src, "function highlight("),
    }

    program = r"""
const vm = require('node:vm'), assert = require('node:assert/strict');
const p = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

function makeTable(rowSpecs) {
  const table = { rows: [] };
  function makeCell(row, colSpan = 1, text = '') {
    const cell = {
      colSpan, dataset: {}, style: {}, className: 'label-cell',
      classList: { contains: c => c === 'label-cell' },
      parentElement: row,
      text,
      get cellIndex() { return row.cells.indexOf(cell); },
      get nextElementSibling() {
        const idx = row.cells.indexOf(cell);
        return idx >= 0 && idx + 1 < row.cells.length ? row.cells[idx + 1] : null;
      },
    };
    return cell;
  }
  rowSpecs.forEach(spec => {
    const row = {
      cells: [],
      deleteCell(i) { this.cells.splice(i, 1); },
      removeChild(node) { const i = this.cells.indexOf(node); if (i >= 0) this.cells.splice(i, 1); },
      insertCell(i) {
        const c = makeCell(this, 1, '');
        if (i < 0 || i >= this.cells.length) this.cells.push(c);
        else this.cells.splice(i, 0, c);
        return c;
      },
    };
    spec.forEach(s => row.cells.push(makeCell(row, s.colSpan || 1, s.text || '')));
    table.rows.push(row);
  });
  return table;
}

// 1) deleteCol: row0 has 1 merged cell (colSpan=2), row1 has 2 cells, select row1 col1 (cellIndex=1)
(function testDeleteCol() {
  const table = makeTable([
    [{ colSpan: 2, text: 'HEADER' }],
    [{ colSpan: 1, text: 'A' }, { colSpan: 1, text: 'B' }],
  ]);
  const props = { style: {} }, noSel = { style: {} };
  const ctx = {
    document: { getElementById: id => id === 'labelTable' ? table : id === 'cellProperties' ? props : id === 'noSelection' ? noSel : null },
    currentTemplate: { rows: 2, cols: 2 },
    selectedCell: table.rows[1].cells[1],
    selectedCells: [table.rows[1].cells[1]],
    __notify() {},
    saveTemplateToStorage() {},
    Math,
  };
  vm.createContext(ctx);
  vm.runInContext(p.reindex + '\n' + p.deleteCol, ctx);
  ctx.deleteCol();
  assert.equal(table.rows[0].cells.length, 1, 'merged cell in row0 must NOT be deleted when shrinking from colSpan 2 to 1');
  assert.equal(table.rows[0].cells[0].colSpan, 1, 'merged cell colSpan must shrink to 1');
  assert.equal(table.rows[1].cells.length, 1, 'selected column in row1 must be deleted');
  assert.equal(table.rows[1].cells[0].text, 'A');
  assert.equal(ctx.currentTemplate.cols, 1);
})();

// 2) applyCellColspanChange: expand 1->2 absorbs sibling; shrink 2->1 inserts sibling
(function testCellColspan() {
  const table = makeTable([[{ colSpan: 1, text: 'L' }, { colSpan: 1, text: 'R' }]]);
  const ctx = {
    document: { getElementById: id => id === 'labelTable' ? table : null },
    initTemplateDragDrop() {},
    Math, parseInt,
  };
  vm.createContext(ctx);
  vm.runInContext(p.reindex + '\n' + p.applyColspan, ctx);
  const first = table.rows[0].cells[0];
  const applied = ctx.applyCellColspanChange(first, 2);
  assert.equal(applied, 2);
  assert.equal(table.rows[0].cells.length, 1, 'expanding to colSpan=2 must absorb right sibling');
  assert.equal(first.colSpan, 2);
  const shrunk = ctx.applyCellColspanChange(first, 1);
  assert.equal(shrunk, 1);
  assert.equal(table.rows[0].cells.length, 2, 'shrinking to colSpan=1 must restore sibling cell');
  assert.equal(first.colSpan, 1);
})();

// 3) updateExistingTemplate sends renamed template name + labelSampleData includes brand + doPrint guards blocked popup
(async function testSaveRenameAndPrintGuard() {
  const posts = [], notices = [];
  const ctx = {
    currentTemplateId: 42,
    currentTemplate: { labelWidth: 90, labelHeight: 50, cols: 2, rows: 3 },
    document: { getElementById: id => id === 'templateNameInput' ? { value: '  新标签名  ' } : null },
    __runLabelTemplateWrite: fn => Promise.resolve().then(fn),
    __collectTemplateData: () => ({ cells: [] }),
    __requireTemplateSuccess: r => r,
    __buildLabelModel: () => ({ rows: 1, cols: 1, labelWidth: 60, labelHeight: 40, cells: [], rowHeights: [30] }),
    __notify: (m, t) => notices.push({ m, t }),
    loadTemplateList: () => Promise.resolve(),
    localStorage: { removeItem() {} },
    window: { open: () => null },
    WMS: { api: { postRaw: (url, body) => { posts.push({ url, body }); return Promise.resolve({ status: 'success' }); } } },
  };
  vm.createContext(ctx);
  vm.runInContext(p.sampleBlock + '\n' + p.updateExisting + '\n' + p.doPrint, ctx);
  assert(ctx.labelSampleData.brand, 'labelSampleData must include brand');
  await ctx.updateExistingTemplate();
  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, '/label_template/42/save_layout');
  assert.equal(posts[0].body.name, '新标签名', 'updateExistingTemplate must submit template name');
  ctx.doPrint();
  assert(notices.some(n => n.m.includes('拦截')), 'doPrint must warn when window.open returns null');
})();

// 4) quick-select renderMaterialItem displays storage_location and inactive badge
(function testQuickSelectRender() {
  const ctx = { String, RegExp };
  vm.createContext(ctx);
  vm.runInContext(p.qsEsc + '\n' + p.qsHighlight + '\n' + p.qsRender, ctx);
  const html = ctx.renderMaterialItem(
    { code: 'M01', name: '轴承', spec: '6204', brand: 'SKF', storage_location: 'A-02-03', status: 'inactive' },
    0,
    'A-02'
  );
  assert(html.includes('库位 '), 'must render storage_location');
  assert(html.includes('A-02'), 'must highlight storage_location');
  assert(html.includes('停用'), 'must badge inactive material');
})();
"""
    proc = subprocess.run(
        [node, "-e", program],
        input=json.dumps(payload),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# =============================================================================
# Part B: Full isolated Flask + SQLite integration tests (Linux CI)
# =============================================================================

@pytest.fixture
def isolated_roles_app(monkeypatch):
    import app as wms
    from werkzeug.security import generate_password_hash

    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "WTF_CSRF_ENABLED", False)
    with wms.app.app_context():
        assert str(wms.db.engine.url) == "sqlite:///:memory:"
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        users = {}
        for role in ("admin", "warehouse", "finance", "production", "viewer"):
            u = wms.User(
                username=f"b3_{role}",
                password_hash=generate_password_hash("admin"),
                role=role,
                must_change_password=False,
            )
            wms.db.session.add(u)
            wms.db.session.flush()
            users[role] = u.id
        wms.db.session.commit()

    def client_as(role: str):
        c = wms.app.test_client()
        with c.session_transaction() as sess:
            sess["_user_id"] = str(users[role])
            sess["_fresh"] = True
        return c

    yield wms, client_as
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


def test_p1_6_image_candidates_role_and_rate_limit_http(isolated_roles_app, monkeypatch):
    """P1-6: Online image search requires warehouse/admin role and enforces per-user 429 rate limit."""
    import rate_limit

    wms, client_as = isolated_roles_app
    with wms.app.app_context():
        mat = wms.Material(code="IMG-RL-1", name="找图限流料", stock=0)
        wms.db.session.add(mat)
        wms.db.session.commit()
        mid = mat.id

    monkeypatch.setattr(wms, "_search_material_images_online", lambda m: ([], m.code))
    rate_limit.reset()
    try:
        headers = {"X-Requested-With": "XMLHttpRequest"}
        assert client_as("viewer").get(f"/material/{mid}/image_candidates", headers=headers).status_code == 403
        assert client_as("production").get(f"/material/{mid}/image_candidates", headers=headers).status_code == 403

        wh_client = client_as("warehouse")
        for _ in range(20):
            r = wh_client.get(f"/material/{mid}/image_candidates", headers=headers)
            assert r.status_code == 200
        r_over = wh_client.get(f"/material/{mid}/image_candidates", headers=headers)
        assert r_over.status_code == 429
        assert "频繁" in r_over.get_json()["msg"]
    finally:
        rate_limit.reset()


def test_p1_6_export_material_role_and_price_dimension_http(isolated_roles_app):
    """P1-6: /material/export allows warehouse/finance, denies viewer/production, and obeys price_dimension_enabled."""
    from openpyxl import load_workbook

    wms, client_as = isolated_roles_app
    with wms.app.app_context():
        wms.db.session.add(wms.Material(code="EXP-P1", name="价格导出测试料", stock=5, price=99.5))
        wms.set_system_setting("price_dimension_enabled", "0")
        wms.db.session.commit()

    assert client_as("viewer").get("/material/export", headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 403
    assert client_as("production").get("/material/export", headers={"X-Requested-With": "XMLHttpRequest"}).status_code == 403

    for role in ("warehouse", "finance"):
        r_off = client_as(role).get("/material/export")
        assert r_off.status_code == 200
        headers_off = [c.value for c in load_workbook(io.BytesIO(r_off.data)).active[1]]
        assert "单价" not in headers_off

    with wms.app.app_context():
        wms.set_system_setting("price_dimension_enabled", "1")
        wms.db.session.commit()
    r_on = client_as("warehouse").get("/material/export")
    assert r_on.status_code == 200
    ws_on = load_workbook(io.BytesIO(r_on.data)).active
    headers_on = [c.value for c in ws_on[1]]
    assert "单价" in headers_on
    assert ws_on.cell(2, headers_on.index("单价") + 1).value == 99.5


def test_p1_6_mobile_material_detail_price_visibility_http(isolated_roles_app):
    """P1-6: /mobile/material obeys price_dimension_enabled."""
    wms, client_as = isolated_roles_app
    with wms.app.app_context():
        wms.db.session.add(wms.Material(code="MOB-P1", name="手机价格测试料", stock=0, price=77.25))
        wms.set_system_setting("price_dimension_enabled", "0")
        wms.db.session.commit()

    wh = client_as("warehouse")
    r_off = wh.get("/mobile/material", query_string={"code": "MOB-P1"})
    assert r_off.status_code == 200
    assert "77.25" not in r_off.text

    with wms.app.app_context():
        wms.set_system_setting("price_dimension_enabled", "1")
        wms.db.session.commit()
    r_on = wh.get("/mobile/material", query_string={"code": "MOB-P1"})
    assert r_on.status_code == 200
    assert "77.25" in r_on.text


def test_p1_7_options_material_all_includes_inactive_and_location_http(isolated_roles_app):
    """P1-7: /api/options/material_all returns inactive materials & storage_location, while /api/options/material excludes inactive."""
    from routes.options_api import invalidate_options_pool

    wms, client_as = isolated_roles_app
    invalidate_options_pool()
    with wms.app.app_context():
        wms.db.session.add_all([
            wms.Material(code="OPT-ACT", name="启用联香料", storage_location="L-01", status="active"),
            wms.Material(code="OPT-INACT", name="停用联香料", storage_location="L-02", status="inactive"),
        ])
        wms.db.session.commit()
    invalidate_options_pool()

    wh = client_as("warehouse")
    r_active = wh.get("/api/options/material?kw=OPT-")
    assert r_active.status_code == 200
    codes_active = {item["code"] for item in r_active.get_json()["data"]}
    assert codes_active == {"OPT-ACT"}

    r_all = wh.get("/api/options/material_all?kw=OPT-")
    assert r_all.status_code == 200
    by_code = {item["code"]: item for item in r_all.get_json()["data"]}
    assert set(by_code) == {"OPT-ACT", "OPT-INACT"}
    assert by_code["OPT-INACT"]["status"] == "inactive"
    assert by_code["OPT-INACT"]["storage_location"] == "L-02"


def test_p1_8_save_label_template_layout_updates_name_and_checks_conflict_http(isolated_roles_app):
    """P1-8: /label_template/<id>/save_layout persists renamed template name and rejects conflicts."""
    wms, client_as = isolated_roles_app
    with wms.app.app_context():
        t1 = wms.LabelTemplate(name="模板甲", width=90, height=50, cols=2, rows=3, layout="{}")
        t2 = wms.LabelTemplate(name="模板乙", width=90, height=50, cols=2, rows=3, layout="{}")
        wms.db.session.add_all([t1, t2])
        wms.db.session.commit()
        id1 = t1.id

    wh = client_as("warehouse")
    r_dup = wh.post(f"/label_template/{id1}/save_layout", json={"layout": {"cells": []}, "name": "模板乙"})
    assert r_dup.status_code == 409

    r_ok = wh.post(f"/label_template/{id1}/save_layout", json={"layout": {"cells": []}, "name": "模板甲-改名"})
    assert r_ok.status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.LabelTemplate, id1).name == "模板甲-改名"


def test_p2_3_both_material_template_endpoints_identical_http(isolated_roles_app):
    """P2-3: /material/download_template, /export/template/material, and build_material_import_template_stream stay identical."""
    from openpyxl import load_workbook
    from routes.material import build_material_import_template_stream

    wms, client_as = isolated_roles_app
    wh = client_as("warehouse")
    for flag, expect_alert_cols in (("0", False), ("1", True)):
        with wms.app.app_context():
            wms.set_system_setting("inventory_alert_enabled", flag)
            wms.db.session.commit()
            direct_rows = list(load_workbook(build_material_import_template_stream()).active.iter_rows(values_only=True))
        r1 = wh.get("/material/download_template")
        r2 = wh.get("/export/template/material")
        assert r1.status_code == 200 and r2.status_code == 200
        rows1 = list(load_workbook(io.BytesIO(r1.data)).active.iter_rows(values_only=True))
        rows2 = list(load_workbook(io.BytesIO(r2.data)).active.iter_rows(values_only=True))
        assert rows1 == rows2 == direct_rows
        assert ("安全库存" in rows1[0]) is expect_alert_cols
