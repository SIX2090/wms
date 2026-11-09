"""Actual native document API, fresh LPAC memory DB and synthetic credentials only."""
from copy import deepcopy
from datetime import date, datetime
import json

import pytest
from sqlalchemy import event

from tests.test_money_route_synthetic_20261109 import money_case
from tests.test_opening_money_routes_20261109 import seed, state

KINDS = ['inbound', 'outbound', 'stocktake', 'opening_stock', 'opening_stock_edit', 'inbound_draft']


def target(c, kind):
    w = c.w
    w.set_system_setting('auto_print_on_submit', '0')
    w.db.session.commit()
    assert w.get_system_setting_bool('auto_print_on_submit', True) is False
    endpoint = '/api/' + kind
    body = {'warehouse_code': 'S-MONEY-W1', 'business_type':'其他入库',
            'lines':[{'material_code':'B-M','quantity':1,'price':.5}]}
    if kind == 'opening_stock_edit':
        ident = seed(c, False, 3, 2, 6)
        from services.document_edit_guard import opening_line_revision
        line = w.db.session.get(w.OpeningStock, ident.line)
        endpoint += ''
        endpoint = '/api/opening_stock/' + str(ident.line)
        body = {'quantity':4,'revision':opening_line_revision(line,c.ids['user'])}
    elif kind == 'stocktake':
        batch = w.InventoryCheck(check_no='S-ATOMIC-CHECK',warehouse=c.warehouse,
                                 status='pending',frozen_at=datetime.now())
        w.db.session.add(batch);w.db.session.flush()
        w.db.session.add(w.InventoryCheckItem(inventory_check_id=batch.id,material_id=c.ids['material'],
                                              system_stock=5,actual_stock=5,difference=0,area=''))
        w.db.session.commit()
        body['check_id'] = batch.id
        body['lines'][0]['actual_stock'] = 3
    elif kind == 'opening_stock':
        body['date'] = date.today().isoformat()
        body['lines'][0]['quantity'] = 3
    elif kind == 'inbound_draft':
        endpoint = '/api/mobile/inbound_draft'
    login = c.client.post('/api/login',json={'username':'bom-audit','password':'fixture-only'})
    assert login.status_code == 200, login.json
    headers = {'Authorization':'Bearer '+login.json['data']['token'], 'X-Idempotency-Key':'synthetic-atomic-request'}
    # The test client also has a web session; a mixed-auth GET may skip Bearer auth.
    # Warm the real Bearer helper so fault injection targets business commit, not token renewal.
    with w.app.test_request_context(headers=headers):
        assert w.get_bearer_user().id == c.ids['user']
    return endpoint,body,headers


def snapshot(c):
    w = c.w
    w.db.session.remove()
    counts = tuple(getattr(w,name).query.count() for name in (
        'InOrder','OutOrder','InventoryCheckScan','OpeningStockDoc','PrintJob','AdjustmentOrder'))
    checks = tuple(w.db.session.query(w.InventoryCheckItem.id,w.InventoryCheckItem.actual_stock,
                    w.InventoryCheckItem.counted_at).order_by(w.InventoryCheckItem.id).all())
    return state(c),counts,checks


@pytest.mark.parametrize('kind', KINDS)
def test_native_document_idempotent(money_case,kind):
    c=money_case;endpoint,body,headers=target(c,kind)
    first=c.client.post(endpoint,json=body,headers=headers)
    assert first.status_code==200 and first.json['success'] is True,first.json
    after=snapshot(c)
    second=c.client.post(endpoint,json=body,headers=headers)
    assert second.status_code==200 and second.json==first.json,second.json
    assert snapshot(c)==after
    assert c.w.MobileApiRequest.query.count()==1
    assert c.w.PrintJob.query.count()==0


@pytest.mark.parametrize('kind', KINDS)
def test_receipt_persistence_failure_rolls_back_native_business_too(money_case,kind):
    c=money_case;w=c.w;endpoint,body,headers=target(c,kind);before=snapshot(c)
    session=w.db.session()
    def refuse_receipt(session):
        if any(isinstance(row,w.MobileApiRequest) for row in (*session.new,*session.identity_map.values())):
            raise RuntimeError('synthetic receipt commit failure')
    event.listen(session,'before_commit',refuse_receipt)
    try:
        result=c.client.post(endpoint,json=body,headers=headers)
    finally:
        event.remove(session,'before_commit',refuse_receipt)
    assert result.status_code in (500,503),result.json
    assert snapshot(c)==before,'A failed receipt cannot leave completed documents or stock changes'
    assert w.MobileApiRequest.query.count()==0


@pytest.mark.parametrize('kind', KINDS)
def test_post_commit_exception_is_recovered_from_atomic_native_receipt(money_case,monkeypatch,kind):
    c=money_case;w=c.w;endpoint,body,headers=target(c,kind)
    session=w.db.session();commit=session.commit;fired=[]
    def lose_result():
        finalizing = session.info.get('native_request', {}).get('finalizing', False)
        commit()
        if finalizing and not fired:
            fired.append(True)
            raise RuntimeError('synthetic response lost after commit')
    monkeypatch.setattr(session,'commit',lose_result)
    first=c.client.post(endpoint,json=body,headers=headers)
    assert fired
    assert first.status_code==200 and first.json['success'] is True,first.json
    after=snapshot(c)
    second=c.client.post(endpoint,json=body,headers=headers)
    assert second.status_code==200 and second.json==first.json,second.json
    assert snapshot(c)==after
    assert w.MobileApiRequest.query.count()==1


@pytest.mark.parametrize('kind', KINDS)
def test_native_key_cannot_silently_replay_different_payload(money_case,kind):
    c=money_case;endpoint,body,headers=target(c,kind)
    first=c.client.post(endpoint,json=body,headers=headers)
    assert first.status_code==200 and first.json['success'] is True,first.json
    after=snapshot(c);changed=deepcopy(body);changed['remark']='different synthetic content'
    second=c.client.post(endpoint,json=changed,headers=headers)
    assert second.status_code==409 and second.json['success'] is False,second.json
    assert snapshot(c)==after


@pytest.mark.parametrize('kind', KINDS)
def test_legacy_native_receipts_keep_the_original_record_for_manual_confirmation(money_case,kind):
    c=money_case;w=c.w;endpoint,body,headers=target(c,kind)
    expected={'status':'success','success':True,'message':'synthetic legacy','msg':'synthetic legacy','data':{'id':42}}
    w.db.session.add(w.MobileApiRequest(user_id=c.ids['user'],endpoint=kind,
        request_key=headers['X-Idempotency-Key'],status_code=200,response_json=json.dumps(expected)))
    w.db.session.commit();before=snapshot(c)
    result=c.client.post(endpoint,json=body,headers=headers)
    assert result.status_code==409 and '核对' in result.json['msg'],result.json
    assert snapshot(c)==before
    assert json.loads(w.MobileApiRequest.query.one().response_json)==expected


@pytest.mark.parametrize('enabled',[False,True])
def test_begin_native_document_write(money_case,enabled):
    c=money_case;w=c.w;endpoint,body,headers=target(c,'outbound')
    w.set_system_setting('location_management_enabled','1' if enabled else '0');w.db.session.commit()
    if enabled:
        body['lines'][0]['location_code']=c.warehouse
    result=c.client.post(endpoint,json=body,headers=headers)
    assert result.status_code==200 and result.json['success'] is True,result.json
    w.db.session.remove()
    assert w.MobileApiRequest.query.count()==1
    assert w.db.session.get(w.Material,c.ids['material']).stock==9
    for warehouse,quantity in ((c.wh1,4),(c.wh2,5)):
        assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,warehouse))[c.ids['material']]==quantity
    # INVENTORY_TRUTH §2: when location management is off, keep its historical rows untouched.
    assert w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id).with_entities(
        w.LocationInventory.warehouse_id,w.LocationInventory.quantity).all()==[(c.wh1,4 if enabled else 5),(c.wh2,5)]


@pytest.mark.parametrize('key',[0,False,42,[]])
def test_native_non_string_request_keys_fail_before_any_business_write(money_case,key):
    c=money_case;endpoint,body,headers=target(c,'inbound')
    headers.pop('X-Idempotency-Key');body['request_id']=key;before=snapshot(c)
    result=c.client.post(endpoint,json=body,headers=headers)
    assert result.status_code==400 and result.json['success'] is False,result.json
    assert snapshot(c)==before


def test_native_opening_edit_request_key_is_bound_to_the_line_path(money_case):
    c=money_case;w=c.w;endpoint,body,headers=target(c,'opening_stock_edit')
    first=c.client.post(endpoint,json=body,headers=headers)
    assert first.status_code==200 and first.json['success'] is True,first.json
    from services.document_edit_guard import opening_line_revision
    other=w.OpeningStock.query.filter_by(warehouse_id=c.wh2).one()
    second_body={'quantity':3,'revision':opening_line_revision(other,c.ids['user'])}
    other_path='/api/opening_stock/'+str(other.id);before=snapshot(c)
    result=c.client.post(other_path,json=second_body,headers=headers)
    assert result.status_code==409 and result.json['success'] is False,result.json
    assert snapshot(c)==before


@pytest.mark.parametrize('enabled',[False,True])
def test_native_same_key_is_independent_for_two_synthetic_accounts(money_case,enabled):
    from werkzeug.security import generate_password_hash
    c=money_case;w=c.w;endpoint,body,headers=target(c,'inbound')
    w.set_system_setting('location_management_enabled','1' if enabled else '0');w.db.session.commit()
    if enabled:
        body['lines'][0]['location_code']=c.warehouse
    first=c.client.post(endpoint,json=body,headers=headers)
    assert first.status_code==200 and first.json['success'] is True,first.json
    other=w.User(username='synthetic-second-native',role='warehouse',status='normal',
        password_hash=generate_password_hash('synthetic-second-only'),must_change_password=False)
    w.db.session.add(other);w.db.session.commit();other_id=other.id
    login=c.client.post('/api/login',json={'username':'synthetic-second-native','password':'synthetic-second-only'})
    assert login.status_code==200,login.json
    second_headers={**headers,'Authorization':'Bearer '+login.json['data']['token']}
    second=c.client.post(endpoint,json=body,headers=second_headers)
    assert second.status_code==200 and second.json['success'] is True,second.json
    assert first.json['data']['id']!=second.json['data']['id']
    w.db.session.remove()
    assert {row.user_id for row in w.MobileApiRequest.query.all()}=={c.ids['user'],other_id}
    assert {row.operator_id for row in w.InOrder.query.all()}=={c.ids['user'],other_id}
    assert w.db.session.get(w.Material,c.ids['material']).stock==12
    for warehouse,quantity in ((c.wh1,7),(c.wh2,5)):
        assert w.get_warehouse_stock_quantities(w.db.session.get(w.Warehouse,warehouse))[c.ids['material']]==quantity
    assert w.LocationInventory.query.order_by(w.LocationInventory.warehouse_id).with_entities(
        w.LocationInventory.warehouse_id,w.LocationInventory.quantity).all()==[(c.wh1,7 if enabled else 5),(c.wh2,5)]


@pytest.mark.parametrize('endpoint',KINDS+['voice_out_draft','voice_intent','assistant_chat'])
@pytest.mark.parametrize('key',[0,False,42,[]])
def test_all_native_decorator_consumers_validate_keys_before_entering_the_view(money_case,endpoint,key):
    c=money_case;w=c.w;user=w.db.session.get(w.User,c.ids['user'])
    def must_not_run(user):
        pytest.fail('Invalid request key reached the business or AI view')
    wrapped=w.mobile_api_idempotent(endpoint)(must_not_run)
    with w.app.test_request_context(json={'request_id':key}):
        response=w.app.make_response(wrapped(user))
        assert response.status_code==400
        assert response.get_json()['msg']=='幂等请求号必须为字符串'


@pytest.mark.parametrize('fail',[False,True])
def test_native_new_location_savepoint_does_not_commit_the_receipt_early(money_case,fail):
    c=money_case;w=c.w;endpoint,body,headers=target(c,'inbound')
    warehouse=w.Warehouse(code='S-ATOMIC-NEW-WH',name='合成原子新增仓',status='active')
    w.db.session.add(warehouse);w.db.session.flush();warehouse_id=warehouse.id
    w.set_system_setting('location_management_enabled','1');w.db.session.commit()
    body['warehouse_code']=warehouse.code;body['lines'][0]['location_code']='S-ATOMIC-NEW-LOCATION'
    before=snapshot(c);session=w.db.session();nested=[]
    def watch(active):
        if active.in_nested_transaction():
            nested.append(True)
        elif fail and any(isinstance(row,w.MobileApiRequest) for row in (*active.new,*active.identity_map.values())):
            raise RuntimeError('synthetic outer transaction receipt failure')
    event.listen(session,'before_commit',watch)
    try:
        result=c.client.post(endpoint,json=body,headers=headers)
    finally:
        event.remove(session,'before_commit',watch)
    if fail:
        assert result.status_code in (500,503),result.json
        assert snapshot(c)==before
        assert w.MobileApiRequest.query.count()==0
    else:
        assert result.status_code==200 and result.json['success'] is True,result.json
        assert nested,'The real location writer must exercise its SAVEPOINT'
        assert w.LocationInventory.query.filter_by(warehouse_id=warehouse_id).one().quantity==1
        assert w.db.session.get(w.Material,c.ids['material']).stock==11
        after=snapshot(c)
        retry=c.client.post(endpoint,json=body,headers=headers)
        assert retry.status_code==200 and retry.json==result.json,retry.json
        assert snapshot(c)==after


@pytest.mark.parametrize('fail',[False,True])
def test_native_draft_auto_created_material_and_unit_reference_share_the_receipt_transaction(money_case,fail):
    c=money_case;w=c.w;endpoint,body,headers=target(c,'inbound_draft')
    body['auto_create_material']=True
    body['lines']=[{'material_code':'UNREGISTERED-SYNTHETIC','name':'合成自动建档物料',
        'spec':'S-ATOMIC','unit':'合成原子新单位','quantity':2,'price':3}]
    before=snapshot(c);counts=(w.Material.query.count(),w.Unit.query.count());session=w.db.session()
    def refuse(active):
        if fail and any(isinstance(row,w.MobileApiRequest) for row in (*active.new,*active.identity_map.values())):
            raise RuntimeError('synthetic auto-create receipt failure')
    event.listen(session,'before_commit',refuse)
    try:
        result=c.client.post(endpoint,json=body,headers=headers)
    finally:
        event.remove(session,'before_commit',refuse)
    if fail:
        assert result.status_code in (500,503),result.json
        assert snapshot(c)==before
        assert (w.Material.query.count(),w.Unit.query.count())==counts
    else:
        assert result.status_code==200 and result.json['success'] is True,result.json
        assert len(result.json['data']['auto_created'])==1
        assert (w.Material.query.count(),w.Unit.query.count())==(counts[0]+1,counts[1])
        row=w.InOrder.query.one();assert row.status=='pending'
        created=w.Material.query.filter_by(name='合成自动建档物料').one();assert created.stock==0
        assert created.unit_id==c.ids['unit'],'Unknown unit text keeps the existing default-unit policy'
        after=snapshot(c)
        retry=c.client.post(endpoint,json=body,headers=headers)
        assert retry.status_code==200 and retry.json==result.json,retry.json
        assert snapshot(c)==after
        assert (w.Material.query.count(),w.Unit.query.count())==(counts[0]+1,counts[1])


@pytest.mark.parametrize('kind',['inbound','outbound'])
def test_native_retry_after_dbapi_commit_result_is_lost_keeps_one_business_write(money_case,monkeypatch,kind):
    c=money_case;w=c.w;endpoint,body,headers=target(c,kind)
    engine=w.db.engine;commit=engine.dialect.do_commit;fired=[]
    def lose_dbapi_result(connection):
        finalizing = w.db.session().info.get('native_request', {}).get('finalizing', False)
        commit(connection)
        if finalizing and not fired:
            fired.append(True)
            raise RuntimeError('synthetic DBAPI commit result lost')
    monkeypatch.setattr(engine.dialect,'do_commit',lose_dbapi_result)
    first=c.client.post(endpoint,json=body,headers=headers)
    assert fired and first.status_code==200,first.json
    after=snapshot(c)
    model=w.InOrder if kind=='inbound' else w.OutOrder
    ident=model.query.one().id
    second=c.client.post(endpoint,json=body,headers=headers)
    assert second.status_code==200 and second.json['success'] is True,second.json
    assert second.json['data']['id']==ident
    assert snapshot(c)==after
    assert w.MobileApiRequest.query.count()==1


@pytest.mark.parametrize('kind',KINDS)
def test_native_response_serialization_failure_keeps_business_and_receipt_atomic(money_case,monkeypatch,kind):
    import services.native_request_idempotency as native
    c=money_case;endpoint,body,headers=target(c,kind);before=snapshot(c)
    original=native.make_response;fired=[]
    def fail_first_response(*args,**kwargs):
        if not fired:
            fired.append(True)
            raise RuntimeError('synthetic response serialization failure after business writes')
        return original(*args,**kwargs)
    monkeypatch.setattr(native,'make_response',fail_first_response)
    result=c.client.post(endpoint,json=body,headers=headers)
    assert fired and result.status_code in (500,503),result.json
    assert snapshot(c)==before
    assert c.w.MobileApiRequest.query.count()==0
