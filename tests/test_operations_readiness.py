"""Supplied facts only; no live health/database/notification transport."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_readiness():
    spec = importlib.util.spec_from_file_location(
        'isolated_readiness', ROOT / 'app/services/operations_readiness.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('database,backup,free,issues', [
    ('ok', 'success', 100, []),
    ('locked', 'success', 100, ['database_locked']),
    ('schema_missing', 'success', 100, ['database_schema_missing']),
    ('unavailable', 'success', 100, ['database_unavailable']),
    ('unknown', 'success', 100, ['database_unknown']),
    ('ok', 'failure', 100, ['backup_failure']),
    ('ok', 'stale', 100, ['backup_stale']),
    ('ok', 'unknown', 100, ['backup_unknown']),
    ('ok', 'success', 99, ['space_low']),
    ('ok', 'success', None, ['space_unknown']),
    ('ok', 'success', True, ['space_unknown']),
])
def test_assess_readiness(database, backup, free, issues):
    result = load_readiness().assess_readiness(database, backup, free, 100)
    assert result['issues'] == issues
    assert result['status'] == ('not_ready' if issues else 'ready')


def test_assess_readiness_never_echoes_untrusted_evidence():
    value = 'synthetic-secret-token-password-path'
    result = load_readiness().assess_readiness(value, value, -1, 100)
    assert result['issues'] == ['backup_unknown', 'database_unknown', 'space_unknown']
    assert value not in json.dumps(result)


@pytest.mark.parametrize('threshold', [None, 0, True, -1])
def test_assess_readiness_rejects_implicit_threshold(threshold):
    with pytest.raises(ValueError, match='明确的正整数'):
        load_readiness().assess_readiness('ok', 'success', 100, threshold)


def test_alert_transitions():
    module = load_readiness()
    first = module.alert_transitions(None, ['space_low', 'database_locked'])
    assert [e['kind'] for e in first['events']] == ['raised', 'raised']
    assert first['checkpoint'] == {'open_issues': ['database_locked', 'space_low']}
    persisted = json.loads(json.dumps(first['checkpoint']))
    assert module.alert_transitions(persisted, ['database_locked', 'space_low'])['events'] == []
    partial = module.alert_transitions(persisted, ['space_low', 'backup_stale'])
    assert [(e['kind'], e['code']) for e in partial['events']] == [
        ('raised', 'backup_stale'), ('recovered', 'database_locked')]
    healthy = module.alert_transitions(partial['checkpoint'], [])
    assert [(e['kind'], e['code']) for e in healthy['events']] == [
        ('recovered', 'backup_stale'), ('recovered', 'space_low')]
    assert module.alert_transitions(healthy['checkpoint'], [])['events'] == []


@pytest.mark.parametrize('previous', [{}, {'open_issues': 'space_low'},
                                   {'open_issues': ['synthetic-secret']},
                                   {'open_issues': [], 'token': 'synthetic-secret'}])
def test_alert_transitions_invalid_checkpoint_cannot_create_recovery(previous):
    with pytest.raises(ValueError, match='检查点无效') as error:
        load_readiness().alert_transitions(previous, [])
    assert 'synthetic-secret' not in str(error.value)


@pytest.mark.parametrize('issues', [None, 'space_low', [None], ['synthetic-secret']])
def test_alert_transitions_invalid_codes_are_not_sent(issues):
    with pytest.raises(ValueError, match='代码无效') as error:
        load_readiness().alert_transitions(None, issues)
    assert 'synthetic-secret' not in str(error.value)
