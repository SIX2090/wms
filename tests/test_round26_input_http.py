"""Round26: complete WMS dispatch with real auth, CSRF and fresh RAM data.

Sessions are synthetic; invalid password hashes cannot be used for real login.
No real provider, device, credential generation, merge, or nonempty deletion.
"""
from tests.document_revision_client import document_post
import json
from datetime import date, datetime, timedelta

import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app as m


@pytest.fixture
def http_case(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    monkeypatch.setitem(m.app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setitem(m.app.config, 'WTF_CSRF_ENABLED', True)
    monkeypatch.setitem(m.app.config, 'SESSION_COOKIE_SECURE', False)
    calls = []
    def no_io(*args, **kwargs):
        calls.append('unexpected external effect')
        raise AssertionError('No external I/O or image/stock side effects in input tests')
    monkeypatch.setattr(m, '_ai_call_llm_chat', no_io)
    monkeypatch.setattr(m, '_save_material_image_from_url', no_io)
    engine = create_engine('sqlite://', poolclass=StaticPool)
    with m.app.app_context():
        old_engine = m.db.engines[None]
        m.db.session.remove()
        m.db.engines[None] = engine
        m.db.create_all()
        m.db.session.add_all([
            m.SystemSetting(key='ai_feature_rollout_mode', value='all'),
            m.SystemSetting(key='ai_feature_global_enabled', value='1'),
        ])
        users = {}
        for role in ('admin', 'warehouse', 'finance'):
            user = m.User(username='QA27-' + role, role=role,
                password_hash='!invalid-unusable-test-hash', must_change_password=False, status='normal')
            m.db.session.add(user)
            m.db.session.flush()
            users[role] = user.id
        a = m.Warehouse(code='QA27-A', name='QA27-A', status='active')
        b = m.Warehouse(code='QA27-B', name='QA27-B', status='active')
        unit = m.Unit(code='QA27-U', name='个')
        m.db.session.add_all([a, b, unit]); m.db.session.flush()
        material = m.Material(code='QA27-M', name='合成物料', unit_id=unit.id, stock=30)
        m.db.session.add(material); m.db.session.flush()
        for wh, quantity, kind in [(a,190,'in'),(a,-180,'out'),(b,20,'in')]:
            m.db.session.add(m.StockTransaction(material_id=material.id, warehouse_id=wh.id,
                location=wh.name, quantity=quantity, transaction_type=kind,
                created_at=datetime.now()-timedelta(days=2)))
        check = m.InventoryCheck(check_no='QA27-CK', warehouse=a.name, status='pending',
            frozen_at=datetime.now()-timedelta(days=1), operator_id=users['warehouse'])
        m.db.session.add(check); m.db.session.flush()
        m.db.session.add(m.InventoryCheckItem(inventory_check_id=check.id, material_id=material.id,
            system_stock=10, actual_stock=10, difference=0,
            counted_by=users['warehouse'], counted_at=datetime.now()))
        m.db.session.commit()
        ids = dict(material=material.id, check=check.id, a=a.id, b=b.id, unit=unit.id)

    def client(role='admin', csrf=True):
        c = m.app.test_client()
        c.environ_base['HTTP_ACCEPT'] = 'application/json'
        c.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        with c.session_transaction() as session:
            if role:
                session['_user_id'] = str(users[role])
                session['_fresh'] = True
            session['csrf_token'] = 'qa27-fixed-public-csrf-seed'
        if csrf:
            serializer=URLSafeTimedSerializer(m.app.secret_key, salt='wtf-csrf-token')
            c.environ_base['HTTP_X_CSRFTOKEN'] = serializer.dumps('qa27-fixed-public-csrf-seed')
        return c

    def business_state():
        with m.app.app_context():
            return dict(adjustments=m.AdjustmentOrder.query.count(),
                details=m.AdjustmentOrderItem.query.count(),
                flows=m.StockTransaction.query.count(), material=m.db.session.get(m.Material, ids['material']).stock,
                check=m.db.session.get(m.InventoryCheck, ids['check']).status,
                images=m.db.session.get(m.Material, ids['material']).image)
    try:
        yield client, ids, business_state
    finally:
        with m.app.app_context():
            m.db.session.remove()
            m.db.engines[None] = old_engine
        engine.dispose()
        assert calls == []


def endpoint(key, ids):
    return {'forecast':'/api/ai/demand_forecast', 'adjustment':'/adjustment/add',
        'check':f"/check/{ids['check']}/complete", 'image':f"/material/{ids['material']}/image_select",
        'acceptance':'/api/ai/acceptance/evidence_package'}[key]


@pytest.mark.parametrize('key', ['forecast','adjustment','check','image','acceptance'])
@pytest.mark.parametrize('raw', ['[1]','[]','1','0','true','false','"bad"','""','null','{broken'])
def test_invalid_root_is_controlled_400_and_no_business_changes(http_case, key, raw):
    client, ids, state = http_case
    before=state()
    response=document_post(client(),endpoint(key,ids), data=raw, content_type='application/json')
    assert response.status_code == 400, response.get_data(as_text=True)[:300]
    body=response.get_json()
    assert body and body['status']=='error'
    assert all(word not in json.dumps(body) for word in ['AttributeError','TypeError','Traceback','input_value'])
    assert state()==before


@pytest.mark.parametrize('key', ['forecast','adjustment','check','image','acceptance'])
def test_real_authentication_and_csrf_guards(http_case, key):
    client, ids, state=http_case
    path=endpoint(key,ids)
    before=state()
    assert document_post(client(role=None),path,json={}).status_code in (401,302)
    assert document_post(client(csrf=False),path,json={}).status_code==400
    denied=document_post(client(role='finance'),path,json={})
    assert denied.status_code==403, denied.get_data(as_text=True)[:300]
    assert state()==before


@pytest.mark.parametrize('days', ['7',None,True,7.0,0,-1,8,365,1e30,[],{}])
def test_forecast_period_type_and_bounds(http_case, days):
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('forecast',ids),json={'forecast_days':days})
    assert response.status_code==400
    assert state()==before


@pytest.mark.parametrize('period', [7,14,30])
def test_forecast_normal_real_read_query(http_case, period):
    client,ids,state=http_case
    response=document_post(client(role='warehouse'),endpoint('forecast',ids),json={'forecast_days':period})
    assert response.status_code==200,response.get_data(as_text=True)[:300]
    body=response.get_json()
    assert body['status']=='success' and body['summary']['total']==1
    assert body['forecasts'][0]['forecast_qty']==period
    assert body['forecasts'][0]['current_stock']==30


@pytest.mark.parametrize('payload', [{'adjustment_no':1},{'date':[]},{'remark':{}},{'warehouse':True},
    {'items':{}},{'items':[1]},{'items':[{'code':[]} ]},
    {'items':[{'material_id':1,'quantity':'nan'}]},
    {'items':[{'material_id':1,'quantity':float('inf')}]},
    {'items':[{'material_id':1,'quantity':True}]},
    {'items':[{'material_id':1,'quantity':0}]},
    {'items':[{'material_id':1,'quantity':1000000}]},
    {'items':[{'material_id':1,'quantity':10**400}]},
    {'warehouse_id':2**80},{'order_id':False},{'order_id':'bad'},
    {'order_id':1,'id':2},{'items':[{'material_id':2**80,'quantity':1}]}])
def test_adjustment_rejects_bad_types_before_any_mutation(http_case,payload):
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('adjustment',ids),json=payload)
    assert response.status_code==400,response.get_data(as_text=True)[:300]
    assert state()==before


@pytest.mark.parametrize('force', [[],{},2,'not-a-boolean',1.1])
def test_check_force_must_be_an_explicit_boolean(http_case,force):
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('check',ids),json={'force':force})
    assert response.status_code==400
    assert state()==before


def test_zero_difference_completion_and_repeat_are_real_http(http_case):
    client,ids,state=http_case
    c=client(role='warehouse')
    response=document_post(c,endpoint('check',ids),json={'force':False})
    assert response.status_code==200,response.get_json()
    assert response.get_json()['status']=='success'
    after=state()
    assert after['check']=='completed' and after['adjustments']==0 and after['flows']==3
    repeat=document_post(c,endpoint('check',ids),json={'force':False})
    assert repeat.status_code==400
    assert state()==after


def test_valid_adjustment_creates_only_a_new_draft(http_case):
    client,ids,state=http_case
    response=document_post(client(role='warehouse'),endpoint('adjustment',ids),json={
        'adjustment_no':'QA27-ADJ-NEW', 'adjustment_type':'surplus', 'warehouse_id':ids['a'],
        'date':date.today().isoformat(), 'items':[{'material_id':ids['material'],'quantity':'1.25'}]})
    assert response.status_code==200,response.get_data(as_text=True)[:300]
    assert response.get_json()['status']=='success'
    after=state()
    assert after['adjustments']==1 and after['details']==1
    assert after['material']==30 and after['flows']==3


@pytest.mark.parametrize('url',[1,[],{},True])
def test_image_url_type_is_checked_before_download(http_case,url):
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('image',ids),json={'image_url':url})
    assert response.status_code==400
    assert state()==before


@pytest.mark.parametrize('payload',[{'category':[]},{'category':True},{'category':'x'*101}])
def test_forecast_category_boundary(http_case,payload):
    client,ids,state=http_case
    before=state()
    assert document_post(client(),endpoint('forecast',ids),json=payload).status_code==400
    assert state()==before


@pytest.mark.parametrize('payload',[{'days':'7'},{'days':True},{'days':0},{'days':31},{'end_date':[]}])
def test_acceptance_field_types_are_controlled(http_case,payload):
    client,ids,state=http_case
    assert document_post(client(),endpoint('acceptance',ids),json=payload).status_code==400


def test_json_object_body(http_case):
    # json_object_body and CheckCompleteInput retain the legacy empty POST.
    client,ids,state=http_case
    assert document_post(client(role='warehouse'),endpoint('check',ids)).status_code==200
    assert document_post(client(),endpoint('image',ids),json={}).status_code==400
    assert document_post(client(),endpoint('acceptance',ids),json={'days':7}).status_code==404


def test_consistent_document_id(http_case):
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('adjustment',ids),json={'order_id':1,'id':2})
    assert response.status_code==400 and '参数格式' in response.get_json()['msg']
    assert state()==before


@pytest.mark.parametrize('quantity',['nan','inf','-inf','0','1000000'])
def test_adjustment_form_uses_same_finite_quantity_guard(http_case,quantity):
    # AdjustmentItemInput shares finite_quantity with JSON; no existing detail is deleted.
    client,ids,state=http_case
    before=state()
    response=document_post(client(),endpoint('adjustment',ids),data={
        'adjustment_type':'surplus','warehouse_id':str(ids['a']),
        'material_id':str(ids['material']),'quantity':quantity})
    assert response.status_code==400
    assert state()==before


@pytest.mark.parametrize('extra',[{'remark':'x'*501},{'adjustment_no':'x'*51},{'warehouse_id':str(2**80)}])
def test_adjustment_form_header_boundaries_match_json(http_case,extra):
    client,ids,state=http_case
    before=state()
    payload={'adjustment_type':'surplus','warehouse_id':str(ids['a']),
        'material_id':str(ids['material']),'quantity':'1'}
    payload.update(extra)
    assert document_post(client(),endpoint('adjustment',ids),data=payload).status_code==400
    assert state()==before
