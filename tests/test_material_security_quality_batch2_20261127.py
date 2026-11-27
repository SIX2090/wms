# -*- coding: utf-8 -*-
"""BUG-2026-11-27-002 回归测试：物料管理第二批安全、表单、导入导出、合并与图片缺陷修复。

覆盖：
- P0-1 + R6：物料及全部基础资料（分类/客户/部门/员工/单位/供应商/仓库/合同）Excel 导出公式注入中和
- P1-1：add_material 先验原始长度再净化、purpose/remark 写入净化值、校验/提交失败清理孤儿图
- P1-2：edit_material 全字段净化与写锁统一回滚、MAX_MATERIAL_IMAGES=5 上限与单事务入库、孤儿图清理、前端防重复提交与防重复传图
- P1-3：import_material 友好拦截旧版 .xls、min_stock/safety_stock 有限边界校验、自动建档净化与列宽预检、导入写审计
- P1-4：fix_empty_fields 写审计、前端防重复提交
- P1-5：merge_material_duplicates 同步主图与冗余字段（BOM.product_code/PurchaseRequestItem）、前端合并按钮与 admin 权限对齐
- P1-10：找图 onerror 防死循环、编辑图库属性转义、手机详情主图去重
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
MATERIAL_ROUTE = ROOT / "app" / "routes" / "material.py"
MATERIAL_JS = ROOT / "app" / "static" / "js" / "pages" / "material-list.js"
MERGE_JS = ROOT / "app" / "static" / "js" / "material_merge.js"
API_JS = ROOT / "app" / "static" / "js" / "api.js"
APP_PY = ROOT / "app" / "app.py"
MOBILE_DETAIL_HTML = ROOT / "app" / "templates" / "mobile_material_detail.html"


# =============================================================================
# Part A: Pure static / AST / Jinja / Node-VM tests (no DB or app import)
# =============================================================================

def _extract_func_source(path: Path, func_name: str) -> str:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            lines = src.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"Function {func_name} not found in {path}")


def test_master_exports_sanitize_excel_cells_ast():
    """P0-1 + R6: All 9 master-data export routes must sanitize cells via _sanitize_excel_cell."""
    targets = [
        (ROOT / "app/routes/material.py", "export_material"),
        (ROOT / "app/routes/category.py", "export_category"),
        (ROOT / "app/routes/customer.py", "export_customer"),
        (ROOT / "app/routes/department.py", "export_department"),
        (ROOT / "app/routes/employee.py", "export_employee"),
        (ROOT / "app/routes/unit_supplier_import.py", "export_unit"),
        (ROOT / "app/routes/unit_supplier_import.py", "export_supplier"),
        (ROOT / "app/routes/warehouse.py", "export_warehouse"),
        (ROOT / "app/routes/contract.py", "export_contract"),
    ]
    for file_path, fn_name in targets:
        body = _extract_func_source(file_path, fn_name)
        assert "_sanitize_excel_cell" in body, f"{file_path.name}:{fn_name} missing _sanitize_excel_cell"
        assert re.search(r"ws\.append\(\[_sanitize_excel_cell\(", body), (
            f"{file_path.name}:{fn_name} must sanitize every cell passed to ws.append"
        )


def test_add_and_edit_material_validate_lengths_and_sanitize_ast():
    """P1-1 & P1-2: raw-length validation before sanitization, sanitized persistence, single commit & orphan cleanup."""
    add_src = _extract_func_source(MATERIAL_ROUTE, "add_material")
    assert "raw_purpose = " in add_src and "raw_remark = " in add_src
    assert "len(raw_name) > 100" in add_src
    assert "len(raw_purpose) > 200" in add_src
    assert "len(raw_remark) > 500" in add_src
    assert "purpose=purpose or None" in add_src
    assert "remark=remark or None" in add_src
    assert "purpose=request.form.get('purpose')" not in add_src
    assert "_cleanup_upload_file(image_path)" in add_src
    assert add_src.index("_parse_optional_fk") < add_src.index("save_upload_image(")

    edit_src = _extract_func_source(MATERIAL_ROUTE, "edit_material")
    assert "def _reject(" in edit_src and "db.session.rollback()" in edit_src
    assert "MAX_MATERIAL_IMAGES" in edit_src
    assert "new_remark = sanitize_text_input(raw_remark" in edit_src
    assert "material.remark = new_remark or None" in edit_src
    assert edit_src.index("_resolve_alert_thresholds") < edit_src.index("save_upload_image(")
    assert edit_src.index("MaterialImage(material_id=id, image=new_image_path") < edit_src.index("db.session.commit()")
    assert edit_src.count("db.session.commit()") == 1


def test_import_and_fix_empty_fields_audit_and_bounds_ast():
    """P1-3 & P1-4: xls guard, stock threshold bounds, auto-create length check, and audit logs."""
    imp_src = _extract_func_source(MATERIAL_ROUTE, "import_material")
    assert "BadZipFile" in imp_src and "InvalidFileException" in imp_src
    assert "MAX_REASONABLE_STOCK" in imp_src
    assert "len(raw_unit_name) > 20" in imp_src
    assert "len(raw_cat_name) > 50" in imp_src
    assert "len(raw_sup_name) > 50" in imp_src
    assert "log_audit(" in imp_src and "'import_material'" in imp_src
    assert "log_operation(" in imp_src

    fix_src = _extract_func_source(MATERIAL_ROUTE, "fix_empty_fields")
    assert "log_audit(" in fix_src and "'fix_empty_fields'" in fix_src
    assert "log_operation(" in fix_src


def test_merge_material_syncs_primary_image_and_redundant_fields_ast():
    """P1-5: merge_material_duplicates syncs primary image, BOM.product_code and PurchaseRequestItem fields."""
    preview_src = _extract_func_source(APP_PY, "material_merge_preview")
    assert "tables['bom']" in preview_src
    merge_src = _extract_func_source(APP_PY, "merge_material_duplicates")
    assert "from utils import sync_material_primary_image" in merge_src
    assert "sync_material_primary_image(target)" in merge_src
    assert "name == 'purchase_request_item'" in merge_src
    assert "update_values['material_code'] = target.code" in merge_src
    assert "bom_tbl.c.product_code == source.code" in merge_src
    assert "bom: 'BOM清单'" in MERGE_JS.read_text(encoding="utf-8")


def test_mobile_material_detail_deduplicates_primary_image_jinja():
    """P1-10: mobile_material_detail.html must never render the primary image twice."""
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
    base_ctx = dict(
        warehouses=[],
        warehouse=None,
        stock=0,
        request=NS(args={}, path="/mobile/material", endpoint="mobile_material_detail"),
        current_user=NS(is_authenticated=True, role="warehouse", username="u"),
        config={},
        url_for=lambda ep, **kw: f"/static/{kw['filename']}" if ep == "static" else f"/{ep}",
        get_flashed_messages=lambda **kw: [],
    )
    mat = NS(
        code="M-IMG", name="图片测试物料", brand="B", spec="S", storage_location="",
        unit=NS(name="个"), category=NS(name="类"), supplier=NS(name="供"),
        purpose="", price=1, min_stock=0, max_stock=0, reorder_point=0,
        expiry_date=None, alert_days=30, status="active", remark="", created_at="2026-11-27",
        image="uploads/material_images/primary.jpg",
    )
    imgs = [NS(image="uploads/material_images/primary.jpg"), NS(image="uploads/material_images/second.jpg")]
    rendered = tpl.render(material=mat, images=imgs, **base_ctx)
    assert rendered.count("uploads/material_images/primary.jpg") == 1
    assert rendered.count("uploads/material_images/second.jpg") == 1

    # Also test /static/ prefix normalization
    mat_prefixed = NS(**{**mat.__dict__, "image": "/static/uploads/material_images/primary.jpg"})
    rendered2 = tpl.render(material=mat_prefixed, images=imgs, **base_ctx)
    assert rendered2.count("uploads/material_images/primary.jpg") == 1
    assert rendered2.count("uploads/material_images/second.jpg") == 1


def test_material_list_js_batch2_runtime_guards():
    """P1-2/P1-4/P1-5/P1-10: Node VM runtime checks on real material-list.js."""
    node = shutil.which("node")
    assert node, "Node is required"
    js_src = MATERIAL_JS.read_text(encoding="utf-8")
    api_src = API_JS.read_text(encoding="utf-8")

    # Slice 1: toolbar + merge guards
    s_toolbar = js_src.index("var materialDeleteBusy = false;")
    e_toolbar = js_src.index("// ==================== 批量修改物料", s_toolbar)
    toolbar_slice = js_src[s_toolbar:e_toolbar]

    # Slice 2: loadEditMaterialImages + uploadEditMaterialImage
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

    load_img_fn = take_fn(js_src, "window.loadEditMaterialImages = function(id)")
    upload_img_fn = take_fn(js_src, "window.uploadEditMaterialImage = function(input)")
    find_img_slice = js_src[
        js_src.index("    var materialImageRequestGeneration = 0;") : js_src.index("    // 删除全部物料入口")
    ]
    edit_submit_fn = take_fn(
        js_src[js_src.index("var editForm = document.getElementById('editForm');") :],
        "function(e)",
    )

    program = r"""
const vm = require('node:vm'), assert = require('node:assert/strict');
const p = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));

async function flush() { for (let i = 0; i < 20; i++) await Promise.resolve(); }

// 1) Merge button & handler enforce canDelete (admin-only)
(function testMergeRoleGuard() {
  const nodes = new Map();
  for (const id of ['toolbarEditBtn','toolbarBatchEditBtn','toolbarCopyBtn','toolbarPrintBtn','toolbarRemotePrintBtn','toolbarFindImageBtn','toolbarDeleteBtn','toolbarMergeBtn','materialSelectionBar','materialSelectionCount']) {
    nodes.set(id, { id, disabled: false, hidden: false, textContent: '', dataset: {} });
  }
  const checked = [{ value: '1', closest() { return { querySelector() { return { textContent: 'M001' }; } }; } }];
  let opened = 0; const toasts = [];
  const ctx = {
    materialPageData: { canDelete: false, urls: {} },
    document: { getElementById: id => nodes.get(id), querySelectorAll: () => checked },
    WMS: { MaterialMerge: { open() { opened++; } } },
    showToast(msg, type) { toasts.push({ msg, type }); },
    Array, Number, String,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(p.toolbar, ctx);
  ctx.updateToolbarButtons();
  assert.equal(nodes.get('toolbarMergeBtn').disabled, true, 'non-admin must disable toolbarMergeBtn');
  ctx.toolbarMerge();
  ctx.mergeMaterialInto(1, 'M001');
  assert.equal(opened, 0, 'non-admin must not open merge modal');
  assert.equal(toasts.length, 2);

  ctx.materialPageData.canDelete = true;
  ctx.updateToolbarButtons();
  assert.equal(nodes.get('toolbarMergeBtn').disabled, false, 'admin with 1 selected enables toolbarMergeBtn');
  ctx.toolbarMerge();
  assert.equal(opened, 1);
})();

// 2) loadEditMaterialImages escapes malicious URL/ID attributes
(async function testEditGalleryEscaping() {
  const grid = { isConnected: true, innerHTML: '', textContent: '' };
  const ctx = {
    document: { getElementById: id => id === 'editMaterialImageGrid' ? grid : null },
    getEditMaterialContext: () => ({ isCurrent: () => true }),
    WMS: { api: { getRaw: () => Promise.resolve({
      status: 'success',
      data: { images: [{ id: '1" onclick="evil()', url: '/a.jpg" onerror="evil()' }] },
    }) } },
    Array, String, Error,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(p.loadImg + ';', ctx);
  await ctx.loadEditMaterialImages(7);
  await flush();
  assert(grid.innerHTML.includes('&quot;'), 'quotes must be escaped');
  assert(!grid.innerHTML.includes('" onerror="'), 'raw event attribute injection must be neutralized');
  assert(!grid.innerHTML.includes('" onclick="'), 'raw button attribute injection must be neutralized');
})();

// 3) findMaterialImage onerror breaks loop + fixEmptyFields single-flight guard
(async function testImageOnerrorAndFixBusy() {
  const createdImgs = [];
  const makeEl = (tag) => {
    const el = {
      tagName: tag, className: '', textContent: '', innerHTML: '', value: '1',
      isConnected: true, dataset: {}, children: [],
      appendChild(c) { this.children.push(c); if (c.tagName === 'img') createdImgs.push(c); },
      addEventListener() {},
    };
    return el;
  };
  const nodes = {
    materialImageModal: makeEl('div'),
    materialImageStatus: makeEl('div'),
    materialImageGrid: makeEl('div'),
    materialImageQuery: makeEl('div'),
    repairCategory: makeEl('select'),
    repairUnit: makeEl('select'),
  };
  const postCalls = [];
  let resolveFix;
  const ctx = {
    materialPageData: { urls: { fix: '/material/fix_empty_fields' } },
    document: { getElementById: id => nodes[id] || null, createElement: tag => makeEl(tag) },
    bootstrap: { Modal: class { show() {} hide() {} static getInstance() { return new this(); } } },
    showToast() {}, location: { reload() {} }, setTimeout() {},
    WMS: {
      api: {
        getRaw: () => Promise.resolve({
          status: 'success', query: 'M1',
          candidates: [{ thumb_url: 'https://x.test/t.jpg', image_url: 'https://x.test/full.jpg', title: 't' }],
        }),
        postRaw: (url, body) => {
          postCalls.push({ url, body });
          return new Promise(r => { resolveFix = r; });
        },
      },
    },
    String, Promise,
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(p.findImg, ctx);
  ctx.findMaterialImage(1);
  await flush();
  assert.equal(createdImgs.length, 1);
  const img = createdImgs[0];
  assert.equal(img.src, 'https://x.test/t.jpg');
  assert.equal(typeof img.onerror, 'function');
  img.onerror();
  assert.equal(img.src, 'https://x.test/full.jpg');
  assert.equal(img.onerror, null, 'onerror must be cleared after fallback to prevent infinite reload loop');

  // fixEmptyFields double-click sends only 1 request while in flight
  ctx.fixEmptyFields();
  ctx.fixEmptyFields();
  assert.equal(postCalls.length, 1, 'concurrent fixEmptyFields clicks must not double-POST');
  resolveFix({ status: 'error', msg: 'failed' });
  await flush();
  ctx.fixEmptyFields();
  assert.equal(postCalls.length, 2, 'must unlock after completion for retry');
})();

// 4) editForm drops image from FormData, blocks while uploading, and blocks double submit
(async function testEditFormGuards() {
  const posts = []; let resolvePost;
  const toasts = [];
  const imgInput = { id: 'edit_image_upload', _uploading: true, value: '', files: [{ name: 'a.png' }] };
  const submitBtn = { disabled: false };
  const form = { _submitting: false, querySelector: () => submitBtn };
  const nodes = {
    edit_id: { value: '9' },
    edit_code: { value: 'M9', getAttribute: () => 'M9' },
    edit_name: { value: 'N9', getAttribute: () => 'N9' },
    edit_image_upload: imgInput,
    editModal: {},
  };
  class FakeFD {
    constructor() { this.keys = new Set(['code', 'name', 'image']); }
    delete(k) { this.keys.delete(k); }
    has(k) { return this.keys.has(k); }
  }
  const ctx = {
    document: { getElementById: id => nodes[id] || null },
    FormData: FakeFD,
    isWmsMasterEditPending: () => false,
    commitQuickSelects: () => true,
    showToast: (m, t) => toasts.push({ m, t }),
    bootstrap: { Modal: { getInstance: () => null } },
    setTimeout() {}, location: { reload() {} },
    WMS: { api: { postRaw: (url, fd) => { posts.push({ url, hasImage: fd.has('image') }); return new Promise(r => { resolvePost = r; }); } } },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext('var submitEdit = ' + p.editSubmit + ';', ctx);

  // While image is uploading -> blocked with toast
  ctx.submitEdit.call(form, { preventDefault() {} });
  assert.equal(posts.length, 0);
  assert(toasts.some(t => t.m.includes('图片正在上传')));

  // Upload finished -> submits once, strips image field, blocks duplicate click
  imgInput._uploading = false;
  ctx.submitEdit.call(form, { preventDefault() {} });
  ctx.submitEdit.call(form, { preventDefault() {} });
  assert.equal(posts.length, 1, 'double submit must be blocked');
  assert.equal(posts[0].hasImage, false, 'editForm must delete image from FormData to prevent duplicate upload');
  assert.equal(submitBtn.disabled, true);
  resolvePost({ status: 'error', msg: 'err' });
  await flush();
  assert.equal(form._submitting, false, 'failure must restore submit state');
  assert.equal(submitBtn.disabled, false);
})();
"""
    payload = {
        "toolbar": toolbar_slice,
        "loadImg": load_img_fn,
        "uploadImg": upload_img_fn,
        "findImg": find_img_slice,
        "editSubmit": edit_submit_fn,
        "api": api_src,
    }
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
# Part B: Full isolated Flask + SQLite runtime integration tests (Linux CI)
# =============================================================================

@pytest.fixture
def isolated_admin_client(monkeypatch, tmp_path):
    import app as wms
    from werkzeug.security import generate_password_hash

    monkeypatch.setitem(wms.app.config, "TESTING", True)
    monkeypatch.setitem(wms.app.config, "WTF_CSRF_ENABLED", False)
    monkeypatch.setattr(wms.app, "static_folder", str(tmp_path / "static"))
    with wms.app.app_context():
        assert str(wms.db.engine.url) == "sqlite:///:memory:"
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        admin = wms.User(
            username="batch2_admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        )
        wms.db.session.add(admin)
        wms.db.session.commit()
        admin_id = admin.id
    client = wms.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_id)
        sess["_fresh"] = True
    yield wms, client, tmp_path / "static"
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


def _make_png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (24, 24), "navy").save(buf, format="PNG")
    return buf.getvalue()


def test_excel_formula_injection_neutralized_across_all_master_exports(isolated_admin_client):
    """P0-1 + R6: Every master-data export neutralizes formula-leading strings."""
    from openpyxl import load_workbook

    wms, client, _ = isolated_admin_client
    with wms.app.app_context():
        cat = wms.MaterialCategory(code="=CAT1", name="+分类名称")
        unit = wms.Unit(code="@U1", name="-单位")
        sup = wms.Supplier(code="=SUP1", name="+供应商", contact="@张三", address="-地址")
        cust = wms.Customer(code="=CUS1", name="+客户", contact="@李四", address="-路")
        dept = wms.Department(code="=DEP1", name="+部门", remark="@备注")
        wh = wms.Warehouse(code="=WH1", name="+仓库", type="-原料", location="@一楼", remark="=说明")
        con = wms.Contract(contract_no="=CON1", project_name="+工程", remark="@备注")
        wms.db.session.add_all([cat, unit, sup, cust, dept, wh, con])
        wms.db.session.flush()
        emp = wms.Employee(code="=EMP1", name="+员工", position="@工长", department_id=dept.id)
        mat = wms.Material(
            code="=MAT1",
            name='=CMD|" /C calc"!A0',
            brand="+品牌",
            spec="-规格",
            storage_location="@A-01",
            unit_id=unit.id,
            category_id=cat.id,
            supplier_id=sup.id,
            stock=12,
            price=3.5,
        )
        wms.db.session.add_all([emp, mat])
        wms.db.session.commit()

    endpoints = [
        "/material/export",
        "/category/export",
        "/customer/export",
        "/department/export",
        "/employee/export",
        "/unit/export",
        "/supplier/export",
        "/warehouse/export",
        "/contract/export",
    ]
    for ep in endpoints:
        resp = client.get(ep)
        assert resp.status_code == 200, ep
        ws = load_workbook(io.BytesIO(resp.data)).active
        assert ws.max_row >= 2, ep
        data_cells = [cell for row in ws.iter_rows(min_row=2) for cell in row]
        assert all(cell.data_type != "f" for cell in data_cells), f"Formula cell leaked in {ep}"
        row_vals = [cell.value for cell in ws[2]]
        assert any(isinstance(v, str) and v.startswith("'") for v in row_vals), (
            f"Expected apostrophe-neutralized payload in {ep}, got {row_vals}"
        )


def test_add_material_sanitizes_purpose_remark_rejects_raw_overlong_and_cleans_orphan_image(isolated_admin_client):
    """P1-1: add_material validates raw lengths, saves sanitized purpose/remark, and cleans orphan image."""
    wms, client, static_dir = isolated_admin_client
    headers = {"X-Requested-With": "XMLHttpRequest"}

    # Raw overlong fields (> column width) must be rejected instead of silently truncated
    for field, limit in [("name", 100), ("spec", 100), ("brand", 100), ("purpose", 200), ("remark", 500)]:
        payload = {"code": f"OVER-{field}", "name": "正常物料", field: "X" * (limit + 5)}
        if field == "name":
            payload["name"] = "X" * (limit + 5)
        resp = client.post("/material/add", data=payload, headers=headers)
        assert resp.status_code == 400, (field, resp.get_json())

    # Invalid FK with an uploaded image must NOT leave an orphan file on disk
    bad_fk = client.post(
        "/material/add",
        data={
            "code": "ORPHAN-1",
            "name": "孤儿图测试",
            "category_id": "999999",
            "image": (io.BytesIO(_make_png_bytes()), "test.png"),
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    assert bad_fk.status_code == 400
    img_dir = static_dir / "uploads" / "material_images"
    assert not img_dir.exists() or list(img_dir.iterdir()) == []

    # Valid add strips XSS from purpose & remark before saving
    ok = client.post(
        "/material/add",
        data={
            "code": "CLEAN-1",
            "name": "净化测试物料",
            "purpose": "<script>alert(1)</script>电机控制",
            "remark": "<img src=x>重要备注",
        },
        headers=headers,
    )
    assert ok.status_code == 200 and ok.get_json()["status"] == "success"
    with wms.app.app_context():
        m = wms.Material.query.filter_by(code="CLEAN-1").one()
        assert "<script>" not in (m.purpose or "") and "电机控制" in (m.purpose or "")
        assert "<img" not in (m.remark or "") and "重要备注" in (m.remark or "")


def test_edit_material_sanitizes_enforces_image_cap_and_rolls_back_cleanly(isolated_admin_client):
    """P1-2: edit_material sanitizes text, rolls back on errors, enforces 5-image cap, and commits image atomically."""
    wms, client, static_dir = isolated_admin_client
    headers = {"X-Requested-With": "XMLHttpRequest"}
    with wms.app.app_context():
        wms.set_system_setting("inventory_alert_enabled", "1")
        mat = wms.Material(code="ED-1", name="原物料", spec="S1", brand="B1", stock=0, price=10)
        wms.db.session.add(mat)
        wms.db.session.commit()
        mid = mat.id

    def get_rev():
        r = client.get(f"/material/{mid}")
        assert r.status_code == 200
        return r.get_json()["material"]["edit_revision"]

    # Threshold error must rollback cleanly without persisting partial field mutations
    r_bad = client.post(
        f"/material/edit/{mid}",
        data={"edit_revision": get_rev(), "code": "ED-1", "name": "不应落库", "min_stock": "20", "reorder_point": "5"},
        headers=headers,
    )
    assert r_bad.status_code == 400
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, mid).name == "原物料"

    # Valid edit sanitizes XSS in name/spec/brand/purpose/remark and adds image in 1 transaction
    r_ok = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": get_rev(),
            "code": "ED-1",
            "name": "<b>新名称</b>",
            "spec": "<i>新规格</i>",
            "brand": "<script>品牌</script>",
            "purpose": "<u>新用途</u>",
            "remark": "<svg>新备注</svg>",
            "min_stock": "5",
            "reorder_point": "10",
            "price": "12.5",
            "image": (io.BytesIO(_make_png_bytes()), "photo1.png"),
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r_ok.status_code == 200, r_ok.get_json()
    with wms.app.app_context():
        mat = wms.db.session.get(wms.Material, mid)
        for val in (mat.name, mat.spec, mat.brand, mat.purpose, mat.remark):
            assert "<" not in (val or "") and ">" not in (val or "")
        imgs = wms.MaterialImage.query.filter_by(material_id=mid).all()
        assert len(imgs) == 1 and mat.image == imgs[0].image
        # Fill up to MAX_MATERIAL_IMAGES (5)
        for idx in range(1, 5):
            wms.db.session.add(wms.MaterialImage(material_id=mid, image=f"uploads/material_images/seed_{idx}.jpg", sort_order=idx))
        wms.db.session.commit()

    img_dir = static_dir / "uploads" / "material_images"
    before_files = set(img_dir.iterdir())
    # 6th image via edit_material must be rejected and leave zero new file on disk
    r_cap = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": get_rev(),
            "code": "ED-1",
            "name": "新名称",
            "min_stock": "5",
            "reorder_point": "10",
            "price": "12.5",
            "image": (io.BytesIO(_make_png_bytes()), "photo6.png"),
        },
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r_cap.status_code == 400 and "最多" in r_cap.get_json()["msg"]
    assert set(img_dir.iterdir()) == before_files


def test_import_material_rejects_xls_bad_thresholds_overlong_masters_and_writes_audit(isolated_admin_client):
    """P1-3: import_material rejects .xls cleanly, validates thresholds & auto-created master widths, writes audit."""
    from openpyxl import Workbook

    wms, client, _ = isolated_admin_client
    headers = {"X-Requested-With": "XMLHttpRequest"}

    # 1) Legacy binary .xls gets friendly message
    r_xls = client.post(
        "/material/import",
        data={"file": (io.BytesIO(bytes.fromhex("d0cf11e0a1b11ae1") + b"0" * 128), "legacy.xls")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r_xls.status_code == 400
    assert "另存" in r_xls.get_json()["msg"] and ".xlsx" in r_xls.get_json()["msg"]

    with wms.app.app_context():
        wms.set_system_setting("inventory_alert_enabled", "1")

    wb = Workbook()
    ws = wb.active
    ws.append(["物料编码", "物料名称", "单位", "分类", "供应商", "最低库存", "安全库存"])
    ws.append(["IMP-NEG", "负阈值料", "个", "正常类", "正常供", -5, 10])
    ws.append(["IMP-BIG", "超限阈值料", "个", "正常类", "正常供", 10, 9999999999])
    ws.append(["IMP-U", "超长单位料", "单" * 25, "不该落库类", "不该落库供", 0, 0])
    ws.append(["IMP-OK", "合法导入料", "<b>套</b>", "<i>电气</i>", "<u>华东供</u>", 5, 10])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    r_imp = client.post(
        "/material/import",
        data={"file": (buf, "materials_batch2.xlsx")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r_imp.status_code == 200, r_imp.get_json()
    body = r_imp.get_json()
    assert body["count"] == 1
    assert "最低库存" in body.get("warnings", "")
    assert "安全库存" in body.get("warnings", "")
    assert "单位名称不能超过20个字符" in body.get("warnings", "")

    with wms.app.app_context():
        assert wms.Material.query.filter_by(code="IMP-OK").first() is not None
        assert wms.MaterialCategory.query.filter_by(name="不该落库类").first() is None
        u = wms.Unit.query.filter_by(name="套").first()
        assert u is not None and "<" not in u.name
        audit = wms.OperationAudit.query.filter_by(action="import_material").first()
        assert audit is not None


def test_fix_empty_fields_writes_audit_on_success(isolated_admin_client):
    """P1-4: fix_empty_fields writes audit trail when repairing records."""
    wms, client, _ = isolated_admin_client
    with wms.app.app_context():
        wms.db.session.add_all([
            wms.Unit(code="U1", name="个"),
            wms.MaterialCategory(code="C1", name="默认分类"),
            wms.Material(code="FIX-1", name="空字段物料", unit_id=None, category_id=None, stock=0),
        ])
        wms.db.session.commit()
    r = client.post("/material/fix_empty_fields", json={})
    assert r.status_code == 200 and "已修复 1 条" in r.get_json()["msg"]
    with wms.app.app_context():
        assert wms.OperationAudit.query.filter_by(action="fix_empty_fields").count() == 1


def test_merge_material_syncs_primary_image_bom_and_pr_redundant_fields(isolated_admin_client):
    """P1-5: merge_material_duplicates syncs primary image, BOM.product_code, and PR item redundant fields."""
    wms, client, _ = isolated_admin_client
    with wms.app.app_context():
        t = wms.Material(code="M-KEEP", name="保留物料", spec="S1", brand="B1", stock=5, image=None)
        s = wms.Material(code="M-OLD", name="保留物料", spec="S1", brand="B1", stock=3, image="uploads/material_images/src.jpg")
        wms.db.session.add_all([t, s])
        wms.db.session.flush()
        wms.db.session.add_all([
            wms.StockTransaction(material_id=t.id, transaction_type="in", quantity=5),
            wms.StockTransaction(material_id=s.id, transaction_type="in", quantity=3),
            wms.MaterialImage(material_id=s.id, image="uploads/material_images/src.jpg", sort_order=0),
            wms.BOM(bom_no="BOM-MERGE-1", product_code="M-OLD", product_name="旧名"),
        ])
        pr = wms.PurchaseRequest(request_no="PR-MERGE-1", applicant="u", status="pending")
        wms.db.session.add(pr)
        wms.db.session.flush()
        wms.db.session.add(wms.PurchaseRequestItem(
            purchase_request_id=pr.id, material_id=s.id,
            material_code="M-OLD", material_name="旧名", spec="OLD-S", quantity=2,
        ))
        wms.db.session.commit()
        tid, sid = t.id, s.id

        preview = wms.material_merge_preview(tid, sid)
        assert preview["tables"].get("bom") == 1

        stats = wms.merge_material_duplicates(tid, sid, keep_alias=True)
        wms.db.session.commit()
        assert stats["ledger_ok"] is True
        assert stats["tables"].get("bom") == 1

        kept = wms.db.session.get(wms.Material, tid)
        assert kept.image == "uploads/material_images/src.jpg"
        assert wms.MaterialImage.query.filter_by(material_id=tid).count() == 1
        bom = wms.BOM.query.filter_by(bom_no="BOM-MERGE-1").one()
        assert bom.product_code == "M-KEEP" and bom.product_name == "保留物料"
        pr_item = wms.PurchaseRequestItem.query.filter_by(purchase_request_id=pr.id).one()
        assert pr_item.material_id == tid
        assert pr_item.material_code == "M-KEEP"
        assert pr_item.material_name == "保留物料"
        assert pr_item.spec == "S1"


def test_mobile_material_detail_http_renders_primary_image_once(isolated_admin_client):
    """P1-10: HTTP /mobile/material renders primary image once even when mirrored in material_image."""
    wms, client, _ = isolated_admin_client
    with wms.app.app_context():
        mat = wms.Material(code="MOB-IMG-1", name="手机详情图测试", image="uploads/material_images/p1.jpg", stock=0)
        wms.db.session.add(mat)
        wms.db.session.flush()
        wms.db.session.add_all([
            wms.MaterialImage(material_id=mat.id, image="uploads/material_images/p1.jpg", sort_order=0),
            wms.MaterialImage(material_id=mat.id, image="uploads/material_images/p2.jpg", sort_order=1),
        ])
        wms.db.session.commit()
    resp = client.get("/mobile/material", query_string={"code": "MOB-IMG-1"})
    assert resp.status_code == 200
    assert resp.text.count("uploads/material_images/p1.jpg") == 1
    assert resp.text.count("uploads/material_images/p2.jpg") == 1
