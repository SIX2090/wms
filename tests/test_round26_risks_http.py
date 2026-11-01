"""Bounded round26 risk verification with complete local HTTP dispatch."""
import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import event

import app as m
from tests.test_round26_input_http import http_case


@pytest.mark.parametrize('scenario',['exception','provider_error','malformed_response'])
def test_vision_diagnostics_do_not_echo_provider_internals(http_case,monkeypatch,scenario):
    client,ids,state=http_case
    marker='ROUND27_PUBLIC_PRIVATE_DETAIL_SENTINEL'
    monkeypatch.setattr(m,'_ai_llm_configured',lambda *a:True)
    monkeypatch.setattr(m,'_ai_llm_vision_enabled',lambda *a:True)
    monkeypatch.setattr(m,'_ai_llm_headers',lambda *a:{})
    monkeypatch.setattr(m,'_ai_llm_endpoint',lambda *a:'https://example.invalid/no-call')
    monkeypatch.setattr(m,'_ai_llm_model',lambda *a,**k:'SYNTHETIC')
    def provider(*a,**k):
        if scenario=='exception':raise RuntimeError(marker)
        if scenario=='provider_error':
            return SimpleNamespace(ok=False,status_code=401,json=lambda:{'error':{'message':marker}})
        return SimpleNamespace(ok=True,raise_for_status=lambda:None,json=lambda:{'choices':marker})
    monkeypatch.setattr(m.requests,'post',provider)
    before=state()
    response=client().post('/system_settings/test_ai_llm',data={'test_type':'vision'})
    assert response.status_code==502,response.get_json()
    body=response.get_json()
    assert marker not in json.dumps(body)
    assert 'RuntimeError' not in json.dumps(body)
    assert state()==before


def test_supplier_reuses_same_material_price_query_without_changing_metrics(http_case,monkeypatch):
    client,ids,state=http_case
    monkeypatch.setattr(m,'_ai_call_llm_chat',lambda message:'synthetic analysis, no provider called')
    with m.app.app_context():
        supplier=m.Supplier(code='QA27-S',name='合成供应商')
        m.db.session.add(supplier);m.db.session.flush()
        for n,price in enumerate([10,20,30]):
            order=m.InOrder(order_no='QA27-IN-'+str(n),business_type='purchase',warehouse='QA27-A',
                supplier_id=supplier.id,date=date.today(),status='completed',total_amount=price)
            m.db.session.add(order);m.db.session.flush()
            m.db.session.add(m.InOrderItem(in_order_id=order.id,material_id=ids['material'],quantity=1,price=price,amount=price))
        m.db.session.commit()
        engine=m.db.engine
    price_queries=[]
    def capture(connection,cursor,statement,parameters,context,executemany):
        if statement.lstrip().upper().startswith('SELECT') and 'in_order_item.price AS' in statement and 'JOIN in_order' in statement:
            price_queries.append(statement)
    event.listen(engine,'before_cursor_execute',capture)
    try:
        response=client().post('/api/ai/supplier_evaluation',json={})
    finally:
        event.remove(engine,'before_cursor_execute',capture)
    assert response.status_code==200,response.get_json()
    body=response.get_json()
    assert body['status']=='success'
    assert body['summary']['total']==1 and body['summary']['total_amount']==60
    assert body['evaluations'][0]['avg_price_cv']==0.5
    assert len(price_queries)==1, len(price_queries)


@pytest.mark.parametrize('force',[False,True])
def test_share_master_off_does_not_dispatch_even_force(http_case,monkeypatch,force):
    client,ids,state=http_case
    def refuse(*a,**k): raise AssertionError('Master off must not send/build/helper-health')
    monkeypatch.setattr(m,'_wechat_share_deliver',refuse)
    monkeypatch.setattr(m,'_build_order_share_image',refuse)
    monkeypatch.setattr(m,'_wechat_share_get_helper_health',refuse)
    with m.app.app_context():
        m.db.session.add(m.SystemSetting(key='wechat_share_enabled',value='0'))
        m.db.session.commit()
    response=client().post('/wechat_share/run_now',data={'force':'1' if force else '0'})
    assert response.status_code==200 and response.get_json()['status']=='skipped'
    with m.app.app_context():
        assert m.WechatShareLog.query.count()==0


def test_merge_preview_is_read_only_and_execution_is_not_attempted(http_case,monkeypatch):
    client,ids,state=http_case
    def refuse(*a,**k):raise AssertionError('Permanent merge not authorized in this test')
    monkeypatch.setattr(m,'merge_material_duplicates',refuse)
    with m.app.app_context():
        target=m.db.session.get(m.Material,ids['material'])
        source=m.Material(code='QA27-SOURCE',name=target.name,unit_id=target.unit_id,stock=0)
        m.db.session.add(source);m.db.session.commit();source_id=source.id
    response=client().post(f'/material/{source_id}/merge',json={
        'target_code':'QA27-M','confirm':False,'identity_confirmed':False})
    assert response.status_code==200,response.get_json()
    assert response.get_json()['status']=='preview'
    with m.app.app_context():
        assert m.db.session.get(m.Material,source_id) is not None
        assert m.db.session.get(m.Material,ids['material']).stock==30


def test_share_existing_pending_log_is_skipped_across_sequential_http_requests(http_case,monkeypatch):
    client,ids,state=http_case
    def refuse(*a,**k):raise AssertionError('Existing pending log must skip image creation and delivery')
    monkeypatch.setattr(m,'_wechat_share_deliver',refuse)
    monkeypatch.setattr(m,'_build_order_share_image',refuse)
    with m.app.app_context():
        m.db.session.add(m.SystemSetting(key='wechat_share_enabled',value='1'))
        config=m.WechatShareConfig(receiver_name='QA27-NO-SEND',share_in_order=True,
            enabled=True,auto_send=False,immediate_on_complete=False)
        order=m.InOrder(order_no='QA27-NO-SEND',business_type='purchase',warehouse='QA27-A',
            date=date.today(),status='completed',total_amount=0)
        m.db.session.add_all([config,order]);m.db.session.flush()
        m.db.session.add(m.WechatShareLog(config_id=config.id,module_key='in_order',order_id=order.id,
            order_no=order.order_no,share_date=date.today(),status='pending'))
        m.db.session.commit()
    c=client()
    for _ in range(2):
        response=c.post('/wechat_share/run_now',data={'force':'0'})
        assert response.status_code==200,response.get_json()
        assert response.get_json()['created']==0 and response.get_json()['skipped']==1
    with m.app.app_context():
        assert m.WechatShareLog.query.count()==1


def test_fresh_merge_preview_revalidates_changed_identity_without_merging(http_case,monkeypatch):
    client,ids,state=http_case
    monkeypatch.setattr(m,'merge_material_duplicates',lambda *a,**k:pytest.fail('No permanent merge'))
    with m.app.app_context():
        target=m.db.session.get(m.Material,ids['material'])
        source=m.Material(code='QA27-CHANGED',name=target.name,unit_id=target.unit_id,stock=0)
        m.db.session.add(source);m.db.session.commit();source_id=source.id
    c=client()
    payload={'target_code':'QA27-M','confirm':False,'identity_confirmed':False}
    assert c.post(f'/material/{source_id}/merge',json=payload).status_code==200
    with m.app.app_context():
        m.db.session.get(m.Material,source_id).spec='SYNTHETIC-CHANGED'
        m.db.session.commit()
    changed=c.post(f'/material/{source_id}/merge',json=payload)
    assert changed.status_code==400,changed.get_json()
    with m.app.app_context():
        assert m.db.session.get(m.Material,source_id) is not None
