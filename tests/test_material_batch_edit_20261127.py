# -*- coding: utf-8 -*-
"""Regression tests for Material Management batch-edit feature (2026-11-27).

Requirement:
- Allow batch editing 5 master-data fields for selected materials:
  brand (品牌), category_id (分类), unit_id (单位),
  storage_location (库位), min_stock (最低库存).
- Only explicitly selected fields are modified; unselected fields stay untouched.
- Atomic all-or-nothing commit, (name, spec, brand) dedup protection,
  min_stock / reorder_point invariant alignment, options pool invalidation,
  audit trail, role isolation, strict CSP + accessible labels, and zero impact
  on three-ledger stock tables (Material.stock / LocationInventory / StockTransaction).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as wms  # noqa: E402
import routes.options_api as options_api  # noqa: E402


def _login(client, username, password="secret"):
    resp = client.post(
        "/login",
        data={"username": username, "password": password},
        content_type="application/x-www-form-urlencoded",
    )
    assert resp.status_code in (200, 302)
    return client


@pytest.fixture
def env():
    options_api._POOL_CACHE.clear()
    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    with wms.app.app_context():
        assert str(wms.db.engine.url) == "sqlite:///:memory:"
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()

        users = {}
        for uname, role in [
            ("admin", "admin"),
            ("wh_user", "warehouse"),
            ("fin_user", "finance"),
            ("sales_user", "sales"),
            ("pur_user", "purchase"),
            ("viewer_user", "viewer"),
            ("plain_user", "user"),
        ]:
            u = wms.User(
                username=uname,
                password_hash=generate_password_hash("secret"),
                role=role,
                must_change_password=False,
            )
            wms.db.session.add(u)
            users[role] = u

        cat1 = wms.MaterialCategory(code="C-01", name="电气件")
        cat2 = wms.MaterialCategory(code="C-02", name="五金件")
        unit1 = wms.Unit(code="PCS", name="个")
        unit2 = wms.Unit(code="SET", name="套")
        sup1 = wms.Supplier(code="SUP-01", name="默认供应商")
        wh1 = wms.Warehouse(code="WH-01", name="主仓库", is_default=True)
        wms.db.session.add_all([cat1, cat2, unit1, unit2, sup1, wh1])
        wms.db.session.flush()

        m1 = wms.Material(
            code="BM-001",
            name="深沟球轴承",
            spec="6204-2RS",
            brand="SKF",
            category_id=cat1.id,
            unit_id=unit1.id,
            supplier_id=sup1.id,
            storage_location="A-01-01",
            min_stock=5,
            reorder_point=8,
            price=12.5,
            stock=0,
            remark="原备注1",
        )
        m2 = wms.Material(
            code="BM-002",
            name="六角螺母",
            spec="M8",
            brand="国产",
            category_id=cat1.id,
            unit_id=unit1.id,
            supplier_id=sup1.id,
            storage_location="A-01-02",
            min_stock=10,
            reorder_point=50,
            price=0.5,
            stock=0,
            remark="原备注2",
        )
        m3 = wms.Material(
            code="BM-003",
            name="平垫片",
            spec="M8",
            brand="保留品牌",
            category_id=cat1.id,
            unit_id=unit1.id,
            supplier_id=sup1.id,
            storage_location="Z-09-09",
            min_stock=3,
            reorder_point=6,
            price=0.2,
            stock=0,
            remark="未选中不动",
        )
        wms.db.session.add_all([m1, m2, m3])
        wms.set_system_setting("location_management_enabled", "0")
        wms.set_system_setting("inventory_alert_enabled", "1")
        wms.db.session.commit()

        ids = {
            "cat1": cat1.id,
            "cat2": cat2.id,
            "unit1": unit1.id,
            "unit2": unit2.id,
            "sup1": sup1.id,
            "wh1": wh1.id,
            "m1": m1.id,
            "m2": m2.id,
            "m3": m3.id,
        }

    client = _login(wms.app.test_client(), "wh_user")
    yield client, ids
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
    options_api._POOL_CACHE.clear()


def test_batch_edit_all_five_fields_and_preserves_unselected(env):
    """Updating all 5 fields updates selected materials, leaves untouched rows/columns intact, and logs audit."""
    client, ids = env
    rev1_before = client.get(f"/material/{ids['m1']}").get_json()["material"]["edit_revision"]

    resp = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"], str(ids["m2"])],
            "updates": {
                "brand": "  ABB  ",
                "category_id": ids["cat2"],
                "unit_id": str(ids["unit2"]),
                "storage_location": "  B-02-05  ",
                "min_stock": 20.5,
            },
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert body["status"] == "success"
    assert body["updated_count"] == 2
    assert set(body["updated_fields"]) == {
        "brand",
        "category_id",
        "unit_id",
        "storage_location",
        "min_stock",
    }

    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        m2 = wms.db.session.get(wms.Material, ids["m2"])
        m3 = wms.db.session.get(wms.Material, ids["m3"])

        # Selected materials updated cleanly
        for m in (m1, m2):
            assert m.brand == "ABB"
            assert m.category_id == ids["cat2"]
            assert m.unit_id == ids["unit2"]
            assert m.storage_location == "B-02-05"
            assert m.min_stock == 20.5
        # Safety stock invariant: m1 raised from 8 -> 20.5; m2 kept at 50 (>= 20.5)
        assert m1.reorder_point == 20.5
        assert m2.reorder_point == 50.0
        # Non-target columns preserved
        assert m1.price == 12.5 and m1.remark == "原备注1" and m1.supplier_id == ids["sup1"]
        assert m2.price == 0.5 and m2.remark == "原备注2" and m2.stock == 0
        # Unselected material untouched
        assert m3.brand == "保留品牌"
        assert m3.category_id == ids["cat1"]
        assert m3.unit_id == ids["unit1"]
        assert m3.storage_location == "Z-09-09"
        assert m3.min_stock == 3 and m3.reorder_point == 6
        # Audit & operation log created
        audit = wms.OperationAudit.query.filter_by(operation="batch_edit_material").one()
        assert "BM-001" in (audit.old_data or "") and "ABB" in (audit.new_data or "")
        assert wms.OperationLog.query.filter_by(operation_type="批量修改物料").count() == 1
        # Accounting tables untouched
        assert wms.LocationInventory.query.count() == 0
        assert wms.StockTransaction.query.count() == 0

    rev1_after = client.get(f"/material/{ids['m1']}").get_json()["material"]["edit_revision"]
    assert rev1_after != rev1_before


def test_batch_edit_partial_fields_and_explicit_clear(env):
    """Unchecked fields stay unchanged; checked empty values explicitly clear nullable fields."""
    client, ids = env

    # 1. Partial update: only storage_location
    r1 = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"], ids["m2"]], "updates": {"storage_location": "C-03-01"}},
    )
    assert r1.status_code == 200
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        assert m1.storage_location == "C-03-01"
        assert m1.brand == "SKF"
        assert m1.category_id == ids["cat1"]
        assert m1.unit_id == ids["unit1"]
        assert m1.min_stock == 5

    # 2. Explicit clear of brand, category_id, unit_id, storage_location while preserving min_stock
    r2 = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"], ids["m2"]],
            "updates": {
                "brand": "",
                "category_id": None,
                "unit_id": "",
                "storage_location": "   ",
            },
        },
    )
    assert r2.status_code == 200
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        m2 = wms.db.session.get(wms.Material, ids["m2"])
        for m in (m1, m2):
            assert m.brand is None
            assert m.category_id is None
            assert m.unit_id is None
            assert m.storage_location is None
        assert m1.min_stock == 5
        assert m2.min_stock == 10


@pytest.mark.parametrize("alert_enabled", ["0", "1"])
def test_batch_edit_min_stock_works_regardless_of_alert_toggle_and_validates(env, alert_enabled):
    """min_stock works whether inventory_alert_enabled is '0' or '1', aligns reorder_point, and rejects invalid inputs."""
    client, ids = env
    with wms.app.app_context():
        wms.set_system_setting("inventory_alert_enabled", alert_enabled)
        wms.db.session.commit()

    # Valid update including zero and decimal rounding
    r_ok = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"], ids["m2"]], "updates": {"min_stock": "15.126"}},
    )
    assert r_ok.status_code == 200
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        m2 = wms.db.session.get(wms.Material, ids["m2"])
        assert m1.min_stock == 15.13 and m1.reorder_point == 15.13
        assert m2.min_stock == 15.13 and m2.reorder_point == 50.0

    r_zero = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"]], "updates": {"min_stock": 0}},
    )
    assert r_zero.status_code == 200
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        assert m1.min_stock == 0.0 and m1.reorder_point == 15.13

    # Invalid values rejected with 400 and no mutation
    for bad_val in (None, "", "   ", -1, -0.01, "abc", True, False, 100_000_000, "NaN", "inf"):
        r_bad = client.post(
            "/material/batch_edit",
            json={"ids": [ids["m1"]], "updates": {"min_stock": bad_val}},
        )
        assert r_bad.status_code == 400, f"Expected 400 for min_stock={bad_val!r}, got {r_bad.status_code}"


def test_batch_edit_brand_dedupe_conflicts_reject_atomically(env):
    """Brand changes colliding with external rows or within the batch roll back ALL fields atomically."""
    client, ids = env
    with wms.app.app_context():
        # Same (name, spec) as m1 ("深沟球轴承", "6204-2RS") but different brand
        m_same_spec = wms.Material(
            code="BM-004",
            name="深沟球轴承",
            spec="6204-2RS",
            brand="NSK",
            category_id=ids["cat1"],
            unit_id=ids["unit1"],
            storage_location="D-01",
            stock=0,
        )
        wms.db.session.add(m_same_spec)
        wms.db.session.commit()
        same_spec_id = m_same_spec.id

    # Case A: External conflict (change m1 brand to ' nsk ' matching unselected BM-004)
    r_ext = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"], ids["m2"]],
            "updates": {"brand": " nsk ", "storage_location": "SHOULD-NOT-COMMIT"},
        },
    )
    assert r_ext.status_code == 400
    assert "BM-004" in r_ext.get_json()["msg"]
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).brand == "SKF"
        assert wms.db.session.get(wms.Material, ids["m2"]).storage_location == "A-01-02"

    # Case B: Intra-batch conflict (m1 and BM-004 both selected, both set to 'FAG')
    r_intra = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"], same_spec_id],
            "updates": {"brand": "FAG", "storage_location": "SHOULD-NOT-COMMIT"},
        },
    )
    assert r_intra.status_code == 400
    assert "BM-001" in r_intra.get_json()["msg"] and "BM-004" in r_intra.get_json()["msg"]
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).brand == "SKF"
        assert wms.db.session.get(wms.Material, same_spec_id).brand == "NSK"
        assert wms.db.session.get(wms.Material, same_spec_id).storage_location == "D-01"

    # Case C: Non-conflicting batch including a material that already has the target brand succeeds
    r_self = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"], ids["m2"]], "updates": {"brand": "SKF"}},
    )
    assert r_self.status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).brand == "SKF"
        assert wms.db.session.get(wms.Material, ids["m2"]).brand == "SKF"


def test_batch_edit_validation_xss_and_smuggled_fields(env):
    """Rejects bad IDs, >200 batch size, missing rows, invalid FKs, overlong strings, empty/extra fields; sanitizes XSS."""
    client, ids = env

    # Empty IDs
    assert client.post("/material/batch_edit", json={"ids": [], "updates": {"brand": "X"}}).status_code == 400
    # Duplicate IDs dedup cleanly (still counts as 1)
    r_dup_id = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"], ids["m1"]], "updates": {"storage_location": "R-01"}},
    )
    assert r_dup_id.status_code == 200 and r_dup_id.get_json()["updated_count"] == 1
    # Too many IDs (>200)
    assert (
        client.post(
            "/material/batch_edit",
            json={"ids": list(range(1, 202)), "updates": {"brand": "X"}},
        ).status_code
        == 400
    )
    # Invalid ID types (bool / negative / string garbage)
    for bad_ids in ([True], [-1], [0], ["abc"], "1"):
        assert (
            client.post("/material/batch_edit", json={"ids": bad_ids, "updates": {"brand": "X"}}).status_code
            == 400
        )
    # Non-existent ID -> 404 and atomic (existing m1 untouched)
    r_404 = client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"], 999999], "updates": {"storage_location": "NO-COMMIT"}},
    )
    assert r_404.status_code == 404
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).storage_location == "R-01"

    # Empty updates
    assert client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {}}).status_code == 400
    # Smuggled disallowed fields (stock, price, code, status)
    for forbidden in ({"stock": 999}, {"price": 1.0}, {"code": "HACK"}, {"status": "inactive"}):
        assert (
            client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": forbidden}).status_code
            == 400
        )
    # Non-existent FK
    assert (
        client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"category_id": 99999}}).status_code
        == 400
    )
    assert (
        client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"unit_id": 99999}}).status_code
        == 400
    )
    assert (
        client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"category_id": True}}).status_code
        == 400
    )
    # Overlong strings (>100 chars)
    r_b_long = client.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"brand": "B" * 101}})
    assert r_b_long.status_code == 400 and "品牌不能超过 100 个字符" in r_b_long.get_json()["msg"]
    r_l_long = client.post(
        "/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"storage_location": "L" * 101}}
    )
    assert r_l_long.status_code == 400 and "库位不能超过 100 个字符" in r_l_long.get_json()["msg"]

    # XSS sanitization
    r_xss = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"]],
            "updates": {
                "brand": "<script>alert(1)</script>施耐德",
                "storage_location": "javascript:evil<img onerror=x>A-09",
            },
        },
    )
    assert r_xss.status_code == 200
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        assert "<" not in m1.brand and ">" not in m1.brand and "施耐德" in m1.brand
        assert "<" not in m1.storage_location and "javascript:" not in m1.storage_location.lower()


def test_batch_edit_permissions(env):
    """admin & warehouse succeed; finance/sales/purchase/viewer/user get 403 on AJAX; anonymous rejected."""
    _, ids = env
    ajax = {"X-Requested-With": "XMLHttpRequest"}

    # Anonymous
    anon = wms.app.test_client()
    r_anon = anon.post("/material/batch_edit", json={"ids": [ids["m1"]], "updates": {"brand": "ANON"}}, headers=ajax)
    assert r_anon.status_code in (302, 401)

    # Disallowed roles
    for uname in ("fin_user", "sales_user", "pur_user", "viewer_user", "plain_user"):
        c = _login(wms.app.test_client(), uname)
        r = c.post(
            "/material/batch_edit",
            json={"ids": [ids["m1"]], "updates": {"brand": f"BY-{uname}"}},
            headers=ajax,
        )
        assert r.status_code == 403, f"Role user {uname} must get 403, got {r.status_code}"

    # Verify DB still untouched
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).brand == "SKF"

    # Admin succeeds
    admin_client = _login(wms.app.test_client(), "admin")
    r_admin = admin_client.post(
        "/material/batch_edit",
        json={"ids": [ids["m1"]], "updates": {"brand": "ADMIN-OK"}},
        headers=ajax,
    )
    assert r_admin.status_code == 200
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, ids["m1"]).brand == "ADMIN-OK"


def test_batch_edit_invalidates_options_pool_and_preserves_three_ledgers(env):
    """Options pool sees new brand/location immediately; three-ledger invariants remain untouched."""
    client, ids = env
    from services.warehouse_stock_service import apply_opening_balance, verify_material_three_ledgers

    with wms.app.app_context():
        wms.set_system_setting("location_management_enabled", "1")
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        op_id = wms.User.query.filter_by(username="wh_user").one().id
        m1.stock = 25
        apply_opening_balance(m1, 25, warehouse="主仓库", location="LOC-A1", operator_id=op_id)
        wms.db.session.commit()
        tx_count_before = wms.StockTransaction.query.count()
        loc_inv_before = wms.LocationInventory.query.filter_by(material_id=ids["m1"]).one().quantity
        ok_before, detail_before = verify_material_three_ledgers(m1)
        assert ok_before is True, detail_before

    # Warm options pool cache
    warm = client.get("/api/options/material?kw=NEWLOC-88").get_json()["data"]
    assert not warm

    # Batch edit brand & storage_location (row count / max id unchanged -> requires explicit invalidation)
    resp = client.post(
        "/material/batch_edit",
        json={
            "ids": [ids["m1"]],
            "updates": {"brand": "OMRON-NEW", "storage_location": "NEWLOC-88"},
        },
    )
    assert resp.status_code == 200

    # Immediately searchable in options pool
    after = client.get("/api/options/material?kw=NEWLOC-88").get_json()["data"]
    assert any(item["code"] == "BM-001" and item.get("storage_location") == "NEWLOC-88" for item in after)

    # Three-ledger accounting completely untouched
    with wms.app.app_context():
        m1 = wms.db.session.get(wms.Material, ids["m1"])
        assert m1.stock == 25
        assert wms.StockTransaction.query.count() == tx_count_before
        assert wms.LocationInventory.query.filter_by(material_id=ids["m1"]).one().quantity == loc_inv_before
        ok_after, detail = verify_material_three_ledgers(m1)
        assert ok_after is True, detail


class _FormNodes(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.form = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form = attrs.get("id", "form")
        self.nodes.append((tag, attrs, self.form))

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = None


def test_batch_edit_html_strict_csp_labels_and_js_runtime(env):
    """Template exposes toolbar button, modal, accessible labels, strict CSP, and real JS builds safe payloads."""
    client, _ = env
    html = client.get("/material").get_data(as_text=True)

    # 1. Markup & JSON config
    assert 'id="toolbarBatchEditBtn"' in html
    assert 'data-material-action="toolbarBatchEdit"' in html
    assert 'id="batchEditModal"' in html
    assert 'id="batchEditForm"' in html
    for ctrl_id in (
        "batchEditEnableBrand",
        "batchEditBrand",
        "batchEditEnableCategory",
        "batchEditCategory",
        "batchEditEnableUnit",
        "batchEditUnit",
        "batchEditEnableStorageLocation",
        "batchEditStorageLocation",
        "batchEditEnableMinStock",
        "batchEditMinStock",
    ):
        assert f'id="{ctrl_id}"' in html, f"Missing #{ctrl_id}"

    match = re.search(r'<script type="application/json" id="material-list-data">([\s\S]*?)</script>', html)
    assert match
    page_data = json.loads(match.group(1))
    assert page_data["urls"]["batchEdit"] == "/material/batch_edit"

    # 2. Zero inline on* handlers & all form controls properly labelled
    nodes = _FormNodes(html).nodes
    assert not [(t, k) for t, a, _ in nodes for k in a if re.fullmatch("on[a-z]+", k)]
    labels = {a.get("for") for t, a, _ in nodes if t == "label" and a.get("for")}
    for ctrl_id in (
        "batchEditBrand",
        "batchEditCategory",
        "batchEditUnit",
        "batchEditStorageLocation",
        "batchEditMinStock",
    ):
        assert ctrl_id in labels, f"Missing <label for='{ctrl_id}'>"

    # 3. Node runtime check against real material-list.js + api.js
    node = shutil.which("node")
    assert node, "Node is required to verify material-list.js runtime"
    program = r"""
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');

const root = process.argv[1];
const jsSrc = fs.readFileSync(path.join(root, 'app/static/js/pages/material-list.js'), 'utf8');
const apiSrc = fs.readFileSync(path.join(root, 'app/static/js/api.js'), 'utf8');

// Extract toolbar + batch-edit slice and action map from real shipped JS
class El {
  constructor(id, tag='input') {
    this.id = id; this.tagName = tag; this.disabled = false; this.checked = false;
    this.value = ''; this.textContent = ''; this.dataset = {}; this.focused = false;
    this.classList = { contains: () => false, add() {}, remove() {}, toggle() {} };
    this.handlers = {};
  }
  focus() { this.focused = true; }
  addEventListener(e, fn) { (this.handlers[e] ||= []).push(fn); }
}

const nodes = new Map();
for (const id of [
  'toolbarEditBtn','toolbarBatchEditBtn','toolbarCopyBtn','toolbarPrintBtn','toolbarRemotePrintBtn',
  'toolbarFindImageBtn','toolbarDeleteBtn','toolbarMergeBtn','materialTable','checkAll',
  'batchEditModal','batchEditForm','batchEditCount','batchEditSubmitBtn',
  'batchEditEnableBrand','batchEditBrand',
  'batchEditEnableCategory','batchEditCategory',
  'batchEditEnableUnit','batchEditUnit',
  'batchEditEnableStorageLocation','batchEditStorageLocation',
  'batchEditEnableMinStock','batchEditMinStock',
]) nodes.set(id, new El(id));
nodes.get('batchEditEnableBrand').dataset.targetId = 'batchEditBrand';
nodes.get('batchEditEnableCategory').dataset.targetId = 'batchEditCategory';
nodes.get('batchEditEnableUnit').dataset.targetId = 'batchEditUnit';
nodes.get('batchEditEnableStorageLocation').dataset.targetId = 'batchEditStorageLocation';
nodes.get('batchEditEnableMinStock').dataset.targetId = 'batchEditMinStock';

const checks = ['10', '20'].map(v => Object.assign(new El('cb_'+v), {value: v, checked: true}));
const toasts = [], calls = [];
let modalShown = false, modalHidden = false, reloads = 0;
const modalInst = { show(){ modalShown = true; }, hide(){ modalHidden = true; } };
const doc = {
  getElementById: id => nodes.get(id) || null,
  querySelectorAll: sel => sel === '#materialTable .check-item:checked' ? checks.filter(c => c.checked) : [],
  querySelector: sel => sel.includes('csrf-token') ? {content: 'csrf-tok'} : null,
  addEventListener() {},
};
const ctx = {
  materialPageData: { canDelete: true, urls: { batchEdit: '/material/batch_edit' } },
  document: doc, console, Promise, Error, JSON, Number, String, Array, Object, Set, Map,
  FormData: class {}, URLSearchParams,
  setTimeout(fn) { fn(); return 1; },
  showToast(msg, type) { toasts.push({msg, type}); },
  location: { reload() { reloads++; } },
  bootstrap: { Modal: class { static getOrCreateInstance() { return modalInst; } static getInstance() { return modalInst; } } },
  fetch(url, opts) {
    calls.push({url, opts});
    return Promise.resolve({
      ok: true, status: 200,
      json: () => Promise.resolve({status: 'success', msg: '已批量修改 2 条物料'}),
    });
  },
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(apiSrc, ctx);

// Run toolbar + batch edit sections from real file
const s1 = jsSrc.indexOf('var materialDeleteBusy = false;');
const e1 = jsSrc.indexOf('// 2026-09-25：物料停用', s1);
const s2 = jsSrc.indexOf('// ==================== 批量修改物料');
const e2 = jsSrc.indexOf('// ==================== 批量修改物料结束', s2);
assert(s1 >= 0 && e1 > s1, 'toolbar slice missing');
assert(s2 >= 0 && e2 > s2, 'batch-edit slice missing');
vm.runInContext(jsSrc.slice(s1, e1) + '\n' + jsSrc.slice(s2, e2), ctx);

// 1. Multi-select enables toolbarBatchEditBtn
ctx.updateToolbarButtons();
assert.equal(nodes.get('toolbarBatchEditBtn').disabled, false);

// 2. Open modal freezes IDs and resets inputs disabled
ctx.toolbarBatchEdit();
assert.equal(modalShown, true);
assert.equal(nodes.get('batchEditCount').textContent, '2');
assert.equal(nodes.get('batchEditBrand').disabled, true);
assert.equal(nodes.get('batchEditMinStock').disabled, true);

// 3. Submit with nothing checked -> warning, zero fetch
ctx.submitBatchEdit();
assert.equal(calls.length, 0);
assert.equal(toasts.at(-1).type, 'warning');

// 4. Enable brand + min_stock (invalid negative) -> warning, zero fetch
nodes.get('batchEditEnableBrand').checked = true;
ctx.toggleBatchEditField(nodes.get('batchEditEnableBrand'));
assert.equal(nodes.get('batchEditBrand').disabled, false);
nodes.get('batchEditBrand').value = 'ABB';

nodes.get('batchEditEnableMinStock').checked = true;
ctx.toggleBatchEditField(nodes.get('batchEditEnableMinStock'));
nodes.get('batchEditMinStock').value = '-5';
ctx.submitBatchEdit();
assert.equal(calls.length, 0);
assert.equal(toasts.at(-1).type, 'warning');

// 5. Fix min_stock + enable category clear -> posts exact checked-only payload with CSRF
nodes.get('batchEditMinStock').value = '12.5';
nodes.get('batchEditEnableCategory').checked = true;
ctx.toggleBatchEditField(nodes.get('batchEditEnableCategory'));
nodes.get('batchEditCategory').value = '';

Promise.resolve(ctx.submitBatchEdit()).then(() => {
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, '/material/batch_edit');
  assert.equal(calls[0].opts.headers['X-CSRFToken'], 'csrf-tok');
  const sent = JSON.parse(calls[0].opts.body);
  assert.deepEqual(sent, {
    ids: ['10', '20'],
    updates: { brand: 'ABB', category_id: null, min_stock: 12.5 },
  });
  assert.equal('unit_id' in sent.updates, false);
  assert.equal('storage_location' in sent.updates, false);
  assert.equal(modalHidden, true);
  assert.equal(reloads, 1);
});
"""
    res = subprocess.run(
        [node, "-e", program, str(ROOT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert res.returncode == 0, res.stdout + res.stderr
