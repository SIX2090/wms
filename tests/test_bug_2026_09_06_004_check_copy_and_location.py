from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_ROUTE = (ROOT / "app" / "routes" / "check.py").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app" / "app.py").read_text(encoding="utf-8")

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

def test_check_adjustment_has_location_guard():
    body = _body(APP_SOURCE, "def _create_adjustment_drafts_from_check(check):", "def _create_adjustment_drafts_from_check_scan(check):")
    assert "missing_locations" in body
    assert "split_locations" in body
    assert "location=(item.area or '').strip() or None" in body
