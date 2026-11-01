from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""017 real multipart route/preprocessing/routing/vision parsing/confirmation.
Only the provider transport and synthetic endpoint/model configuration are replaced.
No real providers, credentials, business commits, inventory changes or deletion.
"""
from pathlib import Path
import copy
import io
import json

import pytest
import requests
from PIL import Image,ImageDraw
from sqlalchemy import event,select

import app as m
from tests.audit_regressions.http_fixture import http_case

ROOT=Path(__file__).resolve().parents[1]
MARKER='QA35_SYNTHETIC_PRIVATE_PROVIDER_DIAGNOSTIC'


def snapshot():
    with m.app.app_context():
        return {t.name:[list(r) for r in m.db.session.execute(select(t).order_by(*t.primary_key.columns))]
            for t in m.db.metadata.tables.values()}


def image():
    picture=Image.new('RGB',(600,400),'white');draw=ImageDraw.Draw(picture)
    draw.rectangle((20,20,580,380),outline='black',width=3)
    for y in range(60,360,40):draw.line((30,y,570,y),fill='black',width=1)
    output=io.BytesIO();picture.save(output,format='PNG');output.seek(0);return output


def post(client):
    return client.post('/api/ai/document_ocr',data={'image':(image(),'QA35.png'),
        'document_type':'in_order','remarks':'仅合成待确认，不提交'},content_type='multipart/form-data')


def response_document(quantity=2.5,items=None):
    extracted={'document_type':'in_order','order_no':'QA35-SYNTHETIC',
        'items':items if items is not None else [{'code':'QA27-M','name':'合成物料','quantity':quantity}]}
    return {'status':200,'body':{'choices':[{'message':{'content':
        '合成单据识别结果。\n```json\n'+json.dumps(extracted,ensure_ascii=False)+'\n```'}}]}}


@pytest.fixture
def ocr_case(http_case,monkeypatch):
    clients,ids,_=http_case
    monkeypatch.setattr(m,'_ai_llm_configured',lambda *a,**k:True)
    monkeypatch.setattr(m,'_ai_llm_vision_enabled',lambda *a,**k:True)
    monkeypatch.setattr(m,'_ai_llm_headers',lambda *a,**k:{})
    monkeypatch.setattr(m,'_ai_llm_endpoint',lambda *a,**k:'https://qa35.invalid/no-network')
    monkeypatch.setattr(m,'_ai_llm_model',lambda *a,**k:'QA35-V1')
    monkeypatch.setattr(m,'_AI_MODEL_POOL',[('QA35-V1','合成主模型',1),('QA35-V2','合成备用模型',2)])
    with m.app.app_context():engine=m.db.engine
    def deny_delete(conn,cursor,sql,params,context,many):
        if sql.lstrip().upper().startswith('DELETE'):raise AssertionError('No deletion authorized')
    event.listen(engine,'before_cursor_execute',deny_delete)
    try:yield clients,ids
    finally:event.remove(engine,'before_cursor_execute',deny_delete)


class LocalResponse:
    def __init__(self,data):self.data=data;self.status_code=data['status'];self.ok=self.status_code<400;self.text=MARKER
    def raise_for_status(self):
        if not self.ok:raise requests.exceptions.HTTPError(MARKER)
    def json(self):
        if self.data.get('invalid_json'):raise ValueError(MARKER)
        return copy.deepcopy(self.data['body'])


def provider(monkeypatch,records):
    calls=[]
    def request(url,**options):
        calls.append({'url':url,'options':copy.deepcopy(options)})
        assert len(calls)<=len(records),'Exceeded finite expected transport budget'
        entry=records[len(calls)-1]
        if isinstance(entry,Exception):raise entry
        return LocalResponse(entry)
    monkeypatch.setattr(m.requests,'post',request)
    return calls


def evidence(name,value):
    (evidence_dir()/('ocr-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


def assert_pending_only(before,body,quantity=2.5,matched=True):
    assert body['status']=='success' and body['draft'] is None and body['confirmation']
    after=snapshot()
    changed={name for name in before if before[name]!=after[name]}
    assert changed <= {'ai_document_job','ai_document_attempt','ai_document_item'},changed
    with m.app.app_context():
        job=m.AIDocumentJob.query.one()
        item=m.AIDocumentItem.query.one()
        assert job.status=='pending_confirmation' and job.generated_document_id is None
        assert item.quantity==quantity and item.match_status==('matched' if matched else 'unmatched')
        assert m.InOrder.query.count()==0 and m.OutOrder.query.count()==0
    return changed


FAILURES={
    'both_models_read_timeout':([requests.exceptions.ReadTimeout(MARKER)]*2,2),
    'both_models_empty_choices':([{'status':200,'body':{'choices':[]}}]*2,2),
    'both_models_bad_json':([{'status':200,'invalid_json':True}]*2,2),
    'provider_429_diagnostic':([{'status':429,'body':{'error':{'message':MARKER,'type':'rate_limit','code':'429'}}}],1),
    'items_not_iterable':([response_document(items=7)],1),
}


@pytest.mark.parametrize('scenario',list(FAILURES))
def test_failure_then_explicit_retry(ocr_case,monkeypatch,scenario):
    clients,ids=ocr_case;records,count=FAILURES[scenario]
    calls=provider(monkeypatch,records+[response_document()])
    client=clients();before=snapshot()
    failed=post(client)
    assert failed.status_code==500 and failed.json['status']=='error',failed.json
    assert len(calls)==count
    assert snapshot()==before,'Failed OCR must not create any business/config/AI review row'
    evidence(scenario,{'http':failed.status_code,'body':failed.json,'provider_calls':len(calls),
        'rows_unchanged':True,'private_marker_in_public_body':MARKER in json.dumps(failed.json)})
    assert MARKER not in json.dumps(failed.json),'OCR error/call evidence must not expose provider internals'
    retried=post(client)
    assert retried.status_code==200,retried.json
    assert len(calls)==count+1
    changed=assert_pending_only(before,retried.json)
    for call in calls:
        assert call['url']=='https://qa35.invalid/no-network' and call['options']['headers']=={}
        assert call['options']['timeout']==120
    evidence(scenario,{'http':500,'provider_calls_before_manual_retry':count,'retry_http':200,
        'retry_provider_calls':1,'failed_all_rows_unchanged':True,'success_changed_tables':sorted(changed),
        'only_pending_confirmation_created':True,'private_marker_in_public_body':False})


@pytest.mark.parametrize('first_failure',[requests.exceptions.ReadTimeout(MARKER),
    {'status':503,'body':{'error':{'message':MARKER}}}],ids=['timeout','503'])
def test_real_backup_model_recovers_to_pending_confirmation(ocr_case,monkeypatch,first_failure):
    clients,ids=ocr_case;calls=provider(monkeypatch,[first_failure,response_document()])
    before=snapshot();response=post(clients())
    assert response.status_code==200,response.json
    assert [c['options']['json']['model'] for c in calls]==['QA35-V1','QA35-V2']
    changed=assert_pending_only(before,response.json)
    evidence('backup-'+('timeout' if isinstance(first_failure,Exception) else '503'),{
        'http':200,'provider_calls':2,'models':['QA35-V1','QA35-V2'],
        'only_pending_confirmation_created':True,'changed_tables':sorted(changed)})


@pytest.mark.parametrize('quantity,stored,matched',[(2.5,2.5,True),('bad',0,False),(0,0,False),(-2,-2,False)])
def test_quantity_requires_human_confirmation_without_inventory_effect(ocr_case,monkeypatch,quantity,stored,matched):
    clients,ids=ocr_case;calls=provider(monkeypatch,[response_document(quantity)])
    before=snapshot();response=post(clients())
    assert response.status_code==200,response.json
    assert len(calls)==1
    changed=assert_pending_only(before,response.json,stored,matched)
    evidence('quantity-'+str(quantity),{'http':200,'provider_calls':1,'stored_quantity':stored,
        'match_status':'matched' if matched else 'unmatched','changed_tables':sorted(changed),
        'business_inventory_config_credentials_unchanged':True})


@pytest.mark.parametrize('role,csrf,code',[(None,True,401),('finance',True,403),('admin',False,400)])
def test_actual_web_session_auth_role_and_csrf_prevent_provider(ocr_case,monkeypatch,role,csrf,code):
    clients,ids=ocr_case;calls=provider(monkeypatch,[]);before=snapshot()
    response=post(clients(role=role,csrf=csrf))
    assert response.status_code==code,response.json
    assert calls==[] and snapshot()==before


@pytest.mark.parametrize('value,expected',[('-2',-2),('-2.75套',-2.75),('-1,200.5',-1200.5),
    ('数量：+2.5个',2.5),('2箱',2),('1,200个',1200),('bad',0),(0,0)])
def test_shared_ocr_number_preserves_sign_and_existing_formats(value,expected):
    assert m._ai_ocr_number(value,0)==expected


@pytest.mark.parametrize('quantity,expected',[(-2,-2),(0,10),('bad',10)])
def test_extraction_packaging_does_not_replace_explicit_negative(quantity,expected):
    raw={'document_type':'in_order','items':[{'code':'QA27-M','quantity':quantity,'box_count':2,'pcs_per_box':5}]}
    normalized=m._ai_normalize_document_extraction(raw)
    assert normalized['items'][0]['quantity']==expected


def test_public_ocr_call_evidence():
    from types import SimpleNamespace
    from services.document_ocr_feedback import public_ocr_call_evidence
    raw={'attempts':[{'attempt_no':1,'error_type':'other','error_message':MARKER,
        'duration_ms':1.25,'has_reply':False,'provider_private':MARKER}],
        'total_attempts':1,'success':False,'final_error_type':'other','final_error_message':MARKER,
        'total_duration_ms':1.25,'provider_private':MARKER}
    public=public_ocr_call_evidence(SimpleNamespace(to_dict=lambda:copy.deepcopy(raw)))
    assert MARKER not in json.dumps(public)
    assert public['total_attempts']==1 and not public['success']
    assert public['attempts'][0]['duration_ms']==1.25
    assert 'provider_private' not in public and 'provider_private' not in public['attempts'][0]


def test_signed_parser_adjacent_confidence_stays_in_valid_range():
    assert m._ai_ocr_confidence('-20')==0
    assert m._ai_ocr_confidence('90%')==0.9
    assert m._ai_ocr_confidence('0.85')==0.85


def test_signed_parser_table_consumer_rejects_negative_without_losing_valid_line():
    doc=m._ai_extract_document_table_from_text('物料编码\t物料名称\t数量\t单位\nA001\t合成一\t-2\t个\nA002\t合成二\t3\t个')
    assert [(r['code'],r['quantity']) for r in doc['items']]==[('A002',3)]


def test_public_ocr_error_message():
    from services.document_ocr_feedback import public_ocr_error_message
    for code in (400,401,403,429):
        message=public_ocr_error_message(f'HTTP {code}: Authorization: Bearer {MARKER}')
        assert f'HTTP {code}' in message and MARKER not in message and 'Bearer' not in message


def test_same_vision_error_boundary_also_protects_excel_consumer(ocr_case,monkeypatch):
    clients,ids=ocr_case
    calls=provider(monkeypatch,[FAILURES['provider_429_diagnostic'][0][0]])
    before=snapshot()
    response=clients().post('/api/ai/document_ocr_excel',data={'image':(image(),'QA35.png')},content_type='multipart/form-data')
    assert response.status_code==500,response.json
    assert MARKER not in json.dumps(response.json) and '429' in response.json['msg']
    assert len(calls)==1 and snapshot()==before
