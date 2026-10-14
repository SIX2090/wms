"""No conversion is implied by a different line unit."""
import io
import pytest
from openpyxl import Workbook
import app as w
from tests.test_flow_source_limits import flow_case
from services.stock_unit_guard import require_stock_unit


@pytest.fixture
def unit_case(flow_case):
    client, ids = flow_case
    with w.app.app_context():
        bom = w.BOM(bom_no='B1', product_code='P1', product_name='产品', version='V1', status='active')
        req = w.ProductionRequisition(req_no='R1', warehouse='审计仓A', status='pending')
        w.db.session.add_all([bom, req])
        w.db.session.flush()
        bi = w.BOMItem(bom_id=bom.id, material_id=ids['mat'], quantity=2, unit_id=ids['each'], unit_cost=5, total_cost=10)
        ri = w.ProductionRequisitionItem(requisition_id=req.id, material_id=ids['mat'], quantity=2, unit_id=ids['each'])
        w.db.session.add_all([bi, ri])
        w.db.session.commit()
        ids.update(bom=bom.id, bi=bi.id, req=req.id, ri=ri.id)
    return client, ids


def test_require_stock_unit(unit_case):
    _, ids = unit_case
    with w.app.app_context():
        material = w.db.session.get(w.Material, ids['mat'])
        assert require_stock_unit(material) == ids['each']
        with pytest.raises(ValueError, match='库存单位'):
            require_stock_unit(material, ids['box'])


def test_box_as_material_stock_unit_is_valid(unit_case):
    client, ids = unit_case
    with w.app.app_context():
        w.db.session.get(w.Material, ids['mat']).unit_id = ids['box']
        w.db.session.get(w.BOMItem, ids['bi']).unit_id = ids['box']
        w.db.session.commit()
    generated = client.post(f"/bom/{ids['bom']}/create_requisition", json=dict(warehouse_id=ids['wh'])).get_json()
    assert generated['status'] == 'success'
    assert client.post(f"/requisition/{generated['id']}/complete").get_json()['status'] == 'success'
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['mat']).stock == 98
        assert w.db.session.get(w.ProductionRequisition, generated['id']).items[0].unit_id == ids['box']


def test_bom_save_rejects_alternate_stock_unit(unit_case):
    client, ids = unit_case
    body = dict(order_id=ids['bom'], order_no='B1', header=dict(product_code='P1', product_name='产品', version='V1', status='active'),
                items=[dict(code='M1', quantity=2, unit_id=ids['box'], price=5)])
    response = client.post('/bom/save_table', json=body)
    assert response.get_json()['status'] == 'error'
    assert '单位' in response.get_json()['msg']
    with w.app.app_context():
        assert w.db.session.get(w.BOMItem, ids['bi']).unit_id == ids['each']


@pytest.mark.parametrize('kind', ['bom', 'requisition'])
def test_legacy_add_rejects_alternate_stock_unit(unit_case, kind):
    client, ids = unit_case
    response = client.post(f"/{kind}/{ids['bom'] if kind == 'bom' else ids['req']}/add_item" if kind == 'bom'
                           else f"/requisition/{ids['req']}/item/add",
                           data=dict(material_code='M1', quantity=2, unit_id=ids['box']))
    assert response.get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.BOMItem.query.count() == 1
        assert w.ProductionRequisitionItem.query.count() == 1


def test_bom_generation_rejects_legacy_mixed_unit(unit_case):
    client, ids = unit_case
    with w.app.app_context():
        w.db.session.get(w.BOMItem, ids['bi']).unit_id = ids['box']
        w.db.session.commit()
    assert client.post(f"/bom/{ids['bom']}/create_requisition", json=dict(warehouse_id=ids['wh'])).get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.ProductionRequisition.query.count() == 1
        assert w.db.session.get(w.Material, ids['mat']).stock == 100


def test_cost_rejects_legacy_mixed_unit(unit_case):
    _, ids = unit_case
    with w.app.app_context():
        row = w.db.session.get(w.BOMItem, ids['bi'])
        row.unit_id = ids['box']
        w.db.session.commit()
        with pytest.raises(ValueError, match='库存单位'):
            w.calculate_bom_cost_value(w.db.session.get(w.BOM, ids['bom']))
        assert row.total_cost == 10


def test_requisition_save_rejects_alternate_stock_unit(unit_case):
    client, ids = unit_case
    body = dict(order_id=ids['req'], order_no='R1', header=dict(warehouse='审计仓A'),
                items=[dict(code='M1', quantity=2, unit_id=ids['box'])])
    response = client.post('/requisition/save_table', json=body)
    assert response.get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.db.session.get(w.ProductionRequisition, ids['req']).items[0].unit_id == ids['each']


def test_requisition_inline_update_rejects_legacy_mixed_unit(unit_case):
    client, ids = unit_case
    with w.app.app_context():
        w.db.session.get(w.ProductionRequisitionItem, ids['ri']).unit_id = ids['box']
        w.db.session.commit()
    response = client.post(f"/requisition/{ids['req']}/item/{ids['ri']}/update", data={'quantity':3})
    assert response.get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.db.session.get(w.ProductionRequisitionItem, ids['ri']).quantity == 2


@pytest.mark.parametrize('unit_key,allowed', [('box', False), ('each', True), (None, True)])
def test_requisition_complete_unit_boundary(unit_case, unit_key, allowed):
    client, ids = unit_case
    with w.app.app_context():
        w.db.session.get(w.ProductionRequisitionItem, ids['ri']).unit_id = ids[unit_key] if unit_key else None
        w.db.session.commit()
        before = w.StockTransaction.query.count()
    response = client.post(f"/requisition/{ids['req']}/complete").get_json()
    assert (response['status'] == 'success') is allowed
    with w.app.app_context():
        assert w.db.session.get(w.Material, ids['mat']).stock == (98 if allowed else 100)
        assert w.db.session.get(w.ProductionRequisition, ids['req']).status == ('completed' if allowed else 'pending')
        if not allowed:
            assert w.StockTransaction.query.count() == before
        stocks = w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse, ids['other']))
        assert stocks.get(ids['mat'], 0) == 0


def test_bom_import_rejects_existing_material_mixed_unit(unit_case):
    client, ids = unit_case
    book = Workbook()
    book.active.append(['产品编码','产品名称','版本','物料编码','物料名称','规格','单位','数量'])
    book.active.append(['P2','另一产品','V1','M1','审计物料','','箱',2])
    buffer = io.BytesIO()
    book.save(buffer)
    buffer.seek(0)
    response = client.post('/bom/import', data={'file':(buffer,'mixed.xlsx')}, content_type='multipart/form-data')
    assert response.get_json()['status'] == 'error'
    with w.app.app_context():
        assert w.BOM.query.count() == 1
        assert w.BOMItem.query.count() == 1
