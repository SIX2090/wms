"""Synthetic evidence must be complete before the existing manual signature."""
from datetime import date, datetime, timedelta
import json

import pytest
import app as wms
from ai.ops.acceptance_evidence import RollbackEvidence
from ai.ops.launch_acceptance import ALL_ACCEPTANCE_METRICS
from ai.ops.business_quality import ALL_METRICS, QualitySample, compare_versions


@pytest.fixture
def evidence_client(monkeypatch):
    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.drop_all(); wms.db.create_all()
        user=wms.User(username='SYNTHETIC-EVIDENCE',password_hash='unusable-test-hash',role='admin',must_change_password=False)
        wms.db.session.add(user); wms.db.session.commit()
        client=wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id']=str(user.id);session['_fresh']=True
        monkeypatch.setattr(wms,'_ai_f02_query_rollout_info',lambda:{'roles':('admin','warehouse','purchase'),'user_count':1,'role_count':3})
        monkeypatch.setattr(wms,'_ai_f02_query_rollback_events',lambda *_:[
            RollbackEvidence(action,action,user.id,'admin','2026-10-31T10:00:00','2026-10-31T10:01:00',60)
            for action in ('shutdown','restore')])
        yield client
        wms.db.session.remove(); wms.db.drop_all()


def seed_snapshots(days=7, gap=False, violation=0):
    for offset in range(days):
        counts={key:0 for key in ALL_ACCEPTANCE_METRICS}
        if offset==0:counts[ALL_ACCEPTANCE_METRICS[0]]=violation
        target=date.today()-timedelta(days=offset+(1 if gap and offset==6 else 0))
        wms.db.session.add(wms.AIAcceptanceDailySnapshot(snapshot_date=target.isoformat(),absolute_counts=json.dumps(counts),
            quality_metrics=json.dumps({key:{'numerator':8,'denominator':10,'rate':0.8} for key in ALL_METRICS}),
            rollout_user_count=1,rollout_role_count=3,rollout_roles='["admin","warehouse","purchase"]',
            window_hours=24,filter_applied='{"source":"SYNTHETIC-TEST"}',generated_at=datetime.now()))
    wms.db.session.commit()


def build(client,days=7):
    response=client.post('/api/ai/acceptance/evidence_package',json={'days':days})
    assert response.status_code==200,response.get_json()
    return response.get_json()


def sign(client,pkg,decision='go',reason='SYNTHETIC ONLY'):
    return client.post('/api/ai/acceptance/go_no_go',json={'package_id':pkg['package_db_id'],'decision':decision,'reason':reason})


def test_complete_unsigned_package_is_ready_then_signed(evidence_client):
    seed_snapshots()
    pkg=build(evidence_client)
    assert pkg['validation_passed'] is True,pkg['validation_failures']
    assert pkg['package']['go_no_go_decision']=='pending'
    response=sign(evidence_client,pkg)
    assert response.status_code==200,response.get_json()
    row=wms.db.session.get(wms.AIAcceptanceEvidencePackage,pkg['package_db_id'])
    assert row.go_no_go_decision=='go' and row.decided_at and row.decided_by


def test_acceptance_page_initializes_after_shared_api_client(evidence_client):
    response=evidence_client.get('/ai/acceptance?embedded=1')
    assert response.status_code==200
    page=response.get_data(as_text=True)
    assert page.index('js/api.js') < page.index('const state = {snapshots:')


@pytest.mark.parametrize('days,gap,violation',[(1,False,0),(7,True,0),(7,False,1)])
def test_incomplete_or_nonzero_package_cannot_go(evidence_client,days,gap,violation):
    seed_snapshots(days,gap,violation)
    pkg=build(evidence_client)
    response=sign(evidence_client,pkg)
    assert response.status_code==400,response.get_json()
    assert wms.db.session.get(wms.AIAcceptanceEvidencePackage,pkg['package_db_id']).go_no_go_decision=='pending'


@pytest.mark.parametrize('reason',['','   '])
def test_no_go_requires_reason_in_backend(evidence_client,reason):
    seed_snapshots();pkg=build(evidence_client)
    assert sign(evidence_client,pkg,'no_go',reason).status_code==400


def test_invalid_package_can_be_rejected_with_reason(evidence_client):
    seed_snapshots(1,violation=1);pkg=build(evidence_client)
    assert sign(evidence_client,pkg,'no_go','SYNTHETIC incomplete evidence').status_code==200


def test_missing_rollback_and_changed_snapshot_cannot_go(evidence_client):
    seed_snapshots();pkg=build(evidence_client)
    row=wms.db.session.get(wms.AIAcceptanceEvidencePackage,pkg['package_db_id'])
    row.rollback_events='[]';wms.db.session.commit()
    assert sign(evidence_client,pkg).status_code==400
    snapshot=wms.AIAcceptanceDailySnapshot.query.first()
    snapshot.absolute_counts=json.dumps({key:1 for key in ALL_ACCEPTANCE_METRICS});wms.db.session.commit()
    assert sign(evidence_client,pkg).status_code==400


def test_two_builds_at_same_second_have_distinct_ids(evidence_client,monkeypatch):
    seed_snapshots()
    class Frozen(datetime):
        @classmethod
        def now(cls,tz=None):return cls.combine(date.today(),datetime.min.time()).replace(hour=12)
    monkeypatch.setattr(wms,'datetime',Frozen)
    first=build(evidence_client);second=build(evidence_client)
    assert first['package_db_id']!=second['package_db_id']
    assert first['package']['package_id']!=second['package']['package_id']


@pytest.mark.parametrize('current,baseline,is_regression',[(1,4,False),(4,1,True),(2,2,False)])
def test_correction_rate_direction(current,baseline,is_regression):
    def sample(corrected):
        return QualitySample('SYN','2026-10-31','admin','fixture','fixture','fixture','fixture',field_total=10,field_corrected=corrected)
    result=compare_versions([sample(current)],[sample(baseline)],current_version='current',baseline_version='base')
    assert ('human_correction_rate' in result.regressions) is is_regression
    assert result.deltas['human_correction_rate']==pytest.approx((current-baseline)/10)


def test_quality_feedback_detail_reads_real_corrected_field(evidence_client):
    wms.db.session.add(wms.AIFieldFeedback(user_id=1,source='SYNTHETIC',field_name='name',original_value='SYN-OLD',corrected_value='SYN-NEW',adopted=True))
    wms.db.session.commit()
    response=evidence_client.post('/api/ai/business_quality_drilldown',json={'dimension':'source','value':'SYNTHETIC'})
    assert response.status_code==200,response.get_json()
    assert len(response.get_json()['samples'])==1
    assert response.get_json()['samples'][0]['confirmed_value']=='SYN-***'
    assert response.get_json()['samples'][0]['confidence'] is None
    assert response.get_json()['samples'][0]['document_job_id'] is None


@pytest.mark.parametrize('value,prefix,suffix,expected',[
    ('SYN-SECRET',4,0,'SYN-***'),('SYN-SECRET',0,3,'***RET'),
    ('SYN-SECRET',0,0,'***'),('ABC',4,0,'***'),('',4,0,''),
])
def test_mask_text_preserves_only_explicit_ends(value,prefix,suffix,expected):
    from ai.security import mask_text
    assert mask_text(value,prefix,suffix)==expected
