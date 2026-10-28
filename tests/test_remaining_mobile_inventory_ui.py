"""Remaining browser findings: scoped facts, read-only actions, and mobile modes."""
import shutil
import subprocess
from pathlib import Path

import pytest
import app as wms
from tests.test_bug_2026_09_13_002_warehouse_deductions import scene, _stock
from tests.test_toolbar_semantic_dedupe import _render_toolbar

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['requisition', 'transfer'])
@pytest.mark.parametrize('legacy', [False, True])
def test_saved_document_rows_use_warehouse_facts(scene, monkeypatch, kind, legacy):
    client, source, other, material=scene
    _stock(material, source, 7, legacy=legacy)
    warehouse=source.code if legacy else source.name
    if kind=='requisition':
        order=wms.ProductionRequisition(req_no='REQ-SCOPE', warehouse=warehouse, status='completed')
        wms.db.session.add(order); wms.db.session.flush()
        wms.db.session.add(wms.ProductionRequisitionItem(requisition_id=order.id,material_id=material.id,quantity=1))
        renderer=wms._render_requisition_form
    else:
        order=wms.TransferOrder(transfer_no='TR-SCOPE',from_location=warehouse,to_location=other.name,status='completed')
        wms.db.session.add(order); wms.db.session.flush()
        wms.db.session.add(wms.TransferOrderItem(transfer_order_id=order.id,material_id=material.id,quantity=1))
        renderer=wms._render_transfer_form
    wms.db.session.commit()
    monkeypatch.setattr(wms, 'render_template', lambda name, **data:data)
    with wms.app.test_request_context():
        data=renderer(order)
    assert data['existing_items'][0]['stock']==7
    assert material.stock==107
    assert wms.get_warehouse_stock_quantities(other)[material.id]==100


@pytest.mark.parametrize('warehouse,expected', [('WA',7),('WB',100)])
def test_stock_lookup_requires_valid_warehouse_and_keeps_legacy_material_metadata(scene, warehouse, expected):
    client,source,other,material=scene
    _stock(material,source,7,legacy=True)
    response=client.get('/mobile/api/stock_lookup',query_string={'code':material.code,'warehouse':warehouse})
    assert response.status_code==200
    assert response.json['data']['stock']==expected
    for bad in ['', 'missing']:
        response=client.get('/mobile/api/stock_lookup',query_string={'code':material.code,'warehouse':bad})
        assert response.status_code==400
        assert response.json['success'] is False
    # General material metadata lookup is still used by existing non-stock pickers.
    assert client.get('/mobile/api/material_lookup',query_string={'code':material.code}).json['data']['stock']==107


def test_query_submit_rejects_missing_or_invalid_warehouse(scene):
    client,source,other,material=scene
    for warehouse in ['', 'missing']:
        response=client.post('/mobile/api/scan_submit',json={'mode':'query','code':material.code,'warehouse':warehouse})
        assert response.status_code==400
    assert client.post('/mobile/api/scan_submit',json={'mode':'query','code':material.code,'warehouse':other.code}).json['data']['material']['stock']==100


def test_mobile_query_has_visible_required_default_warehouse(scene):
    client,source,other,material=scene
    from bs4 import BeautifulSoup
    html=BeautifulSoup(client.get('/mobile/scan?mode=query&embedded=1').data,'html.parser')
    field=html.select_one('#warehouseInput')
    assert field.has_attr('required') and field['value']==source.name
    assert 'd-none' not in field.parent.get('class',[])


@pytest.mark.parametrize('path', ['/requisition/1','/transfer/1','/check/1'])
def test_common_readonly_form_has_no_global_save(path):
    labels=_render_toolbar([],path=path,isList=False,isForm=True,readonlyForm=True)
    assert '保存' not in labels
    assert '新增' in labels


@pytest.mark.parametrize('scenario',['confirm-init','confirm-loading','confirm-switch','more-switch','lookup-race','warehouse-change','query-submit-switch','recognize-match'])
def test_real_mobile_runtime(scenario):
    node=shutil.which('node')
    if not node: pytest.skip('Node.js required')
    result=subprocess.run([node,str(ROOT/'tests/frontend_remaining_mobile_ui.cjs'),scenario],capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_scoped_lookup_when_location_management_is_enabled(scene):
    client,source,other,material=scene
    wms.set_system_setting('location_management_enabled','1')
    wms.db.session.add_all([
        wms.LocationInventory(material_id=material.id,warehouse_id=source.id,location='A-01',quantity=7),
        wms.LocationInventory(material_id=material.id,warehouse_id=other.id,location='B-01',quantity=100),
    ])
    wms.db.session.commit()
    for warehouse,quantity,location in [(source,7,'A-01'),(other,100,'B-01')]:
        response=client.get('/mobile/api/stock_lookup',query_string={'code':material.code,'warehouse':warehouse.code})
        assert response.status_code==200
        assert response.json['data']['stock']==quantity
        assert [x['location'] for x in response.json['data']['locations']]==[location]


def test_transfer_display_prefers_warehouse_over_bin(scene,monkeypatch):
    client,source,other,material=scene
    _stock(material,source,7)
    order=wms.TransferOrder(transfer_no='TR-BIN',from_warehouse=source.name,from_location='A-01',to_warehouse=other.name,to_location='B-01',status='completed')
    wms.db.session.add(order);wms.db.session.flush()
    wms.db.session.add(wms.TransferOrderItem(transfer_order_id=order.id,material_id=material.id,quantity=1))
    wms.db.session.commit()
    monkeypatch.setattr(wms,'render_template',lambda name,**data:data)
    with wms.app.test_request_context():
        data=wms._render_transfer_form(order)
    assert data['existing_items'][0]['stock']==7
