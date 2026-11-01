from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""New 017 numeric/recognition-repeat boundaries. No business confirmation POST."""
from pathlib import Path
import json
import math
import sqlite3
import threading

import pytest
from sqlalchemy import create_engine,event
from sqlalchemy.pool import NullPool

import app as m
from tests.audit_regressions.http_fixture import http_case
from tests.test_browser_audit_35_ocr_contract import ocr_case,post,provider,response_document,snapshot

ROOT=Path(__file__).resolve().parents[1]


def save(name,record):
    (evidence_dir()/('numeric-'+name+'.json')).write_text(
        json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def strict_json(response):
    def reject(value):raise ValueError('Nonfinite JSON constant '+value)
    try:
        json.loads(response.get_data(as_text=True),parse_constant=reject)
        return True
    except ValueError:return False


INVALID={
    'nan_literal':float('nan'),'positive_infinity_literal':float('inf'),
    'negative_infinity_literal':float('-inf'),'nan_string':'NaN',
    'infinity_string':'Infinity','overflow_exponent':'1e309',
    'integer_float_overflow':10**400,'finite_rounding_overflow':1e100,
    'integer_precision_loss':2**53+1,
}


@pytest.mark.parametrize('name',list(INVALID))
def test_unsupported_numeric_is_controlled_before_any_write(ocr_case,monkeypatch,name):
    clients,ids=ocr_case
    calls=provider(monkeypatch,[response_document(INVALID[name])])
    before=snapshot();r=post(clients());unchanged=snapshot()==before
    save(name,{'http':r.status_code,'strict_json':strict_json(r),
        'all_rows_unchanged':unchanged,'provider_calls':len(calls),
        'response_status':(r.json or {}).get('status')})
    assert r.status_code==422,r.get_data(as_text=True)[:240]
    assert r.json['status']=='error' and strict_json(r)
    assert unchanged and len(calls)==1


@pytest.mark.parametrize('name,value,expected,matched',[
    ('scientific_large','1e3',1000,True),('scientific_fraction','2.5e-1',0.25,True),
    ('half_up_cent','1.005e0',1.01,True),('negative_zero',-0.0,0,False)])
def test_supported_representation_is_consistent_in_response_and_review(ocr_case,monkeypatch,name,value,expected,matched):
    clients,ids=ocr_case;calls=provider(monkeypatch,[response_document(value)])
    before=snapshot();r=post(clients());assert r.status_code==200,r.json
    with m.app.app_context():
        job=m.AIDocumentJob.query.one();item=m.AIDocumentItem.query.one()
        actual=item.quantity;kind=item.match_status
        assert job.status=='pending_confirmation' and job.generated_document_id is None
    save(name,{'http':200,'strict_json':strict_json(r),'stored_quantity':actual,
        'response_quantity':r.json['items'][0]['quantity'],'match_status':kind,
        'provider_calls':len(calls)})
    assert math.isfinite(actual) and actual==expected
    assert r.json['items'][0]['quantity']==expected
    assert r.json['items'][0]['matched']==matched
    assert kind==('matched' if matched else 'unmatched')
    assert strict_json(r) and len(calls)==1
    after=snapshot()
    assert {t for t in before if before[t]!=after[t]} <= {'ai_document_job','ai_document_attempt','ai_document_item'}


def assert_review_count(before,count):
    after=snapshot()
    assert {t for t in before if before[t]!=after[t]} <= {'ai_document_job','ai_document_attempt','ai_document_item'}
    with m.app.app_context():
        assert m.AIDocumentJob.query.count()==m.AIDocumentAttempt.query.count()==m.AIDocumentItem.query.count()==count
        jobs=m.AIDocumentJob.query.all()
        assert all(j.status=='pending_confirmation' and j.generated_document_id is None for j in jobs)
        job_ids=sorted(j.id for j in jobs)
        assert sorted(i.job_id for i in m.AIDocumentItem.query.all())==job_ids
        assert sorted(a.job_id for a in m.AIDocumentAttempt.query.all())==job_ids
        assert all(i.quantity==2.5 for i in m.AIDocumentItem.query.all())
        assert m.InOrder.query.count()==m.OutOrder.query.count()==0


def test_explicit_same_image_rerecognition_keeps_two_reviews_without_business_creation(ocr_case,monkeypatch):
    clients,ids=ocr_case;calls=provider(monkeypatch,[response_document(),response_document()])
    c=clients();before=snapshot();first=post(c);second=post(c)
    assert first.status_code==second.status_code==200
    assert first.json['confirmation']['url']!=second.json['confirmation']['url']
    with c.session_transaction() as session:assert len(session['_ai_document_confirmations'])==2
    assert_review_count(before,2);assert len(calls)==2
    save('explicit-rerecognition',{'http':[200,200],'provider_calls':2,'pending_reviews':2,
        'business_documents':0,'semantics':'two explicit recognition attempts; no draft deduplication requirement invented'})




def test_parse_ocr_number():
    from services.document_ocr_numbers import parse_ocr_number, _recognized_number, InvalidOCRNumber
    for value,expected in [('-2套',-2),('1e3',1000),('2.5e-1',0.25),('1.005e0',1.01),
        ('1,200个',1200),('bad',0),('NaN',0),('1e309',0),(10**400,0)]:
        assert parse_ocr_number(value,0)==expected
    with pytest.raises(InvalidOCRNumber):_recognized_number('Infinity')


def test_normalize_document_quantities():
    from services.document_ocr_numbers import normalize_document_quantities
    data={'document_type':'in_order','items':[{'quantity':'1e3','box_count':'2','pcs_per_box':'2.5e1'},
        {'quantity':'bad'}]}
    normalized=normalize_document_quantities(data)
    assert data['items'][0]['quantity']=='1e3'
    assert normalized['items']==[{'quantity':1000,'box_count':2,'pcs_per_box':25},{'quantity':'bad'}]


def test_normalize_document_quantities_rejects_nonfinite_before_public_json():
    from services.document_ocr_numbers import normalize_document_quantities, InvalidOCRNumber
    with pytest.raises(InvalidOCRNumber):
        normalize_document_quantities({'items':[{'quantity':float('nan')}]})


def test_rejected_numeric_can_be_manually_rerecognized_in_same_session(ocr_case,monkeypatch):
    clients,ids=ocr_case
    calls=provider(monkeypatch,[response_document(float('nan')),response_document()])
    c=clients();before=snapshot();failed=post(c)
    assert failed.status_code==422 and snapshot()==before and len(calls)==1
    restored=post(c)
    assert restored.status_code==200 and len(calls)==2
    assert_review_count(before,1)
    save('numeric-recovery',{'http':[422,200],'provider_calls':2,
        'failed_all_rows_unchanged':True,'pending_reviews_after_manual_retry':1,'business_documents':0})
