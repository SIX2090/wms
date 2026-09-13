import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene, _stock


def _check(warehouse):
    check = wms.InventoryCheck(check_no="CK017", warehouse=warehouse, status="pending")
    wms.db.session.add(check)
    wms.db.session.commit()
    return check


@pytest.mark.parametrize("warehouse", ["missing", "inactive", "empty_without_default"])
def test_invalid_warehouse_never_uses_global_stock(scene, warehouse):
    client, source, other, material = scene
    if warehouse == "inactive":
        other.status = "inactive"
        warehouse = other.name
    elif warehouse == "empty_without_default":
        source.is_default = False
        warehouse = ""
    check = _check(warehouse)
    result = client.post(f'/check/{check.id}/add_item', data={"material_id": material.id}).get_json()
    assert result["status"] == "error", result
    assert wms.InventoryCheckItem.query.count() == 0
    assert material.stock == 100


@pytest.mark.parametrize("warehouse", ["default", "code"])
def test_add_freezes_warehouse_stock_and_preserves_area(scene, warehouse):
    client, source, other, material = scene
    _stock(material, source, 7, legacy=True)
    check = _check("" if warehouse == "default" else source.code)
    result = client.post(f'/check/{check.id}/add_item', data={
        "material_id": material.id, "area": "Zone A"}).get_json()
    assert result["status"] == "success", result
    item = wms.InventoryCheckItem.query.one()
    assert item.system_stock == item.actual_stock == 7
    assert item.area == "Zone A"
    assert check.frozen_at is not None
    frozen = check.frozen_at
    duplicate = client.post(f'/check/{check.id}/add_item', data={
        "material_id": material.id, "area": "Zone A"}).get_json()
    assert duplicate["status"] == "error"
    other_area = client.post(f'/check/{check.id}/add_item', data={
        "material_id": material.id, "area": "Zone B"}).get_json()
    assert other_area["status"] == "success", other_area
    assert check.frozen_at == frozen
    assert material.stock == 107
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert wms.StockTransaction.query.count() == 2


def test_location_enabled_requires_area(scene):
    client, source, other, material = scene
    wms.set_system_setting("location_management_enabled", "1")
    check = _check(other.name)
    result = client.post(f'/check/{check.id}/add_item', data={"material_id": material.id}).get_json()
    assert result["status"] == "error", result
    assert wms.InventoryCheckItem.query.count() == 0


def test_rechecks_status_under_write_lock(scene, monkeypatch):
    client, source, other, material = scene
    check = _check(other.name)
    calls = []

    def denied(*args, **kwargs):
        calls.append(args)
        return None, False

    monkeypatch.setattr(wms, "_acquire_order_write_lock", denied)
    result = client.post(f'/check/{check.id}/add_item', data={"material_id": material.id}).get_json()
    assert result["status"] == "error", result
    assert calls
    assert wms.InventoryCheckItem.query.count() == 0


def test_legacy_frozen_empty_warehouse_is_not_reassigned(scene):
    client, source, other, material = scene
    check = _check("")
    wms.db.session.add(wms.InventoryCheckItem(inventory_check_id=check.id,
        material_id=material.id, area="Zone A", system_stock=100, actual_stock=100, difference=0))
    wms.db.session.commit()
    result = client.post(f'/check/{check.id}/add_item', data={
        "material_id": material.id, "area": "Zone B"}).get_json()
    assert result["status"] == "error"
    assert check.warehouse == ""
    assert wms.InventoryCheckItem.query.count() == 1
    assert wms.InventoryCheckItem.query.one().system_stock == 100


def test_location_area_saved_with_warehouse_balance(scene):
    client, source, other, material = scene
    wms.set_system_setting("location_management_enabled", "1")
    wms.db.session.add(wms.LocationInventory(material_id=material.id,
        warehouse_id=other.id, location="Zone A", quantity=100))
    check = _check(other.name)
    result = client.post(f'/check/{check.id}/add_item', data={
        "material_id": material.id, "location": "Zone A"}).get_json()
    assert result["status"] == "success", result
    item = wms.InventoryCheckItem.query.one()
    assert item.area == "Zone A"
    assert item.system_stock == item.actual_stock == 100
    assert material.stock == 100
