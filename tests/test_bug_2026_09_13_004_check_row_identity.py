from tests.document_revision_client import document_post
import io

import pytest
from openpyxl import Workbook

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene


def _save(client, warehouse, material, rows, order_id=None):
    return document_post(client,"/check/save_table", json={
        "order_id": order_id, "order_no": "CK-ROWS", "header": {"warehouse": warehouse.name},
        "items": [{"material_id": material.id, **row} for row in rows],
    }).get_json()


def test_duplicate_named_area_rejected_without_partial_save(scene):
    client, source, other, material = scene
    result = _save(client, other, material, [{"actual_stock": 98, "area": "A"}] * 2)
    assert result["status"] == "error", result
    assert wms.InventoryCheck.query.count() == 0
    assert wms.InventoryCheckItem.query.count() == 0


def test_separate_paper_lines_keep_identity_and_subtract_book_once(scene):
    client, _, warehouse, material = scene
    rows = [{"actual_stock": 1} for _ in range(200)]
    rows[0]["actual_stock"] = 40
    rows[-1]["actual_stock"] = 70
    saved = _save(client, warehouse, material, rows)
    assert saved["status"] == "success", saved
    check_id = saved["id"]
    lines = wms.InventoryCheckItem.query.order_by(wms.InventoryCheckItem.id).all()
    assert len(lines) == 200
    kept = [{"line_id": lines[-1].id, "actual_stock": 70}, {"line_id": lines[0].id, "actual_stock": 40}]
    assert _save(client, warehouse, material, kept, check_id)["status"] == "success"
    result = document_post(client, f"/check/{check_id}/complete", json={}).get_json()
    assert result["status"] == "success", result
    adjustment = wms.AdjustmentOrder.query.one()
    assert adjustment.status == "pending" and adjustment.warehouse == warehouse.name
    assert [(item.material_id, item.quantity) for item in adjustment.items] == [(material.id, 10)]
    assert material.stock == 100


def test_blank_and_explicit_zero_remain_distinct_after_save(scene):
    client, _, warehouse, material = scene
    saved = _save(client, warehouse, material, [{"actual_stock": 12}, {"actual_stock": 0}])
    assert saved["status"] == "success", saved
    lines = wms.InventoryCheckItem.query.order_by(wms.InventoryCheckItem.id).all()
    kept = [{"line_id": lines[0].id, "actual_stock": None}, {"line_id": lines[1].id, "actual_stock": 0}]
    assert _save(client, warehouse, material, kept, saved["id"])["status"] == "success"
    wms.db.session.expire_all()
    assert lines[0].counted_at is None and lines[0].actual_stock == lines[0].system_stock
    assert lines[1].counted_at and lines[1].actual_stock == 0
    warning = document_post(client, f"/check/{saved['id']}/complete", json={}).get_json()
    assert warning["status"] == "confirm", warning
    result = document_post(client, f"/check/{saved['id']}/complete", json={
        "force": True, "confirmation_token": warning["confirmation_token"]}).get_json()
    assert result["status"] == "success", result
    assert wms.AdjustmentOrderItem.query.one().quantity == -100


def test_area_rows_roundtrip_and_keep_independent_freezes(scene):
    client, source, other, material = scene
    rows = [{"area": "Zone A", "actual_stock": 30}, {"area": "Zone B", "actual_stock": 68}]
    result = _save(client, other, material, rows)
    assert result["status"] == "success", result
    check_id = result["id"]
    wms.db.session.expire_all()
    check = wms.db.session.get(wms.InventoryCheck, check_id)
    assert {row.area for row in check.items} == {"Zone A", "Zone B"}
    original_ids = {row.area: row.id for row in check.items}
    rows[0]["actual_stock"] = 32
    result = _save(client, other, material, rows, check_id)
    assert result["status"] == "success", result
    wms.db.session.expire_all()
    assert {row.area: row.id for row in check.items} == original_ids
    assert {row.area: row.actual_stock for row in check.items} == {"Zone A": 32, "Zone B": 68}
    assert all(row.system_stock == 100 for row in check.items)
    page = client.get(f"/check/{check_id}").get_data(as_text=True)
    assert 'data-column-key="area"' in page
    assert '"area": "Zone A"' in page
    result = _save(client, other, material, rows[:1], check_id)
    assert result["status"] == "success", result
    wms.db.session.expire_all()
    assert [row.area for row in check.items] == ["Zone A"]


@pytest.mark.parametrize("area", ["", "Location 1"])
def test_location_enabled_check_requires_and_preserves_area(scene, area):
    client, source, other, material = scene
    wms.set_system_setting("location_management_enabled", "1")
    wms.db.session.add(wms.LocationInventory(material_id=material.id, warehouse_id=other.id,
                                             location="Location 1", quantity=100))
    wms.db.session.commit()
    result = _save(client, other, material, [{"area": area, "actual_stock": 98}])
    assert result["status"] == ("success" if area else "error"), result
    if area:
        # 已填写实盘且没有期间流水，不制造不存在的未盘风险。
        completed = document_post(client,f"/check/{result['id']}/complete", json={}).get_json()
        assert completed["status"] == "success", completed
        adjustment = wms.AdjustmentOrder.query.one()
        assert adjustment.status == "pending"
        assert adjustment.items[0].location == area
        assert adjustment.items[0].quantity == -2
        assert material.stock == 100


def test_import_rejects_duplicate_material_area(scene):
    client, source, other, material = scene
    book = Workbook()
    sheet = book.active
    sheet.append(["盘点单号", "仓库", "物料编码", "实际库存", "区域"])
    sheet.append(["CK-IMPORT", other.name, material.code, 30, "Zone A"])
    sheet.append(["CK-IMPORT", other.name, material.code, 30, "Zone A"])
    sheet.append(["CK-IMPORT", other.name, material.code, 68, "Zone B"])
    content = io.BytesIO()
    book.save(content)
    content.seek(0)
    result = document_post(client,"/check/import", data={"file": (content, "checks.xlsx")}).get_json()
    assert result["status"] == "success", result
    rows = wms.InventoryCheckItem.query.all()
    assert len(rows) == 2
    assert {row.area for row in rows} == {"Zone A", "Zone B"}


def test_import_includes_each_unnamed_pallet_and_explicit_zero(scene):
    client, _, warehouse, material = scene
    book = Workbook()
    sheet = book.active
    sheet.append(["盘点单号", "仓库", "物料编码", "实际库存"])
    for qty in (40, 0, 65):
        sheet.append(["CK-PAPER", warehouse.name, material.code, qty])
    content = io.BytesIO()
    book.save(content)
    content.seek(0)
    result = document_post(client, "/check/import", data={"file": (content, "paper.xlsx")}).get_json()
    assert result["status"] == "success", result
    check = wms.InventoryCheck.query.one()
    assert sorted(row.actual_stock for row in check.items if row.counted_at) == [0, 40, 65]
    result = document_post(client, f"/check/{check.id}/complete", json={}).get_json()
    if result["status"] == "confirm":
        result = document_post(client, f"/check/{check.id}/complete", json={
            "force": True, "confirmation_token": result["confirmation_token"]}).get_json()
    assert result["status"] == "success", result
    assert wms.AdjustmentOrderItem.query.one().quantity == 5
