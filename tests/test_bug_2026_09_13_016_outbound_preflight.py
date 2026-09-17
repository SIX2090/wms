import pytest

import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene, _stock


def _order(warehouse, material, quantities, number="OUT016"):
    order = wms.OutOrder(order_no=number, warehouse=warehouse, status="pending",
                         business_type="领料单")
    wms.db.session.add(order)
    wms.db.session.flush()
    for quantity in quantities:
        wms.db.session.add(wms.OutOrderItem(out_order_id=order.id,
            material_id=material.id, quantity=quantity, price=1, amount=quantity))
    wms.db.session.commit()
    return order


def test_batch_inactive_warehouse_rejected(scene):
    client, source, other, material = scene
    other.status = "inactive"
    order = _order(other.name, material, [1])
    result = client.post('/out_order/batch_complete', json={"ids": [order.id]}).get_json()
    assert result["completed"] == 0, result
    wms.db.session.expire_all()
    assert order.status == "pending"
    assert material.stock == 100


def test_missing_material_does_not_abort_remaining_batch(scene):
    client, source, other, material = scene
    broken = _order(other.name, material, [1], "OUT016-BAD")
    good = _order(other.name, material, [2], "OUT016-GOOD")
    broken_id, good_id, material_id = broken.id, good.id, material.id
    wms.db.session.remove()
    with wms.db.engine.connect() as connection:
        # 污染治理（AI-CI-GREEN-001）：PRAGMA foreign_keys 是连接级状态，
        # 内存库场景引擎为 StaticPool 单连接——测试期改动的值会泄漏给同进程
        # 后续所有测试（本测试原先 finally 硬编码 =ON，把基线 OFF 翻成 ON，
        # 导致 TestOpeningStock* 家族 _wipe 删 user 时被 login_log 外键卡死）。
        # 正确做法：先记录原值，finally 恢复原值。
        original_fk = connection.exec_driver_sql('PRAGMA foreign_keys').fetchone()[0]
        connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
        try:
            connection.exec_driver_sql('UPDATE out_order_item SET material_id=? WHERE out_order_id=?',
                                       (999999, broken_id))
            connection.commit()
        finally:
            connection.exec_driver_sql(
                'PRAGMA foreign_keys=' + ('ON' if original_fk else 'OFF'))
    result = client.post('/out_order/batch_complete', json={"ids": [broken_id, good_id]}).get_json()
    assert result["completed"] == 1, result
    assert "物料不存在" in result["msg"]
    assert wms.db.session.get(wms.OutOrder, broken_id).status == "pending"
    assert wms.db.session.get(wms.OutOrder, good_id).status == "completed"
    assert wms.db.session.get(wms.Material, material_id).stock == 98


@pytest.mark.parametrize("entry", ["single", "batch"])
def test_atomic_failure_rolls_back_entire_document(scene, monkeypatch, entry):
    client, source, other, material = scene
    order = _order(other.name, material, [1, 2])
    calls = []
    original = wms.deduct_stock_atomic

    def fail_second(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            return False, "test deduction failure", None
        return original(*args, **kwargs)

    monkeypatch.setattr(wms, "deduct_stock_atomic", fail_second)
    if entry == "single":
        result = client.post(f'/out_order/{order.id}/complete?force=true').get_json()
        assert result["status"] == "error"
    else:
        result = client.post('/out_order/batch_complete', json={"ids": [order.id]}).get_json()
        assert result["completed"] == 0
    wms.db.session.expire_all()
    assert order.status == "pending"
    assert material.stock == 100
    assert wms.StockTransaction.query.count() == 1
    assert wms.StockTransaction.query.count() == 1


@pytest.mark.parametrize("entry", ["single", "batch"])
def test_cumulative_demand_rejected_before_any_deduction(scene, monkeypatch, entry):
    client, source, other, material = scene
    _stock(material, source, 10, legacy=True)
    order = _order(source.code, material, [6, 6])
    calls = []
    original = wms.deduct_stock_atomic

    def record(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(wms, "deduct_stock_atomic", record)
    if entry == "single":
        result = client.post(f'/out_order/{order.id}/complete?force=true').get_json()
        assert result["status"] == "error"
    else:
        result = client.post('/out_order/batch_complete', json={"ids": [order.id]}).get_json()
        assert result["completed"] == 0
    assert not calls
    assert wms.get_warehouse_stock_quantities(source)[material.id] == 10
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == 110
    assert order.status == "pending"


@pytest.mark.parametrize("entry", ["single", "batch"])
def test_legacy_source_stock_success_and_no_repeat_completion(scene, entry):
    client, source, other, material = scene
    _stock(material, source, 10, legacy=True)
    order = _order(source.code, material, [4, 6])
    for attempt in range(2):
        if entry == "single":
            result = client.post(f'/out_order/{order.id}/complete?force=true').get_json()
            assert result["status"] == ("success" if attempt == 0 else "error"), result
        else:
            result = client.post('/out_order/batch_complete', json={"ids": [order.id]}).get_json()
            assert result["completed"] == (1 if attempt == 0 else 0), result
    wms.db.session.expire_all()
    assert order.status == "completed"
    assert wms.get_warehouse_stock_quantities(source).get(material.id, 0) == 0
    assert wms.get_warehouse_stock_quantities(other)[material.id] == 100
    assert material.stock == 100
