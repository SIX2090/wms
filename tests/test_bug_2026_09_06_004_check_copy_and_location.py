from pathlib import Path
import pytest
import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene

ROOT = Path(__file__).resolve().parent.parent
CHECK_ROUTE = (ROOT / "app" / "routes" / "check.py").read_text(encoding="utf-8")

def _body(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]

def test_copy_check_is_fresh_same_warehouse():
    body = _body(CHECK_ROUTE, "def copy_check(id):", "    # pydantic:reason=")
    assert "validate_inventory_warehouse(warehouse)" in body
    assert "warehouse=warehouse_obj.name" in body
    assert "get_warehouse_stock_quantities(warehouse_obj)" in body
    assert "actual_stock=system_stock" in body
    assert "difference=0" in body
    assert "counted_by" not in body and "counted_at" not in body
    assert "frozen_at = datetime.now()" in body

@pytest.mark.parametrize("areas, expected", [([""], "必须填写"), (["A", "B"], "跨多个区域"), (["A"], None)])
def test_check_adjustment_has_location_guard(scene, areas, expected):
    _, _, warehouse, material = scene
    wms.set_system_setting("location_management_enabled", "1")
    check = wms.InventoryCheck(check_no="CK-LOCATION-GUARD", warehouse=warehouse.name, status="pending")
    wms.db.session.add(check)
    for area in areas:
        wms.db.session.add(wms.InventoryCheckItem(inventory_check=check, material_id=material.id,
            system_stock=100, actual_stock=30, difference=-70, area=area))
    wms.db.session.commit()
    with wms.app.test_request_context():
        drafts, error = wms._create_adjustment_drafts_from_check(check)
        if expected:
            assert expected in error and drafts is None
            assert wms.AdjustmentOrder.query.count() == 0
        else:
            assert error is None and len(drafts) == 1
            assert [(row.location, row.quantity) for row in drafts[0].items] == [("A", -70)]
