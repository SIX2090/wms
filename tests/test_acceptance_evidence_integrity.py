"""Synthetic contracts only; these packages are never production evidence.

AI_FIX_TASK: AI-R18-F01-FIX-20261108-001
"""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from ai.ops import acceptance_evidence as evidence
from ai.ops import launch_acceptance as launch
from ai.ops.business_quality import ALL_METRICS

NOW = datetime(2026, 11, 8, 12)


def cli():
    spec = importlib.util.spec_from_file_location('readiness_integrity', Path(__file__).resolve().parents[1] / 'scripts/verify_production_readiness.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def offline_package():
    gate = cli()
    return {
        'environment': 'production', 'synthetic_sample_count': 0,
        'real_samples': [{'sample_id': f'SYNTHETIC-{i}', 'desensitized': True,
                          'source': sorted(gate.REQUIRED_REAL_SOURCES)[i % 3]} for i in range(20)],
        'daily_snapshots': [{'snapshot_date': f'2026-11-{i:02}',
                            'absolute_counts': dict.fromkeys(gate.ABSOLUTE_METRICS, 0),
                            'rollout_roles': sorted(gate.REQUIRED_ROLES)} for i in range(1, 8)],
        'go_no_go': {'decision': 'go', 'signed_by': 'synthetic-operator', 'decided_at': '2026-11-08T10:00:00'},
    }


def runtime_package():
    counts = dict.fromkeys(launch.ALL_ACCEPTANCE_METRICS, 0)
    quality = {m: {'numerator': 1, 'denominator': 2, 'rate': .5} for m in ALL_METRICS}
    days = [evidence.build_daily_snapshot(snapshot_date=f'2026-11-{i:02}',
        absolute_counts=counts, quality_metrics=quality, rollout_user_count=3,
        rollout_role_count=3, rollout_roles=('admin', 'warehouse', 'purchase'),
        filter_applied={'date': f'2026-11-{i:02}', 'source': 'synthetic', 'model': '', 'prompt_hash': '', 'schema_version': ''}, now=NOW)
        for i in range(1, 8)]
    return evidence.build_evidence_package(package_id='SYNTHETIC-NOT-ACTUAL', daily_snapshots=days,
        rollout_role_matrix=[('admin', True), ('warehouse', True), ('purchase', True)],
        rollback_events=[evidence.RollbackEvidence('synthetic-'+a, a, 1, 'admin',
            '2026-11-07T10:00:00', '2026-11-07T10:01:00', 60) for a in ('shutdown', 'restore')],
        go_no_go_decision='go', decided_by=1, decided_at='2026-11-08T10:00:00', now=NOW)


def test_complete_legacy_formats_still_pass():
    assert cli().validate_evidence(offline_package(), now=NOW) == []
    assert evidence.validate_all_evidence(runtime_package(), now=NOW) == (True, [])


@pytest.mark.parametrize('value', [None, False, True, '0', -1, 0.0, [], {}])
@pytest.mark.parametrize('metric', launch.ALL_ACCEPTANCE_METRICS)
def test_runtime_invalid_or_missing_count_never_passes(metric, value):
    counts = dict.fromkeys(launch.ALL_ACCEPTANCE_METRICS, 0)
    counts[metric] = value
    assert not launch.compute_acceptance_metrics(counts).all_passed
    pkg = runtime_package()
    day = replace(pkg.daily_snapshots[0], absolute_counts=counts)
    assert not evidence.validate_seven_consecutive_days_zero([day, *pkg.daily_snapshots[1:]], now=NOW)[0]


@pytest.mark.parametrize('metric', launch.ALL_ACCEPTANCE_METRICS)
def test_missing_and_nonzero_counts_reject(metric):
    counts = dict.fromkeys(launch.ALL_ACCEPTANCE_METRICS, 0); del counts[metric]
    assert not launch.compute_acceptance_metrics(counts).all_passed
    pkg = runtime_package()
    day = evidence.build_daily_snapshot(snapshot_date='2026-11-01', absolute_counts=counts, quality_metrics={}, now=NOW)
    assert not day.all_absolute_zero
    assert metric not in day.absolute_counts, 'Missing data must remain visibly missing'
    gate = cli(); package = offline_package()
    key = dict(zip(launch.ALL_ACCEPTANCE_METRICS, gate.ABSOLUTE_METRICS))[metric]
    del package['daily_snapshots'][0]['absolute_counts'][key]
    assert gate.validate_evidence(package, now=NOW)
    package['daily_snapshots'][0]['absolute_counts'][key] = 1
    assert gate.validate_evidence(package, now=NOW)


@pytest.mark.parametrize('kind', ['missing_counts', 'counts_container', 'false', 'float', 'non_dict_sample',
    'unhashable_id', 'empty_id', 'duplicate_id', 'not_desensitized', 'missing_source', 'bad_roles',
    'missing_role', 'duplicate_date', 'gap', 'future', 'unfinished', 'bad_date', 'bad_window',
    'signature_type', 'signature_time', 'signature_future', 'signature_before_window', 'empty'])
def test_offline_malformed_evidence_returns_no_go_without_exception(kind):
    package = offline_package()
    day = package['daily_snapshots'][0]
    if kind == 'missing_counts': day['absolute_counts'] = {}
    elif kind == 'counts_container': day['absolute_counts'] = 0
    elif kind in ('false', 'float'): day['absolute_counts']['duplicate_drafts'] = False if kind == 'false' else 0.0
    elif kind == 'non_dict_sample': package['real_samples'][-1] = None
    elif kind == 'unhashable_id': package['real_samples'][0]['sample_id'] = []
    elif kind == 'empty_id': package['real_samples'][0]['sample_id'] = ' '
    elif kind == 'duplicate_id': package['real_samples'][0]['sample_id'] = package['real_samples'][1]['sample_id']
    elif kind == 'not_desensitized': package['real_samples'][0]['desensitized'] = 1
    elif kind == 'missing_source':
        for sample in package['real_samples']: sample['source'] = 'wechat_text'
    elif kind == 'bad_roles': day['rollout_roles'] = [{}]
    elif kind == 'missing_role': day['rollout_roles'] = ['admin', 'warehouse']
    elif kind == 'duplicate_date': package['daily_snapshots'][1]['snapshot_date'] = day['snapshot_date']
    elif kind == 'gap': day['snapshot_date'] = '2026-10-31'
    elif kind in ('future', 'unfinished'):
        start = datetime(2027, 1, 1) if kind == 'future' else NOW-timedelta(days=6)
        for i, item in enumerate(package['daily_snapshots']): item['snapshot_date'] = (start+timedelta(days=i)).date().isoformat()
    elif kind == 'bad_date': day['snapshot_date'] = False
    elif kind == 'bad_window': day['window_hours'] = 1
    elif kind == 'signature_type': package['go_no_go']['signed_by'] = {'name': 'admin'}
    elif kind == 'signature_time': package['go_no_go']['decided_at'] = True
    elif kind == 'signature_future': package['go_no_go']['decided_at'] = '2099-01-01T10:00:00'
    elif kind == 'signature_before_window': package['go_no_go']['decided_at'] = '2026-11-07T10:00:00'
    elif kind == 'empty': package = {}
    assert cli().validate_evidence(package, now=NOW)


@pytest.mark.parametrize('kind', ['missing', 'nonzero', 'today', 'future', 'bad_date', 'window',
                                'summary', 'signer', 'time', 'false_roles', 'missing_daily_role', 'quality', 'premature_capture'])
def test_runtime_go_rechecks_actual_details(kind):
    pkg = runtime_package(); days = list(pkg.daily_snapshots); day = days[0]
    if kind in ('missing', 'nonzero'):
        counts = dict(day.absolute_counts)
        if kind == 'missing': del counts['duplicate_drafts']
        else: counts['duplicate_drafts'] = 1
        days[0] = replace(day, absolute_counts=counts)
    elif kind in ('today', 'future', 'bad_date'):
        days[-1] = replace(days[-1], snapshot_date={'today':'2026-11-08','future':'2099-01-01','bad_date':'x'}[kind])
    elif kind == 'window': days[0] = replace(day, window_hours=True)
    elif kind == 'summary': pkg = replace(pkg, seven_day_summary={'all_absolute_zero': True})
    elif kind == 'signer': pkg = replace(pkg, decided_by=True)
    elif kind == 'time': pkg = replace(pkg, decided_at=None)
    elif kind == 'false_roles': pkg = replace(pkg, rollout_role_matrix=(('admin', False), ('warehouse', False), ('purchase', False)))
    elif kind == 'missing_daily_role': days[0] = replace(day, rollout_roles=('admin',), rollout_role_count=1)
    elif kind == 'quality': days[0] = replace(day, quality_metrics={})
    elif kind == 'premature_capture': days[0] = replace(day, generated_at='2026-11-01T12:00:00')
    pkg = replace(pkg, daily_snapshots=tuple(days))
    assert not evidence.validate_all_evidence(pkg, now=NOW)[0]


def test_zero_denominator_is_uncovered_and_weighted_summary_is_recomputed():
    pkg = runtime_package(); days = list(pkg.daily_snapshots)
    quality = {m: {'numerator': 0, 'denominator': 0, 'rate': 0.0} for m in ALL_METRICS}
    days[0] = replace(days[0], quality_metrics=quality)
    result = evidence.build_evidence_package(package_id='synthetic-weighted', daily_snapshots=days, rollout_role_matrix=[])
    assert all(m['numerator'] == 6 and m['denominator'] == 12 and m['rate'] == .5 for m in result.seven_day_summary['quality_summary'].values())
    assert not evidence.validate_evidence_reproducible(replace(result, seven_day_summary=pkg.seven_day_summary))[0]


def test_replay_is_not_a_duplicate_business_document_and_window_is_half_open():
    start = datetime(2026, 11, 1); end = start + timedelta(days=1)
    def row(i, at, draft, status='completed', job=1):
        return SimpleNamespace(id=i, created_at=at, status=status, user_id=1, capability='in_order',
            document_job_id=job, idempotency_key=str(i), draft_type='in_order', draft_id=draft)
    original = row(1, start-timedelta(seconds=1), 10)
    replay = row(2, start, 10, 'replayed')
    legacy_intercept = row(3, start, None, 'replayed')
    assert launch.count_duplicate_draft_receipts([original, replay, legacy_intercept], start, end) == 0
    extra = row(4, start, 11)
    next_day = row(5, end, 12)
    other_job = row(6, start, 20, job=2)
    assert launch.count_duplicate_draft_receipts([extra, original, replay, next_day, other_job], start, end) == 1
    assert launch.count_duplicate_draft_receipts([row(7, start, None)], start, end) is None
