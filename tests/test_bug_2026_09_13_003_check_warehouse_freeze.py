from datetime import datetime

import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene


@pytest.mark.parametrize("same_warehouse", [False, True])
def test_frozen_check_keeps_warehouse_identity(scene, same_warehouse):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no="CK-FREEZE", warehouse=source.name,
                               status="pending", frozen_at=datetime.now())
    wms.db.session.add(check)
    wms.db.session.flush()
    row = wms.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
                                 system_stock=60, actual_stock=58, difference=-2)
    wms.db.session.add(row)
    wms.db.session.commit()
    result = client.post("/check/save_table", json={
        "order_id": check.id, "order_no": check.check_no,
        "header": {"warehouse": source.code if same_warehouse else other.name},
        "items": [{"material_id": material.id, "actual_stock": 18}],
    }).get_json()
    assert result["status"] == ("success" if same_warehouse else "error"), result
    wms.db.session.expire_all()
    assert check.warehouse == source.name
    assert row.system_stock == 60
    assert row.actual_stock == (18 if same_warehouse else 58)
    assert row.difference == (-42 if same_warehouse else -2)


def test_empty_check_can_choose_another_warehouse(scene):
    client, source, other, material = scene
    check = wms.InventoryCheck(check_no="CK-EMPTY", warehouse=source.name, status="pending")
    wms.db.session.add(check)
    wms.db.session.commit()
    result = client.post("/check/save_table", json={
        "order_id": check.id, "order_no": check.check_no,
        "header": {"warehouse": other.name},
        "items": [{"material_id": material.id, "actual_stock": 98}],
    }).get_json()
    assert result["status"] == "success", result
    wms.db.session.expire_all()
    assert check.warehouse == other.name
    assert check.items[0].system_stock == 100
    assert check.items[0].difference == -2
