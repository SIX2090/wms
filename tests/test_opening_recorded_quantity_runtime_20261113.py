"""Actual five opening removal routes; only verified isolated memory runtime."""
from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

import pytest  # noqa: E402
import app as w  # noqa: E402
from tests.test_opening_reference_ownership_runtime_20261113 import (  # noqa: E402,F401
    source_scene, _remove, _seed, _state)


def _historical_scene(scene, location_on, quantity):
    case = _seed(scene, location_on, legacy=False)
    _client, _a, b = scene
    line = w.db.session.get(w.OpeningStock, case['line_id'])
    original = w.StockTransaction.query.filter_by(material_id=case['material_id'],
        reference_type='opening_stock',reference_id=case['line_id']).one()
    # The HTTP producer still accepts ordinary two-decimal inputs. Only this
    # proven fresh-memory fixture represents a row stored by an older producer.
    line.quantity = quantity
    original.quantity = quantity
    material = w.db.session.get(w.Material,case['material_id'])
    material.stock = 25 + quantity
    other = w.StockTransaction(material_id=material.id,warehouse_id=b.id,location=b.name,
        quantity=20,transaction_type='opening',reference_type='material_initial',
        reference_id=material.id,remark='合成另一仓初始库存')
    w.db.session.add(other)
    if location_on:
        position = w.LocationInventory.query.filter_by(material_id=material.id,
            warehouse_id=case['warehouse_id']).one()
        position.quantity = 5 + quantity
        w.db.session.add(w.LocationInventory(material_id=material.id,warehouse_id=b.id,
            location=case['location'],quantity=20))
    w.db.session.commit()
    case['other_id'],case['other_warehouse_id']=other.id,b.id
    return case


@pytest.mark.parametrize('quantity',[1.005,1.01])
@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_removal_paths_reverse_recorded_quantity_exactly(source_scene,mode,location_on,quantity):
    case = _historical_scene(source_scene,location_on,quantity)
    response = _remove(case,mode)
    assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
    material = w.db.session.get(w.Material,case['material_id'])
    assert material.stock==pytest.approx(25,abs=1e-12,rel=0)
    assert w.db.session.get(w.OpeningStock,case['line_id']) is None
    assert w.StockTransaction.query.filter_by(material_id=material.id,
        reference_type='opening_stock',reference_id=case['line_id']).count()==0
    initial=w.db.session.get(w.StockTransaction,case['initial_id'])
    other=w.db.session.get(w.StockTransaction,case['other_id'])
    assert (initial.quantity,initial.reference_type)==(5,'material_initial')
    assert (other.quantity,other.warehouse_id)==(20,case['other_warehouse_id'])
    if location_on:
        positions = {row.warehouse_id:row.quantity for row in
                     w.LocationInventory.query.filter_by(material_id=material.id)}
        assert positions[case['warehouse_id']]==pytest.approx(5,abs=1e-12,rel=0)
        assert positions[case['other_warehouse_id']]==20


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_paths_refuse_mismatching_original_net_and_rollback(source_scene,mode,location_on):
    case = _historical_scene(source_scene,location_on,1.005)
    original = w.StockTransaction.query.filter_by(material_id=case['material_id'],
        reference_type='opening_stock',reference_id=case['line_id']).one()
    original.quantity=1.01
    w.db.session.get(w.Material,case['material_id']).stock=26.01
    if location_on:
        w.LocationInventory.query.filter_by(material_id=case['material_id'],
            warehouse_id=case['warehouse_id']).one().quantity=6.01
    w.db.session.commit()
    before = _state()
    response = _remove(case,mode)
    assert response.status_code==400 and response.get_json()['status']=='error',response.get_json()
    assert '净额不一致' in response.get_json()['msg']
    assert _state()==before


@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_paths_refuse_missing_original_position_and_rollback(source_scene,mode):
    case = _historical_scene(source_scene,True,1.005)
    line=w.db.session.get(w.OpeningStock,case['line_id'])
    original=w.StockTransaction.query.filter_by(material_id=case['material_id'],
        reference_type='opening_stock',reference_id=case['line_id']).one()
    line.location=''
    original.location=None
    w.db.session.commit()
    before=_state()
    response=_remove(case,mode)
    assert response.status_code==400 and response.get_json()['status']=='error',response.get_json()
    assert '原库位缺失' in response.get_json()['msg']
    assert _state()==before


@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_paths_refuse_existing_point_zero_zero_five_location_difference(source_scene,mode):
    case = _historical_scene(source_scene,True,1.005)
    w.LocationInventory.query.filter_by(material_id=case['material_id'],
        warehouse_id=case['warehouse_id']).one().quantity=6.01
    w.db.session.commit()
    before=_state()
    response=_remove(case,mode)
    assert response.status_code==400 and response.get_json()['status']=='error',response.get_json()
    assert '库位账与总账或原仓流水不一致' in response.get_json()['msg']
    assert _state()==before
