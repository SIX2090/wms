from datetime import date
from pathlib import Path
import json
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def selection_case(monkeypatch):
    import app as w
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    with w.app.app_context():
        assert str(w.db.engine.url)=='sqlite:///:memory:'
        w.db.drop_all();w.db.create_all()
        user=w.User(username='selection-fixture',password_hash='fixture-only',role='warehouse',status='active')
        suppliers=[w.Supplier(code='S1',name='普通供应商'),w.Supplier(code='S2',name='FIND供应商')]
        materials=[w.Material(code='M1',name='普通物料',spec='BASE'),w.Material(code='M2',name='独有目标物料',spec='SPEC-FIND',brand='品牌B')]
        w.db.session.add_all([user,*suppliers,*materials]);w.db.session.flush()
        orders=[w.PurchaseOrder(order_no='PO-BASE',supplier_id=suppliers[0].id,date=date(2026,1,1),status='pending'),
                w.PurchaseOrder(order_no='PO-FIND',supplier_id=suppliers[1].id,date=date(2026,1,2),status='pending')]
        w.db.session.add_all(orders);w.db.session.flush()
        items=[w.PurchaseOrderItem(purchase_order_id=o.id,material_id=m.id,quantity=10,received_quantity=0,price=0)
               for o,m in zip(orders,materials)]
        w.db.session.add_all(items);w.db.session.commit()
        ids=dict(orders=[o.id for o in orders],items=[i.id for i in items],suppliers=[s.id for s in suppliers],materials=[m.id for m in materials])
        client=w.app.test_client()
        with client.session_transaction() as session:session.update(_user_id=str(user.id),_fresh=True)
        yield w,client,ids
        w.db.session.remove();w.db.drop_all()


@pytest.mark.parametrize('search',['PO-FIND','FIND供应商','M2','独有目标','SPEC-FIND','品牌B'])
def test_search_precedes_candidate_limit(selection_case,search):
    _,client,ids=selection_case
    data=client.get('/api/purchase_order/selectable',query_string={'limit':1,'search':search}).get_json()
    assert [item['purchase_order_id'] for item in data['items']]==[ids['orders'][1]]
    assert data['total']==1 and data['total_pages']==1
    assert data['items'][0]['price']==0
    assert data['items'][0]['brand']=='品牌B'


def test_pagination_metadata_and_page_two(selection_case):
    _,client,ids=selection_case
    first=client.get('/api/purchase_order/selectable?limit=1&page=1').get_json()
    second=client.get('/api/purchase_order/selectable?limit=1&page=2').get_json()
    assert [o['id'] for o in first['orders']]==[ids['orders'][0]]
    assert [o['id'] for o in second['orders']]==[ids['orders'][1]]
    assert {key:second[key] for key in ['total','page','page_size','total_pages']}==dict(total=2,page=2,page_size=1,total_pages=2)


def test_fully_received_pending_orders_do_not_consume_page(selection_case):
    w,client,ids=selection_case
    w.db.session.get(w.PurchaseOrderItem,ids['items'][0]).received_quantity=10
    w.db.session.commit()
    data=client.get('/api/purchase_order/selectable?limit=1').get_json()
    assert [o['id'] for o in data['orders']]==[ids['orders'][1]]
    assert data['total']==1


def test_supplier_source_filters_and_null_received_quantity(selection_case):
    w,client,ids=selection_case
    w.db.session.execute(w.db.text('UPDATE purchase_order_item SET received_quantity = NULL WHERE id = :id'),{'id':ids['items'][1]})
    w.db.session.commit()
    data=client.get('/api/purchase_order/selectable',query_string={'supplier_id':ids['suppliers'][1],'purchase_order_id':ids['orders'][1]}).get_json()
    assert len(data['items'])==1 and data['items'][0]['remaining_quantity']==10
    assert data['total']==1


def test_search_literal_wildcards_and_excludes_received_matching_lines(selection_case):
    w,client,ids=selection_case
    w.db.session.get(w.PurchaseOrder,ids['orders'][1]).order_no='PO-%_-TARGET'
    w.db.session.commit()
    data=client.get('/api/purchase_order/selectable?limit=1&search=%25_').get_json()
    assert [o['id'] for o in data['orders']]==[ids['orders'][1]]
    w.db.session.get(w.PurchaseOrderItem,ids['items'][1]).received_quantity=10
    w.db.session.add(w.PurchaseOrderItem(purchase_order_id=ids['orders'][1],material_id=ids['materials'][0],quantity=2,received_quantity=0))
    w.db.session.commit()
    data=client.get('/api/purchase_order/selectable?search=M2').get_json()
    assert data['items']==[] and data['total']==0


def test_selector_requests_explicit_first_page_and_ignores_stale_search_results():
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    source=(ROOT/'app/templates/in_order_add.html').read_text(encoding='utf-8')
    function='function loadPurchaseOrderSelectable()'+source.split('function loadPurchaseOrderSelectable()',1)[1].split('\nfunction renderPurchaseOrderSelectableRows',1)[0]
    script=r'''
const assert=require('node:assert/strict');let purchaseOrderSearchSeq=0,rendered=[];
const purchaseOrderSelectableMap=new Map();const window={};
const body={innerHTML:''},hint={textContent:''},search={value:'old'};
const document={querySelector:()=>null,getElementById(id){return {purchaseOrderSelectBody:body,purchaseOrderSelectHint:hint,purchaseOrderSelectSearch:search}[id];}};
const sourcePurchaseOrderId='';function getCurrentSupplierId(){return '';}
function escapeHtml(v){return v;}function updatePurchaseOrderSelectionSummary(){}
function renderPurchaseOrderSelectableRows(items){rendered=items;}
const pending=[];
function fetch(url){return new Promise(resolve=>pending.push({url,resolve}));}
''' + (ROOT/'app/static/js/api.js').read_text(encoding='utf-8') + '\nconst WMS=window.WMS;\n' + function + r'''
loadPurchaseOrderSelectable(); search.value='new'; loadPurchaseOrderSelectable();
const params=new URL(pending[1].url,'http://localhost').searchParams;
assert.equal(params.get('search'),'new');assert.equal(params.get('page'),'1');assert.equal(params.get('limit'),'150');
pending[1].resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',items:['new'],total:160,total_pages:2})});
setImmediate(()=>{
 assert.deepEqual(rendered,['new']);assert.ok(hint.textContent.includes('160'));assert.ok(hint.textContent.includes('150'));
 pending[0].resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',items:['old'],total:1,total_pages:1})});
 setImmediate(()=>{assert.deepEqual(rendered,['new']);});
});
'''
    subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8',check=True)


def test_select_whole_order_accepts_quotes_without_css_selector_interpolation():
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    source=(ROOT/'app/templates/in_order_add.html').read_text(encoding='utf-8')
    function='function selectAllRowsOfOrder(orderNo)'+source.split('function selectAllRowsOfOrder(orderNo)',1)[1].split('\nfunction updatePurchaseOrderSelectionSummary',1)[0]
    script=r'''
const assert=require('node:assert/strict'),orderNo='PO"x\'[]';
const boxes=[{checked:false},{checked:false}];
const rows=boxes.map((box,i)=>({dataset:{orderNo:i===0?orderNo:'OTHER'},querySelector(){return box;}}));
const document={querySelectorAll(selector){assert.equal(selector,'#purchaseOrderSelectBody tr');return rows;}};
function updatePurchaseOrderSelectionSummary(){}
''' + function + r'''
selectAllRowsOfOrder(orderNo);assert.equal(boxes[0].checked,true);assert.equal(boxes[1].checked,false);
selectAllRowsOfOrder(orderNo);assert.equal(boxes[0].checked,false);
'''
    subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8',check=True)
