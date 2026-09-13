import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene


@pytest.mark.parametrize("actuals, expected", [
    ((100, 2), 2), ((100, 0), 0), ((30, 68), -2), ((100,), 0), ((0, 0), -100),
])
def test_check_area_totals_include_zero_difference_rows(scene, actuals, expected):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no="CK-TOTAL", warehouse=other.name, status="pending")
    wms.db.session.add(check)
    wms.db.session.flush()
    for index, actual in enumerate(actuals):
        wms.db.session.add(wms.InventoryCheckItem(
            inventory_check_id=check.id, material_id=material.id, system_stock=100,
            actual_stock=actual, difference=actual - 100, area=f"Zone {index}"))
    wms.db.session.commit()
    result = client.post(f"/check/{check.id}/complete", json={"force": True}).get_json()
    assert result["status"] == "success", result
    adjustments = wms.AdjustmentOrder.query.filter_by(source_type="check", source_id=check.id).all()
    assert sum(row.quantity for order in adjustments for row in order.items) == expected
    assert len(adjustments) == (1 if expected else 0)
    assert all(order.status == "pending" and order.warehouse == other.name for order in adjustments)
    assert wms.StockTransaction.query.count() == 1
    assert material.stock == 100


def test_zero_difference_area_still_participates_in_location_guard(scene):
    client, source, other, material = scene
    wms.set_system_setting("location_management_enabled", "1")
    check = wms.InventoryCheck(check_no="CK-LOCATION", warehouse=other.name, status="pending")
    wms.db.session.add(check)
    wms.db.session.flush()
    for area, actual in (("Location 1", 100), ("Location 2", 2)):
        wms.db.session.add(wms.InventoryCheckItem(
            inventory_check_id=check.id, material_id=material.id, system_stock=100,
            actual_stock=actual, difference=actual - 100, area=area))
    wms.db.session.commit()
    result = client.post(f"/check/{check.id}/complete", json={"force": True}).get_json()
    assert result["status"] == "error", result
    assert wms.AdjustmentOrder.query.count() == 0
    wms.db.session.expire_all()
    assert check.status == "pending"
