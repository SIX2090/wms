from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Five finite 037 date/aggregation contracts; synthetic time is not observation."""
from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import re

from itsdangerous import URLSafeTimedSerializer
import pytest
from sqlalchemy import create_engine, event, select

import app as m
from ai.ops.launch_acceptance import ALL_ACCEPTANCE_METRICS, AUTO_SUBMIT_FORBIDDEN_ACTIONS
from ai.ops.business_quality import ALL_METRICS
from ai.ops.acceptance_evidence import RollbackEvidence

ROOT=Path(__file__).resolve().parents[1]
DAY=datetime(2026,11,1)


def record(name,data):
    (evidence_dir()/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')


def unchanged_rows():
    with m.app.app_context():
        return {t.name:[list(row) for row in m.db.session.execute(select(t).order_by(*t.primary_key.columns))]
            for t in m.db.metadata.tables.values()
            if t.name not in {'ai_acceptance_daily_snapshot','ai_acceptance_evidence_package','operation_log'}}


@pytest.fixture
def acceptance_case(tmp_path,monkeypatch):
    path=tmp_path/'fresh-qa44.sqlite'
    assert not path.exists()
    assert path.resolve().is_relative_to(tmp_path.resolve())
    engine=create_engine('sqlite:///'+path.as_posix())
    seed_mode=[True]
    @event.listens_for(engine,'before_cursor_execute')
    def boundary(conn,cursor,sql,parameters,context,many):
        verb=sql.lstrip().split(None,1)[0].upper()
        assert verb not in {'DELETE','DROP','ALTER','REPLACE'},'Deletion/restore forbidden'
        if not seed_mode[0] and verb in {'INSERT','UPDATE','CREATE'}:
            match=re.match(r'\s*(?:INSERT INTO|UPDATE)\s+["\[]?([a-z_]+)',sql,re.I)
            assert match and match.group(1).lower() in {
                'ai_acceptance_daily_snapshot','ai_acceptance_evidence_package','operation_log'},sql
    monkeypatch.setitem(m.app.config,'TESTING',True)
    monkeypatch.setitem(m.app.config,'PROPAGATE_EXCEPTIONS',False)
    monkeypatch.setitem(m.app.config,'WTF_CSRF_ENABLED',True)
    monkeypatch.setitem(m.app.config,'SESSION_COOKIE_SECURE',False)
    with m.app.app_context():
        original=m.db.engines[None]
        m.db.session.remove();m.db.engines[None]=engine;m.db.create_all()
        actor=m.User(username='QA44-unusable-session-actor',role='admin',status='normal',
            password_hash='!qa44-unusable-no-password',must_change_password=False)
        m.db.session.add(actor);m.db.session.commit();actor_id=actor.id
    seed_mode[0]=False
    def seed(rows):
        seed_mode[0]=True
        try:
            with m.app.app_context():
                m.db.session.add_all(rows);m.db.session.commit()
                return [row.id for row in rows]
        finally:seed_mode[0]=False
    client=m.app.test_client()
    with client.session_transaction() as session:
        session['_user_id']=str(actor_id);session['_fresh']=True;session['csrf_token']='qa44-public-csrf'
    client.environ_base.update(HTTP_ACCEPT='application/json',HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        HTTP_X_CSRFTOKEN=URLSafeTimedSerializer(m.app.secret_key,salt='wtf-csrf-token').dumps('qa44-public-csrf'))
    monkeypatch.setattr(m,'_ai_f02_query_rollout_info',lambda:{
        'user_count':1,'role_count':3,'roles':('admin','warehouse','purchase')})
    monkeypatch.setattr(m,'_ai_f02_query_rollback_events',lambda start,end:[
        RollbackEvidence('QA44-'+action,action,actor_id,'admin',end+'T10:00:00',end+'T10:01:00',60)
        for action in ('shutdown','restore')])  # Evidence metadata only, no rollback action.
    def forbidden(*args,**kwargs):raise AssertionError('No model, helper or external transport')
    monkeypatch.setattr(m.requests,'post',forbidden);monkeypatch.setattr(m.requests,'get',forbidden)
    try:yield {'client':client,'seed':seed,'actor':actor_id,'engine':engine}
    finally:
        with m.app.app_context():
            m.db.session.remove();m.db.engines[None]=original
        engine.dispose()  # Keep fresh file; no table drop, deletion or restore.


def collect(case,day):
    response=case['client'].post('/api/ai/acceptance/daily_snapshot',json={'date':day})
    assert response.status_code==200,response.json
    return response.json['snapshot']


def feedback(actor,at,field='supplier',correct=True,line=-1):
    return m.AIFieldFeedback(user_id=actor,source='QA44-SYNTHETIC',field_name=field,line_index=line,
        original_value='QA44',corrected_value='QA44',adopted=not correct,created_at=at)


def test_default_local_date_switches_at_midnight_and_same_date_recollect_updates(acceptance_case,monkeypatch):
    case=acceptance_case
    class Clock(datetime):
        current=datetime(2026,10,31,23,59,59)
        @classmethod
        def now(cls,tz=None):
            assert tz is None,'Current acceptance contract uses local naive time'
            return cls.current
    monkeypatch.setattr(m,'datetime',Clock)
    before=unchanged_rows()
    first=case['client'].post('/api/ai/acceptance/daily_snapshot',json={})
    Clock.current=datetime(2026,11,1,0,0,0)
    second=case['client'].post('/api/ai/acceptance/daily_snapshot',json={})
    Clock.current=datetime(2026,11,1,0,0,1)
    third=case['client'].post('/api/ai/acceptance/daily_snapshot',json={})
    assert [r.status_code for r in (first,second,third)]==[200,200,200]
    assert [r.json['snapshot']['snapshot_date'] for r in (first,second,third)]==['2026-10-31','2026-11-01','2026-11-01']
    package=case['client'].post('/api/ai/acceptance/evidence_package',json={'days':7})
    assert package.status_code==200 and package.json['package']['end_date']=='2026-11-01'
    with m.app.app_context():assert m.AIAcceptanceDailySnapshot.query.count()==2
    assert unchanged_rows()==before
    record('local-midnight-default',{'injected_local_times':['2026-10-31T23:59:59','2026-11-01T00:00:00','2026-11-01T00:00:01'],
        'persisted_snapshot_count':2,'package_end_date':package.json['package']['end_date'],
        'real_seven_day_observation':False,'all_other_rows_unchanged':True})


def test_absolute_metrics_use_half_open_local_natural_day(acceptance_case):
    case=acceptance_case
    times=[DAY-timedelta(microseconds=1),DAY,DAY+timedelta(days=1,microseconds=-1),DAY+timedelta(days=1)]
    run=m.AIRun(user_id=case['actor'],request_id='QA44-BOUNDARY',request_hash='qa44',endpoint='synthetic')
    run_id=case['seed']([run])[0]
    for index,at in enumerate(times):
        job=m.AIDocumentJob(user_id=case['actor'],source='QA44',status='draft_created',created_at=at)
        job_id=case['seed']([job])[0]
        case['seed']([
            m.AIToolCall(ai_run_id=run_id,user_id=case['actor'],tool_name=next(iter(AUTO_SUBMIT_FORBIDDEN_ACTIONS)),
                status='completed',permission_allowed=False,created_at=at),
            m.AIDraftIdempotency(user_id=case['actor'],capability='QA44',idempotency_key=f'QA44-{index}',
                status='replayed',created_at=at),
            m.AIDocumentItem(job_id=job_id,line_no=1,confidence=0.2,created_at=at)])
    before=unchanged_rows()
    snapshots={day:collect(case,day)['absolute_counts'] for day in ('2026-10-31','2026-11-01','2026-11-02')}
    assert snapshots=={day:{metric:count for metric in ALL_ACCEPTANCE_METRICS}
        for day,count in [('2026-10-31',1),('2026-11-01',2),('2026-11-02',1)]}
    assert unchanged_rows()==before
    record('absolute-natural-day',{'counts':snapshots,'all_other_rows_unchanged':True})


def test_real_quality_samples_populate_all_seven_metric_numerators_and_denominators(acceptance_case):
    case=acceptance_case;actor=case['actor'];at=DAY+timedelta(hours=12)
    case['seed']([feedback(actor,at,'document_type'),feedback(actor,at,'supplier',False),
        feedback(actor,at,'name',True,0),feedback(actor,at,'name',False,1),
        m.AIDraftIdempotency(user_id=actor,capability='QA44',idempotency_key='QA44-completed',status='completed',created_at=at),
        m.AIDraftIdempotency(user_id=actor,capability='QA44',idempotency_key='QA44-replayed',status='replayed',created_at=at)])
    before=unchanged_rows();snapshot=collect(case,'2026-11-01');metrics=snapshot['quality_metrics']
    expected={'classification_accuracy':(1,1),'header_accuracy':(0,1),'line_recall':(1,2),
        'material_match_rate':(1,2),'human_correction_rate':(2,4),'draft_adoption_rate':(0,1),
        'duplicate_interception_rate':(1,2)}
    record('real-quality-metrics',{'actual':metrics,'expected':expected})
    assert set(metrics)==set(ALL_METRICS)
    for key,(num,den) in expected.items():
        assert metrics[key]=={'numerator':num,'denominator':den,'rate':round(num/den,6)},(key,metrics[key])
    assert unchanged_rows()==before


def test_quality_day_excludes_next_midnight_at_actual_query_boundary(acceptance_case,monkeypatch):
    case=acceptance_case
    case['seed']([feedback(case['actor'],DAY),
        feedback(case['actor'],DAY+timedelta(days=1,microseconds=-1)),
        feedback(case['actor'],DAY+timedelta(days=1))])
    original=m._ai_bq_query_samples;observed=[]
    def observe(filters=None):
        samples=original(filters)
        observed.append({'filter':filters,'sample_dates':[sample.occurred_at for sample in samples]})
        return samples
    monkeypatch.setattr(m,'_ai_bq_query_samples',observe)  # Observe real query, no sample substitution.
    before=unchanged_rows();snapshot=collect(case,'2026-11-01')
    record('quality-midnight-boundary',{'observed_actual_samples':observed,'metrics':snapshot['quality_metrics']})
    assert observed and observed[0]['sample_dates']==['2026-11-01'],observed
    assert snapshot['quality_metrics']['header_accuracy']=={'numerator':2,'denominator':2,'rate':1.0}
    assert unchanged_rows()==before


def test_seven_day_package_clips_outside_dates_and_uses_weighted_totals(acceptance_case):
    case=acceptance_case;start=datetime(2026,10,26)
    rows=[feedback(case['actor'],start+timedelta(hours=12))]
    rows += [feedback(case['actor'],start+timedelta(days=1,hours=12),correct=(index==0)) for index in range(9)]
    rows += [feedback(case['actor'],start-timedelta(days=1)),feedback(case['actor'],start+timedelta(days=7))]
    case['seed'](rows);before=unchanged_rows()
    # Include adjacent snapshots as sentinels; the requested inclusive date range must clip them.
    for offset in range(-1,8):collect(case,(start+timedelta(days=offset)).strftime('%Y-%m-%d'))
    response=case['client'].post('/api/ai/acceptance/evidence_package',json={'end_date':'2026-11-01','days':7})
    assert response.status_code==200,response.json
    package=response.json['package'];quality=package['seven_day_summary']['quality_summary']['header_accuracy']
    record('weighted-seven-day-package',{'package':package,'validation_passed':response.json['validation_passed'],
        'expected_header':{'numerator':2,'denominator':10,'rate':0.2}})
    assert package['start_date']=='2026-10-26' and package['end_date']=='2026-11-01'
    assert len(package['daily_snapshots'])==7
    assert quality=={'numerator':2,'denominator':10,'rate':0.2},quality
    assert package['go_no_go_decision']=='pending' and response.json['validation_passed'] is True
    assert unchanged_rows()==before
