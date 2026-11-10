"""Web save retry receipts are atomic, user-scoped and payload-bound."""
import pytest
import app as w
from sqlalchemy import event
from services.web_document_idempotency import web_document_idempotent, stage_document_response


@pytest.fixture
def receipt_case(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        user=w.User(username='retry-test',role='admin',password_hash='unused',must_change_password=False)
        wh=w.Warehouse(code='RETRY',name='重试仓',status='active',is_default=True)
        mat=w.Material(code='RETRY',name='重试物料',stock=0)
        w.db.session.add_all([user,wh,mat]);w.db.session.commit()
        uid, wid=user.id,wh.id
    client=w.app.test_client()
    with client.session_transaction() as s:s['_user_id']=str(uid);s['_fresh']=True
    yield client, {'order_id':'None','business_type':'产品入库','warehouse_id':wid,'items':[{'code':'RETRY','quantity':1,'price':0}]}
    with w.app.app_context():w.db.session.remove()


def test_web_document_idempotent(receipt_case):
    client,payload=receipt_case
    headers={'X-Idempotency-Key':'same-request'}
    first=client.post('/in_order/add',json=payload,headers=headers)
    second=client.post('/in_order/add',json=payload,headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json == second.json
    with w.app.app_context():
        assert w.InOrder.query.count()==1
        assert w.Material.query.one().stock==0


def test_changed_payload_rejected_and_new_key_creates_new_intent(receipt_case):
    client,payload=receipt_case;headers={'X-Idempotency-Key':'one'}
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==200
    payload['remark']='changed'
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==409
    assert client.post('/in_order/add',json=payload,headers={'X-Idempotency-Key':'two'}).status_code==200
    with w.app.app_context():assert w.InOrder.query.count()==2


def test_validation_error_releases_claim(receipt_case):
    client,payload=receipt_case;headers={'X-Idempotency-Key':'retry'}
    invalid=dict(payload,items=[])
    assert client.post('/in_order/add',json=invalid,headers=headers).status_code==400
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==200
    with w.app.app_context():assert w.InOrder.query.count()==1


def test_stage_document_response(receipt_case):
    client,payload=receipt_case;headers={'X-Idempotency-Key':'commit-fault'}
    with w.app.app_context():
        engine=w.db.engine
    def fail_commit(connection):raise RuntimeError('synthetic commit failure')
    event.listen(engine,'commit',fail_commit)
    try:
        response=client.post('/in_order/add',json=payload,headers=headers)
        assert response.json['status']=='error'
    finally:event.remove(engine,'commit',fail_commit)
    with w.app.app_context():
        assert w.InOrder.query.count()==0
        assert w.MobileApiRequest.query.count()==0
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==200


def test_authentication_precedes_replay(receipt_case):
    client,payload=receipt_case;headers={'X-Idempotency-Key':'private'}
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==200
    outsider=w.app.test_client()
    assert outsider.post('/in_order/add',json=payload,headers=headers).status_code in (302,401)


from tests.test_document_create_number_conflicts import case, case as all_case, CASES, payload as create_payload, post as create_post


@pytest.mark.parametrize('kind,endpoint,model,field', CASES)
@pytest.mark.parametrize('transport', ['json','form'])
def test_document_family_replay(all_case,kind,endpoint,model,field,transport):
    clients,ids=all_case
    client=clients[0]
    client.environ_base['HTTP_X_IDEMPOTENCY_KEY']='family-retry'
    data=create_payload(kind,ids,'REPLAY-1')
    if transport == 'form' and kind in ('check', 'transfer'):
        assert create_post(client,endpoint,data,transport).status_code == 400
        transport = 'json'  # These table-save routes deliberately accept JSON only.
    one=create_post(client,endpoint,data,transport)
    two=create_post(client,endpoint,data,transport)
    assert one.status_code==200,one.json
    assert two.status_code==200,two.json
    assert one.json==two.json
    with w.app.app_context():assert getattr(w,model).query.count()==1


def test_two_connections_serialize_same_request(receipt_case,tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import create_engine
    client,payload=receipt_case
    engine=create_engine('sqlite:///'+str(tmp_path/'concurrent.db'),connect_args={'timeout':30})
    with w.app.app_context():
        monkeypatch.setitem(w.db.engines,None,engine)
        w.db.create_all()
        user=w.User(username='parallel',role='admin',password_hash='unused',must_change_password=False)
        wh=w.Warehouse(code='RETRY',name='重试仓',status='active',is_default=True)
        mat=w.Material(code='RETRY',name='重试物料',stock=0)
        w.db.session.add_all([user,wh,mat]);w.db.session.commit()
        uid=user.id;payload=dict(payload,warehouse_id=wh.id)
        w.db.session.remove()
    def send():
        c=w.app.test_client()
        with c.session_transaction() as session:session['_user_id']=str(uid);session['_fresh']=True
        r=c.post('/in_order/add',json=payload,headers={'X-Idempotency-Key':'parallel'})
        return r.status_code,r.json
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:send(),range(2)))
        assert results[0]==results[1]
        assert results[0][0]==200,results
        with w.app.app_context():
            assert w.InOrder.query.count()==1
            assert w.MobileApiRequest.query.count()==1
            w.db.session.remove()
    finally:engine.dispose()



from tests.test_sales_order_number_conflicts import sales_case, payload as sales_payload


def test_sales_warnings_replay_exactly(sales_case):
    clients,ids=sales_case
    data=sales_payload(ids,'SO-REPLAY')
    headers={'X-Idempotency-Key':'sales-replay'}
    one=clients[0].post('/sales/add',json=data,headers=headers)
    two=clients[0].post('/sales/add',json=data,headers=headers)
    assert one.status_code==two.status_code==200
    assert one.json==two.json


def test_requisition_table_replay(all_case):
    clients,ids=all_case
    data=create_payload('work-requisition',ids,'RQ-REPLAY')
    headers={'X-Idempotency-Key':'requisition-replay'}
    one=clients[0].post('/requisition/save_table',json=data,headers=headers)
    two=clients[0].post('/requisition/save_table',json=data,headers=headers)
    assert one.status_code==two.status_code==200,(one.json,two.json)
    assert one.json==two.json


def test_actual_api_attaches_and_retains_retry_keys():
    import subprocess
    from pathlib import Path
    source=Path(__file__).resolve().parents[1]/'app/static/js/api.js'
    program=r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const calls=[];let fail=false;
const ctx={FormData,Math,Date,JSON,encodeURIComponent,setTimeout,document:{querySelector(){return {content:'csrf'};}},location:{href:''},confirm(){return false;},fetch(url,options){calls.push({url,options});if(fail)return Promise.reject(new Error('lost response'));return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',id:1})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
(async()=>{
const api=ctx.WMS.api,data={order_id:'None',order_no:'IN-PREVIEW',items:[{quantity:1}]};
await api.postRaw('/in_order/add',data);await api.postRaw('/in_order/add',data);
assert.equal(calls[0].options.headers['X-Idempotency-Key'],calls[1].options.headers['X-Idempotency-Key']);
assert.equal(calls[0].options.headers['X-CSRFToken'],'csrf');
await api.postRaw('/in_order/add',{...data,order_id:1});assert.equal(calls[2].options.headers['X-Idempotency-Key'],undefined);
await api.postRaw('/purchase_request/add',{request_id:1,request_no:'PR-1'});assert.equal(calls.at(-1).options.headers['X-Idempotency-Key'],undefined);
fail=true;await api.postRaw('/out_order/add',{items:[]}).catch(()=>{});const key=calls.at(-1).options.headers['X-Idempotency-Key'];
fail=false;await api.postRaw('/out_order/add',{items:[]});assert.equal(calls.at(-1).options.headers['X-Idempotency-Key'],key);
await api.postRaw('/out_order/add',{items:[]});assert.notEqual(calls.at(-1).options.headers['X-Idempotency-Key'],key);
const form=new FormData();form.set('issue_no','ISSUE-1');await api.postRaw('/subcontract/issue/add',form);assert.ok(calls.at(-1).options.headers['X-Idempotency-Key']);
for (const path of ['/bom/add','/bom/save_table']) {
  const bom=new FormData();bom.set('bom_no','BOM-PREVIEW');
  fail=true;await api.postRaw(path,bom).catch(()=>{});const firstKey=calls.at(-1).options.headers['X-Idempotency-Key'];assert.ok(firstKey);
  fail=false;await api.postRaw(path,bom);assert.equal(calls.at(-1).options.headers['X-Idempotency-Key'],firstKey);
  await api.postRaw(path,bom);assert.equal(calls.at(-1).options.headers['X-Idempotency-Key'],firstKey);
}
// A new page/form may legitimately reuse a deleted preview number. It needs a new identity.
const another={...ctx, WMS:undefined};another.window=another;vm.createContext(another);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),another);
await another.WMS.api.postRaw('/in_order/add',data);assert.notEqual(calls.at(-1).options.headers['X-Idempotency-Key'],calls[0].options.headers['X-Idempotency-Key']);
await api.postRaw('/out_order/1/complete',{});assert.equal(calls.at(-1).options.headers['X-Idempotency-Key'],undefined);
})().catch(e=>{console.error(e);process.exit(1);});
"""
    result=subprocess.run(['node','-e',program,str(source)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


@pytest.mark.parametrize('endpoint,model', [
    ('/subcontract/add','SubcontractOrder'),
    ('/subcontract/issue/add','SubcontractIssue'),
    ('/subcontract/receive/add','SubcontractReceive'),
    ('/requisition/add','ProductionRequisition'),
    ('/transfer/add','TransferOrder'),
])
def test_legacy_form_entry_replay(all_case,endpoint,model):
    clients,ids=all_case
    with w.app.app_context():
        parent=w.SubcontractOrder(order_no='SC-PARENT',warehouse=ids['names'][0],operator_id=ids['user'])
        w.db.session.add(parent);w.db.session.commit();parent_id=parent.id
    data=dict(warehouse_id=ids['a'],subcontract_order_id=parent_id,
              from_warehouse=ids['names'][0],to_warehouse=ids['names'][1],
              material_id=ids['mats'][0],quantity=1)
    headers={'X-Idempotency-Key':'form-retry'}
    one=clients[0].post(endpoint,data=data,headers=headers)
    two=clients[0].post(endpoint,data=data,headers=headers)
    assert one.status_code==two.status_code==200,(one.json,two.json)
    assert one.json==two.json
    with w.app.app_context():assert getattr(w,model).query.count()==(2 if model=='SubcontractOrder' else 1)


def test_purchase_order_replay(all_case):
    clients,ids=all_case
    with w.app.app_context():
        supplier=w.Supplier(code='REPLAY-S',name='重试供应商')
        w.db.session.add(supplier);w.db.session.commit();sid=supplier.id
    data=dict(order_no='PO-REPLAY',supplier_id=sid,items=[dict(material_id=ids['mats'][0],quantity=1,price=2)])
    headers={'X-Idempotency-Key':'purchase-retry'}
    one=clients[0].post('/purchase_order/save',json=data,headers=headers)
    two=clients[0].post('/purchase_order/save',json=data,headers=headers)
    assert one.status_code==two.status_code==200,(one.json,two.json)
    assert one.json==two.json
    with w.app.app_context():assert w.PurchaseOrder.query.count()==1


def test_user_scope_and_csrf_are_preserved(receipt_case,monkeypatch):
    client,payload=receipt_case;headers={'X-Idempotency-Key':'scoped'}
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==200
    with w.app.app_context():
        user=w.User(username='second-fixture',role='admin',password_hash='unused',must_change_password=False)
        w.db.session.add(user);w.db.session.commit();uid=user.id
    other=w.app.test_client()
    with other.session_transaction() as session:session['_user_id']=str(uid);session['_fresh']=True
    assert other.post('/in_order/add',json=payload,headers=headers).status_code==200
    with w.app.app_context():assert w.InOrder.query.count()==2
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',True)
    assert client.post('/in_order/add',json=payload,headers=headers).status_code==400
    with w.app.app_context():assert w.InOrder.query.count()==2


@pytest.mark.parametrize('scope',['','all'])
def test_legacy_check_entry_preserves_generated_message(all_case,scope):
    clients,ids=all_case
    data={'warehouse_id':ids['a'],'scope':scope}
    headers={'X-Idempotency-Key':'check-form'}
    one=clients[0].post('/check/add',data=data,headers=headers)
    two=clients[0].post('/check/add',data=data,headers=headers)
    assert one.status_code==two.status_code==200,(one.json,two.json)
    assert one.json==two.json
    with w.app.app_context():assert w.InventoryCheck.query.count()==1


@pytest.mark.parametrize('entry', CASES, ids=[entry[0] for entry in CASES])
def test_explicit_document_edit_bypasses_create_receipt(all_case, entry):
    clients, ids = all_case
    kind, endpoint, model_name, _ = entry
    headers = {'X-Idempotency-Key': 'create-then-edit'}
    data = create_payload(kind, ids, 'EDIT-RETRY-' + kind)
    first = clients[0].post(endpoint, json=data, headers=headers)
    assert first.status_code == 200, first.json
    edited = create_payload(kind, ids, data['order_no'], True)
    edited['request_id' if kind == 'request' else 'order_id'] = first.json['id']
    from tests.document_revision_client import document_post
    result = document_post(clients[0], endpoint, json=edited, headers=headers)
    assert result.status_code == 200, result.json
    assert result.json['id'] == first.json['id']
    with w.app.app_context():
        doc = getattr(w, model_name).query.one()
        assert doc.remark == 'second'
        assert doc.items[0].material_id == ids['mats'][1]
        assert w.MobileApiRequest.query.count() == 1
