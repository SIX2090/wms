import pytest

import app as wms
from scripts.verify_inventory_identity import (
    build_identity_rows, build_warehouse_rows, find_mismatches, find_warehouse_mismatches,
)
from services.warehouse_stock_service import (
    find_location_ledger_mismatches, inventory_reconciliation_summary, verify_material_three_ledgers,
)
from tests.test_document_create_number_conflicts import case, rows


def seed(ids, stock, warehouse_movements, bins=()):
    wms.StockTransaction.query.delete()
    for material in wms.Material.query.all():
        material.stock = stock if material.id == ids['mats'][0] else 0
    wms.db.session.add_all([
        wms.StockTransaction(material_id=ids['mats'][0], transaction_type='in',
                             warehouse_id=warehouse, quantity=quantity)
        for warehouse, quantity in warehouse_movements
    ])
    wms.db.session.add_all([
        wms.LocationInventory(material_id=ids['mats'][0], warehouse_id=warehouse,
                              location='SYNTH-BIN', quantity=quantity)
        for warehouse, quantity in bins
    ])
    wms.db.session.commit()


@pytest.mark.parametrize('difference', [0.01, 0.0001])
def test_global_ledger_reports_small_differences_with_bins_off(case, difference):
    _, ids = case
    with wms.app.app_context():
        mid = ids['mats'][0]
        recorded = 10 - difference
        seed(ids, 10, [(ids['a'], recorded)])
        before = rows(wms.Material), rows(wms.StockTransaction)
        assert not verify_material_three_ledgers(mid)[0]
        title, message = inventory_reconciliation_summary()
        assert '发现差异' in title and '总账与流水差异 1' in message
        assert f'总账 10.0000 / 流水 {recorded:.4f}' in message
        assert '库位核对关闭' in message
        assert (rows(wms.Material), rows(wms.StockTransaction)) == before

    cli = find_mismatches(build_identity_rows([(mid, 'TEST', 10)], [], [(mid, recorded)]))
    assert len(cli) == 1 and cli[0]['delta'] == difference


def test_equal_totals_with_tiny_warehouse_mismatch_block_enabling_bins(case):
    clients, ids = case
    mid, a, b = ids['mats'][0], ids['a'], ids['b']
    with wms.app.app_context():
        seed(ids, 30, [(a, 20), (b, 10)], [(a, 20.0001), (b, 9.9999)])
        findings = find_location_ledger_mismatches(limit=20)
        assert {finding['warehouse_id']: finding['delta'] for finding in findings} == {a: 0.0001, b: -0.0001}
        assert find_location_ledger_mismatches(tolerance=0.01) == []

    response = clients[0].post('/system_settings/save', data={'location_management_enabled': '1'})
    assert response.status_code == 400 and '20.0001' in response.json['msg']
    with wms.app.app_context():
        assert not wms.location_management_enabled()
        wms.set_system_setting('location_management_enabled', '1')
        wms.db.session.commit()
        title, message = inventory_reconciliation_summary()
        assert '发现差异' in title and '仓库分布差异 2' in message
        assert '总账与流水差异 0' in message and '总账与库位差异 0' in message
        assert '流水 20.0000 / 库位 20.0001' in message

    locations, transactions = [(mid, 20.0001, a), (mid, 9.9999, b)], [(mid, 20, a), (mid, 10, b)]
    material_rows = build_identity_rows([(mid, 'TEST', 30)], locations, transactions)
    assert find_mismatches(material_rows) == []
    findings = find_warehouse_mismatches(material_rows, build_warehouse_rows(locations, transactions))
    assert {finding['warehouse_id']: finding['delta'] for finding in findings} == {a: 0.0001, b: -0.0001}


def test_binary_float_residue_does_not_create_inventory_difference(case):
    _, ids = case
    mid, a = ids['mats'][0], ids['a']
    with wms.app.app_context():
        seed(ids, 0.3, [(a, 0.1), (a, 0.2)], [(a, 0.3)])
        wms.set_system_setting('location_management_enabled', '1')
        wms.db.session.commit()
        assert verify_material_three_ledgers(mid)[0]
        assert find_location_ledger_mismatches() == []
        assert '数量相符' in inventory_reconciliation_summary()[0]
    cli_rows = build_identity_rows([(mid, 'TEST', 0.3)], [(mid, 0.3)], [(mid, 0.1), (mid, 0.2)])
    assert find_mismatches(cli_rows) == []
