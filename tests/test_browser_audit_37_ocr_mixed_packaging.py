from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""017 bounded mixed rows, packaging and actual review-write rollback.

No confirmation POST, business document, provider connection, deletion or restore.
"""
from pathlib import Path
import json

import pytest
from sqlalchemy import event

import app as m
from tests.audit_regressions.http_fixture import http_case
from tests.test_browser_audit_35_ocr_contract import ocr_case,post,provider,response_document,snapshot

ROOT=Path(__file__).resolve().parents[1]
AI_TABLES={'ai_document_job','ai_document_attempt','ai_document_item'}


@pytest.fixture
def mixed_case(ocr_case):
    with m.app.app_context():
        m.db.session.add(m.Material(code='QA37-B',name='第二合成物料',unit_id=1,stock=0))
        m.db.session.commit()
    yield ocr_case


def save(name,value):
    (evidence_dir()/('mixed-'+name+'.json')).write_text(
        json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def assert_success_review(before,response,expected):
    assert response.status_code==200,response.json
    assert response.json['status']=='success' and response.json['draft'] is None
    after=snapshot();changed={t for t in before if before[t]!=after[t]}
    assert changed <= AI_TABLES,changed
    with m.app.app_context():
        job=m.AIDocumentJob.query.one();attempt=m.AIDocumentAttempt.query.one()
        rows=m.AIDocumentItem.query.order_by(m.AIDocumentItem.line_no).all()
        persisted={r.code:(r.quantity,r.match_status) for r in rows}
        assert job.status=='pending_confirmation' and job.generated_document_id is None
        assert attempt.job_id==job.id and attempt.item_count==len(expected)
        assert all(r.job_id==job.id for r in rows)
        material_ids={material.code:material.id for material in m.Material.query.all()}
        assert all(r.material_id==(material_ids[r.code] if r.match_status=='matched' else None) for r in rows)
        assert len(rows)==len(expected) and sorted(r.line_no for r in rows)==list(range(1,len(rows)+1))
        assert persisted==expected,persisted
        assert m.InOrder.query.count()==m.OutOrder.query.count()==0
    payload=response.json['confirmation']['payload']
    confirmation={r['code']:(r['quantity'],r['match_status']) for r in payload['rows']}
    assert confirmation==expected,confirmation
    assert all(r['material_id']==(material_ids[r['code']] if r['match_status']=='matched' else None)
        for r in payload['rows'])
    ui={r['code']:(r['quantity'],r['matched']) for r in response.json['items']}
    for code,(quantity,status) in expected.items():
        assert ui[code][1]==(status=='matched')
        if quantity!=0:assert ui[code][0]==quantity
    return changed


MIXED={
    'two_valid':([{'code':'QA27-M','quantity':2.5},{'code':'QA37-B','quantity':3}],200,
        {'QA27-M':(2.5,'matched'),'QA37-B':(3,'matched')}),
    'valid_and_negative':([{'code':'QA27-M','quantity':2.5},{'code':'QA37-B','quantity':-2}],200,
        {'QA27-M':(2.5,'matched'),'QA37-B':(-2,'unmatched')}),
    'valid_and_unknown_text':([{'code':'QA27-M','quantity':2.5},{'code':'QA37-B','quantity':'bad'}],200,
        {'QA27-M':(2.5,'matched'),'QA37-B':(0,'unmatched')}),
    'valid_and_nonfinite':([{'code':'QA27-M','quantity':2.5},{'code':'QA37-B','quantity':float('nan')}],422,{}),
    'valid_and_unrepresentable':([{'code':'QA27-M','quantity':2.5},{'code':'QA37-B','quantity':1e100}],422,{}),
    'valid_and_nonobject_entry':([{'code':'QA27-M','quantity':2.5},7],200,{'QA27-M':(2.5,'matched')}),
}


@pytest.mark.parametrize('name',list(MIXED))
def test_mixed_rows_keep_correct_links_or_reject_entire_batch_before_write(mixed_case,monkeypatch,name):
    clients,ids=mixed_case;items,status,expected=MIXED[name]
    calls=provider(monkeypatch,[response_document(items=items)])
    before=snapshot();response=post(clients())
    assert len(calls)==1 and response.status_code==status,response.json
    if status==422:
        assert response.json['status']=='error' and snapshot()==before
        save(name,{'http':422,'provider_calls':1,'all_rows_unchanged':True})
    else:
        changed=assert_success_review(before,response,expected)
        save(name,{'http':200,'provider_calls':1,'review_rows':len(expected),'row_code_quantity_status':expected,
            'changed_tables':sorted(changed),'business_inventory_config_credentials_unchanged':True})


PACKAGING={
    'missing_quantity':({'box_count':2,'pcs_per_box':5},200,10,'matched'),
    'zero_quantity':({'quantity':0,'box_count':2,'pcs_per_box':5},200,10,'matched'),
    'existing_quantity_wins':({'quantity':3,'box_count':2,'pcs_per_box':5},200,3,'matched'),
    'negative_quantity_not_overridden':({'quantity':-2,'box_count':2,'pcs_per_box':5},200,-2,'unmatched'),
    'zero_factor':({'quantity':0,'box_count':0,'pcs_per_box':5},200,0,'unmatched'),
    'negative_factor':({'quantity':0,'box_count':-2,'pcs_per_box':5},200,0,'unmatched'),
    'scientific_factors':({'quantity':0,'box_count':'1e3','pcs_per_box':'2.5e-1'},200,250,'matched'),
    'fractional_product':({'quantity':0,'box_count':0.1,'pcs_per_box':0.2},200,0.02,'matched'),
    'factor_rounding_before_product':({'quantity':0,'box_count':1.005,'pcs_per_box':2},200,2.02,'matched'),
    'largest_existing_decimal_precision':({'quantity':0,'box_count':1e12,'pcs_per_box':1e13},200,1e25,'matched'),
    'unsafe_product':({'quantity':0,'box_count':1e13,'pcs_per_box':1e13},422,0,''),
    'existing_quantity_ignores_unused_extreme_product':({'quantity':3,'box_count':1e20,'pcs_per_box':1e20},200,3,'matched'),
}


@pytest.mark.parametrize('name',list(PACKAGING))
def test_packaging_fallback_uses_existing_precedence_and_safe_business_precision(mixed_case,monkeypatch,name):
    clients,ids=mixed_case;fields,status,quantity,kind=PACKAGING[name]
    calls=provider(monkeypatch,[response_document(items=[{'code':'QA27-M',**fields}])])
    before=snapshot();response=post(clients())
    actual=None
    with m.app.app_context():
        row=m.AIDocumentItem.query.first()
        if row:actual=row.quantity
    save('pack-'+name,{'http':response.status_code,'provider_calls':len(calls),
        'persisted_quantity':actual,'all_rows_unchanged':snapshot()==before})
    assert len(calls)==1 and response.status_code==status,response.json
    if status==422:
        assert response.json['status']=='error' and snapshot()==before
    else:
        assert_success_review(before,response,{'QA27-M':(quantity,kind)})


@pytest.mark.parametrize('stage',['second_item_insert','confirmation_token_update'])
def test_review_write_failure_rolls_back_all_rows_and_session_confirmation(mixed_case,monkeypatch,stage):
    clients,ids=mixed_case
    calls=provider(monkeypatch,[response_document(items=[{'code':'QA27-M','quantity':2.5},
        {'code':'QA37-B','quantity':3}])]*2)
    c=clients();before=snapshot();seen={'item_inserts':0,'failed':False,'observed_prior_item_insert':False,
        'sqlite_write_transaction':False}
    with c.session_transaction() as session:pending_before=dict(session.get('_ai_document_confirmations') or {})
    with m.app.app_context():engine=m.db.engine
    def fail(conn,cursor,sql,params,context,many):
        upper=sql.lstrip().upper()
        if upper.startswith('INSERT INTO AI_DOCUMENT_ITEM'):
            seen['item_inserts']+=1
        trigger=(stage=='second_item_insert' and upper.startswith('INSERT INTO AI_DOCUMENT_ITEM') and seen['item_inserts']==2)
        trigger|=(stage=='confirmation_token_update' and upper.startswith('UPDATE AI_DOCUMENT_JOB') and 'CONFIRMATION_TOKEN' in upper)
        if trigger and not seen['failed']:
            seen['failed']=True
            seen['observed_prior_item_insert']=conn.exec_driver_sql('SELECT count(*) FROM ai_document_item').scalar()>0
            seen['sqlite_write_transaction']=conn.connection.driver_connection.in_transaction
            raise RuntimeError('QA37_TEST_WRITE_FAILURE')
    event.listen(engine,'before_cursor_execute',fail)
    try:response=post(c)
    finally:event.remove(engine,'before_cursor_execute',fail)
    with c.session_transaction() as session:pending_after=dict(session.get('_ai_document_confirmations') or {})
    same=snapshot()==before
    save('atomic-'+stage,{'http':response.status_code,'provider_calls':len(calls),'injection':seen,
        'all_rows_unchanged':same,'session_confirmation_count_before':len(pending_before),
        'session_confirmation_count_after':len(pending_after)})
    assert response.status_code==500 and seen['failed'] and seen['observed_prior_item_insert']
    assert seen['sqlite_write_transaction'],'Whole OCR review must still be in one write transaction'
    assert same,'Failed OCR must not leave a committed partial review job'
    assert pending_after==pending_before,'Failed OCR must not retain a new dangling confirmation token'
    assert len(calls)==1
    recovered=post(c)
    assert len(calls)==2
    assert_success_review(before,recovered,{'QA27-M':(2.5,'matched'),'QA37-B':(3,'matched')})
    save('atomic-'+stage,{'http':500,'failed_provider_calls':1,'injection':seen,
        'all_rows_unchanged':True,'session_confirmation_count_before':len(pending_before),
        'session_confirmation_count_after':len(pending_after),'manual_retry_http':200,
        'manual_retry_provider_calls':1,'recovered_review_jobs':1,'recovered_review_rows':2})


def test_packaged_ocr_quantity():
    from services.document_ocr_numbers import packaged_ocr_quantity,InvalidOCRNumber
    assert packaged_ocr_quantity(2,5)==10
    assert packaged_ocr_quantity(0,5)==packaged_ocr_quantity(-2,5)==0
    assert packaged_ocr_quantity('bad',5)==0
    assert packaged_ocr_quantity(1e13,1e13)==0
    with pytest.raises(InvalidOCRNumber):packaged_ocr_quantity(1e13,1e13,strict=True)


def test_existing_record_job_callers_keep_default_immediate_commit(mixed_case):
    from flask_login import login_user
    with m.app.test_request_context('/qa/default-helper-contract'):
        login_user(m.db.session.get(m.User,1))
        job=m._ai_record_document_job({'document_type':'in_order','items':[]},'qa-existing-caller',
            'pending_confirmation',matched=[],unmatched=[])
        job_id=job.id
        assert not m.db.session.connection().connection.driver_connection.in_transaction
        m.db.session.remove()
        assert m.db.session.get(m.AIDocumentJob,job_id).status=='pending_confirmation'
