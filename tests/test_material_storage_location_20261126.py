# -*- coding: utf-8 -*-
"""Regression tests for optional Material.storage_location field (2026-11-26).

Requirement:
- Add an optional `库位` (`storage_location`) field to Material master data so
  warehouse staff can quickly locate materials and later run location-based
  stocktakes.
- Completely independent of `location_management_enabled` (works identically
  when location management is OFF `'0'` or ON `'1'`, and never writes to
  `LocationInventory` or three-ledger accounting tables).
"""
from __future__ import annotations

import io
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
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
from utils import serialize_material, serialize_material_legacy  # noqa: E402

AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture
def client():
    import routes.options_api as options_api
    options_api._POOL_CACHE.clear()
    wms.app.config["TESTING"] = True
    wms.app.config["WTF_CSRF_ENABLED"] = False
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        admin = wms.User(
            username="admin",
            password_hash=generate_password_hash("admin"),
            role="admin",
            must_change_password=False,
        )
        unit = wms.Unit(code="PCS", name="个")
        cat = wms.MaterialCategory(code="CAT-01", name="五金件")
        sup = wms.Supplier(code="SUP-01", name="鑫达五金")
        wh = wms.Warehouse(code="WH-01", name="主仓库", is_default=True)
        wms.db.session.add_all([admin, unit, cat, sup, wh])
        wms.set_system_setting("location_management_enabled", "0")
        wms.db.session.commit()
    c = wms.app.test_client()
    r = c.post(
        "/login",
        data={"username": "admin", "password": "admin"},
        content_type="application/x-www-form-urlencoded",
    )
    assert r.status_code in (200, 302)
    yield c
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


@pytest.mark.parametrize("loc_mgmt", ["0", "1"])
def test_add_material_storage_location_optional_and_independent_of_switch(client, loc_mgmt):
    """Adding material with/without storage_location works regardless of location_management_enabled."""
    with wms.app.app_context():
        wms.set_system_setting("location_management_enabled", loc_mgmt)
        wms.db.session.commit()

    # 1. Optional: omit storage_location completely
    r1 = client.post(
        "/material/add",
        data={"code": f"SL-EMPTY-{loc_mgmt}", "name": f"无库位物料{loc_mgmt}", "spec": "S1"},
        headers=AJAX_HEADERS,
    )
    assert r1.status_code == 200 and r1.get_json()["status"] == "success"

    # 2. Provided: with whitespace and unsafe angle brackets (sanitized)
    r2 = client.post(
        "/material/add",
        data={
            "code": f"SL-SET-{loc_mgmt}",
            "name": f"有库位物料{loc_mgmt}",
            "spec": "S2",
            "storage_location": "  A-01-02<tag>  ",
        },
        headers=AJAX_HEADERS,
    )
    assert r2.status_code == 200 and r2.get_json()["status"] == "success"

    # 3. Too long (>100 chars) rejected cleanly
    r3 = client.post(
        "/material/add",
        data={
            "code": f"SL-LONG-{loc_mgmt}",
            "name": f"超长库位{loc_mgmt}",
            "storage_location": "A" * 101,
        },
        headers=AJAX_HEADERS,
    )
    assert r3.status_code == 400 and r3.get_json()["status"] == "error"
    assert "库位不能超过 100 个字符" in r3.get_json()["msg"]

    with wms.app.app_context():
        m1 = wms.Material.query.filter_by(code=f"SL-EMPTY-{loc_mgmt}").one()
        m2 = wms.Material.query.filter_by(code=f"SL-SET-{loc_mgmt}").one()
        assert m1.storage_location is None
        assert m2.storage_location == "A-01-02tag"
        # Descriptive master field must never write to LocationInventory accounting table
        assert wms.LocationInventory.query.filter(
            wms.LocationInventory.material_id.in_([m1.id, m2.id])
        ).count() == 0
        # Audit log captured storage_location
        audit = wms.OperationAudit.query.filter_by(
            action="add_material", target_id=m2.id
        ).first()
        assert audit is not None and "A-01-02tag" in (audit.new_data or "")


def test_edit_copy_revision_and_clear_storage_location(client):
    """Edit sets/changes/clears storage_location, preserves when omitted, and bumps edit_revision."""
    r = client.post(
        "/material/add",
        data={"code": "SL-ED-1", "name": "可编辑库位", "spec": "M8", "storage_location": "B-02-01"},
        headers=AJAX_HEADERS,
    )
    assert r.status_code == 200
    with wms.app.app_context():
        mid = wms.Material.query.filter_by(code="SL-ED-1").one().id

    # GET detail exposes storage_location and edit_revision
    detail = client.get(f"/material/{mid}").get_json()["material"]
    assert detail["storage_location"] == "B-02-01"
    rev1 = detail["edit_revision"]

    # Copy carries storage_location into draft
    copied = client.post(f"/material/{mid}/copy", headers=AJAX_HEADERS).get_json()["material"]
    assert copied["storage_location"] == "B-02-01"

    # Legacy edit omitting storage_location key preserves existing value
    r_omit = client.post(
        f"/material/edit/{mid}",
        data={"edit_revision": rev1, "code": "SL-ED-1", "name": "可编辑库位", "spec": "M8"},
        headers=AJAX_HEADERS,
    )
    assert r_omit.status_code == 200 and r_omit.get_json()["status"] == "success"
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, mid).storage_location == "B-02-01"

    # Edit changes storage_location and changes revision
    rev2 = client.get(f"/material/{mid}").get_json()["material"]["edit_revision"]
    r_upd = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": rev2,
            "code": "SL-ED-1",
            "name": "可编辑库位",
            "spec": "M8",
            "storage_location": "C-03-05",
        },
        headers=AJAX_HEADERS,
    )
    assert r_upd.status_code == 200 and r_upd.get_json()["status"] == "success"
    rev3 = client.get(f"/material/{mid}").get_json()["material"]["edit_revision"]
    assert rev3 != rev2, "Changing storage_location must advance edit_revision"

    # Stale revision rejected with 409
    r_stale = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": rev2,
            "code": "SL-ED-1",
            "name": "可编辑库位",
            "spec": "M8",
            "storage_location": "D-01",
        },
        headers=AJAX_HEADERS,
    )
    assert r_stale.status_code == 409

    # Overlong storage_location rejected with 400 without mutating DB
    r_long = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": rev3,
            "code": "SL-ED-1",
            "name": "可编辑库位",
            "spec": "M8",
            "storage_location": "X" * 101,
        },
        headers=AJAX_HEADERS,
    )
    assert r_long.status_code == 400
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, mid).storage_location == "C-03-05"

    # Submitting empty string clears storage_location back to None
    r_clear = client.post(
        f"/material/edit/{mid}",
        data={
            "edit_revision": rev3,
            "code": "SL-ED-1",
            "name": "可编辑库位",
            "spec": "M8",
            "storage_location": "",
        },
        headers=AJAX_HEADERS,
    )
    assert r_clear.status_code == 200 and r_clear.get_json()["status"] == "success"
    with wms.app.app_context():
        assert wms.db.session.get(wms.Material, mid).storage_location is None


def test_list_display_search_sort_and_apis(client):
    """Material list renders storage_location, supports search (incl. NFKC) and sort, and APIs expose it."""
    with wms.app.app_context():
        m_a = wms.Material(code="M-001", name="轴承甲", spec="6204", storage_location="A-01-01")
        m_b = wms.Material(code="M-002", name="螺母乙", spec="M8", storage_location="C-09-02")
        m_c = wms.Material(code="M-003", name="垫片丙", spec="M8", storage_location=None)
        wms.db.session.add_all([m_a, m_b, m_c])
        wms.db.session.commit()
        ids = (m_a.id, m_b.id, m_c.id)

    # List page renders storage_location header & cell even when location_management_enabled='0'
    html = client.get("/material").get_data(as_text=True)
    assert 'data-column-key="storage_location"' in html
    assert 'data-sortable="storage_location"' in html
    assert ">A-01-01<" in html
    assert ">C-09-02<" in html

    # Search by storage_location (including full-width NFKC)
    html_search = client.get("/material?search=Ａ-01-01").get_data(as_text=True)
    assert "M-001" in html_search
    assert "M-002" not in html_search

    # Sort by storage_location desc puts C-09-02 before A-01-01
    html_desc = client.get("/material?sort=storage_location&order=desc").get_data(as_text=True)
    assert html_desc.index("C-09-02") < html_desc.index("A-01-01")

    # Serializers & APIs
    with wms.app.app_context():
        m_a = wms.db.session.get(wms.Material, ids[0])
        assert serialize_material(m_a)["storage_location"] == "A-01-01"
        assert serialize_material_legacy(m_a)["storage_location"] == "A-01-01"
        assert wms.api_material_payload(m_a)["storage_location"] == "A-01-01"
        from routes.mobile import mobile_material_payload
        assert mobile_material_payload(m_a)["storage_location"] == "A-01-01"
        from routes.print_queue import _material_label_data
        assert _material_label_data(m_a)["storage_location"] == "A-01-01"

    api_list = client.get("/material/api/list").get_json()["materials"]
    by_code = {row["code"]: row for row in api_list}
    assert by_code["M-001"]["storage_location"] == "A-01-01"
    assert by_code["M-003"]["storage_location"] == ""

    # /api/options/material, /api/material/search, /mobile/api/material_archive/search match storage_location
    opt = client.get("/api/options/material?kw=C-09-02").get_json()
    assert any(item["code"] == "M-002" and item.get("storage_location") == "C-09-02" for item in opt["data"])

    search_api = client.get("/api/material/search?keyword=C-09-02").get_json()
    assert any(item["code"] == "M-002" and item["storage_location"] == "C-09-02" for item in search_api["data"])

    mob_arch = client.get("/mobile/api/material_archive/search?keyword=C-09-02").get_json()
    assert any(item["code"] == "M-002" and item["storage_location"] == "C-09-02" for item in mob_arch["data"])

    # Mobile detail, archive print, and label batch print show storage_location
    mob_html = client.get("/mobile/material?code=M-001").get_data(as_text=True)
    assert "库位" in mob_html and "A-01-01" in mob_html
    arch_html = client.get(f"/material_archive/{ids[0]}/print").get_data(as_text=True)
    assert "库位" in arch_html and "A-01-01" in arch_html
    lbl_html = client.get(f"/label/batch_print?ids={ids[0]}").get_data(as_text=True)
    assert "A-01-01" in lbl_html


def test_excel_template_export_and_import_roundtrip(client):
    """Both templates include 库位 identically; export/import roundtrips and legacy files without 库位 still import."""
    t1 = load_workbook(io.BytesIO(client.get("/material/download_template").data)).active
    t2 = load_workbook(io.BytesIO(client.get("/export/template/material").data)).active
    h1 = [c.value for c in t1[1]]
    h2 = [c.value for c in t2[1]]
    assert h1 == h2
    assert "库位" in h1

    # Import with 库位 + overlong row + legacy file without 库位
    wb = Workbook()
    ws = wb.active
    ws.append(["物料编码", "物料名称", "品牌", "规格", "库位", "单价"])
    ws.append(["IMP-LOC-1", "带库位物料", "ABB", "S1", "D-04-08", 10])
    ws.append(["IMP-LOC-2", "空库位物料", "ABB", "S2", "", 12])
    ws.append(["IMP-LOC-BAD", "超长库位物料", "ABB", "S3", "Z" * 101, 15])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    resp = client.post(
        "/material/import",
        data={"file": (buf, "with_loc.xlsx")},
        content_type="multipart/form-data",
        headers=AJAX_HEADERS,
    )
    body = resp.get_json()
    assert body["status"] == "success" and body["count"] == 2
    assert "库位不能超过100个字符" in (body.get("warnings") or "")

    # Legacy file without 库位 column still imports cleanly
    wb_old = Workbook()
    ws_old = wb_old.active
    ws_old.append(["物料编码", "物料名称", "规格", "单价"])
    ws_old.append(["IMP-OLD-1", "旧模板物料", "OLD-S", 5])
    buf_old = io.BytesIO()
    wb_old.save(buf_old)
    buf_old.seek(0)
    r_old = client.post(
        "/material/import",
        data={"file": (buf_old, "legacy.xlsx")},
        content_type="multipart/form-data",
        headers=AJAX_HEADERS,
    )
    assert r_old.get_json()["status"] == "success" and r_old.get_json()["count"] == 1

    with wms.app.app_context():
        assert wms.Material.query.filter_by(code="IMP-LOC-1").one().storage_location == "D-04-08"
        assert wms.Material.query.filter_by(code="IMP-LOC-2").one().storage_location is None
        assert wms.Material.query.filter_by(code="IMP-LOC-BAD").first() is None
        assert wms.Material.query.filter_by(code="IMP-OLD-1").one().storage_location is None

    # Export includes 库位 column and supports search by storage_location
    exp_all = load_workbook(io.BytesIO(client.get("/material/export").data)).active
    exp_headers = [c.value for c in exp_all[1]]
    assert "库位" in exp_headers
    loc_idx = exp_headers.index("库位")
    rows = {r[0]: r[loc_idx] for r in exp_all.iter_rows(min_row=2, values_only=True)}
    assert rows["IMP-LOC-1"] == "D-04-08"
    assert rows["IMP-LOC-2"] in ("", None)

    exp_filtered = load_workbook(io.BytesIO(client.get("/material/export?search=D-04-08").data)).active
    filtered_codes = [r[0] for r in exp_filtered.iter_rows(min_row=2, values_only=True)]
    assert filtered_codes == ["IMP-LOC-1"]


def test_ensure_material_status_column_adds_storage_location_idempotently(tmp_path):
    """Legacy SQLite databases lacking storage_location are migrated idempotently."""
    db_file = tmp_path / "legacy_inventory.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, name TEXT, status VARCHAR(20))")
    conn.execute("INSERT INTO material (code, name, status) VALUES ('OLD-1', '旧物料', 'active')")
    conn.commit()
    conn.close()

    wms.ensure_material_status_column(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(material)")]
    indexes = [r[1] for r in conn.execute("PRAGMA index_list(material)")]
    row = conn.execute("SELECT code, status, storage_location FROM material").fetchone()
    conn.close()

    assert "storage_location" in cols
    assert "idx_material_storage_location" in indexes
    assert row == ("OLD-1", "active", None)

    # Idempotent second run
    wms.ensure_material_status_column(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols2 = [r[1] for r in conn.execute("PRAGMA table_info(material)")]
    conn.close()
    assert cols2.count("storage_location") == 1


def test_frontend_material_forms_and_js_syntax(client):
    """Add/edit forms expose optional storage_location inputs with labels, and JS parses cleanly."""
    mat_html = client.get("/material").get_data(as_text=True)
    add_html = client.get("/material/add").get_data(as_text=True)
    for html, input_id in (
        (mat_html, "add_storage_location"),
        (mat_html, "edit_storage_location"),
        (add_html, "material-add-storage_location"),
    ):
        assert f'for="{input_id}"' in html
        m = re.search(rf'<input[^>]*id="{re.escape(input_id)}"[^>]*>', html)
        assert m, f"Missing input #{input_id}"
        assert "required" not in m.group(0), f"#{input_id} must be optional"

    for js_rel in ("app/static/js/pages/material-list.js", "app/static/js/material_merge.js"):
        res = subprocess.run(
            [shutil.which("node"), "--check", str(ROOT / js_rel)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
        )
        assert res.returncode == 0, res.stderr
