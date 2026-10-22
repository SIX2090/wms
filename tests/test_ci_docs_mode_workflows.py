"""BUG-2026-10-22-016: execute the actual workflow aggregation programs.

The full-job snapshots preserve the existing validation payload during routing changes.
An intentional future full-job change must review and update its snapshot.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FULL = {
    'ci': ['lint-and-static', 'unit-tests-shard-0', 'unit-tests-shard-1', 'unit-tests-shard-2',
           'verify-shard-0', 'verify-shard-1', 'verify-shard-2', 'verify-shard-3', 'smoke'],
    'verify': ['static-checks', 'ai-core'],
    'perf': ['perf'],
}
DOCS = {'ci': 'docs-checks', 'verify': 'docs-checks', 'perf': 'docs-skip'}
FULL_IF = "${{ github.event_name != 'push' || github.ref != 'refs/heads/main' || needs.changes.outputs.docs_only != 'true' }}"
DOCS_IF = "${{ github.event_name == 'push' && github.ref == 'refs/heads/main' && needs.changes.outputs.docs_only == 'true' }}"


def workflow(name):
    return yaml.safe_load((ROOT / '.github/workflows' / (name + '.yml')).read_text(encoding='utf-8'))


@pytest.mark.parametrize('name', FULL)
def test_trigger_classifier_and_parallel_routing(name):
    data = workflow(name)
    triggers = data.get('on', data.get(True))
    expected_events = {'push', 'schedule', 'workflow_dispatch'}
    if name != 'perf':
        expected_events.add('pull_request')
    assert expected_events <= triggers.keys()
    for event in expected_events & {'push', 'pull_request'}:
        assert triggers[event]['branches'] == ['main']
        assert not {'paths', 'paths-ignore'} & triggers[event].keys()
    assert triggers['schedule']
    jobs = data['jobs']
    assert set(jobs) == {'changes', DOCS[name], 'gate', *FULL[name]}
    changes = jobs['changes']
    assert changes.get('needs') is None
    assert changes['permissions'] == {'contents': 'read', 'actions': 'read'}
    assert changes['steps'][0]['with']['fetch-depth'] == 0
    assert changes['steps'][1]['with']['python-version'] == '3.11'
    assert all('pip install' not in s.get('run', '') for s in changes['steps'])
    step = changes['steps'][2]
    assert step['id'] == 'scope'
    assert step['env']['GITHUB_TOKEN'] == '${{ github.token }}'
    assert step['run'] == 'python scripts/ci_change_scope.py --event-file "$GITHUB_EVENT_PATH" --github-output "$GITHUB_OUTPUT"'
    for output in ('docs_only', 'mode', 'reason'):
        assert changes['outputs'][output] == '${{ steps.scope.outputs.' + output + ' }}'
    for job in FULL[name]:
        assert jobs[job]['needs'] == 'changes'
        assert jobs[job]['if'] == FULL_IF
    assert jobs[DOCS[name]]['needs'] == 'changes'
    assert jobs[DOCS[name]]['if'] == DOCS_IF
    assert jobs['gate']['if'] == '${{ always() }}'
    assert set(jobs['gate']['needs']) == {'changes', DOCS[name], *FULL[name]}


def test_document_checks_keep_contracts_secrets_rules_and_strict_ledger():
    jobs = workflow('ci')['jobs']
    docs = jobs['docs-checks']
    assert docs['steps'][0]['with']['fetch-depth'] == 0
    commands = '\n'.join(step.get('run', '') for step in docs['steps'])
    for module in ('test_f4_4_ledger_split.py', 'test_inventory_truth_line_refs.py',
                   'test_audit_readme_inventory_identity.py'):
        assert 'tests/' + module in commands
    assert '--noconftest' in commands
    assert 'scripts/lint_wms_rules.py --full --full-gate' in commands
    secrets = [step for step in jobs['lint-and-static']['steps'] if 'gitleaks' in step.get('name', '')]
    assert len(secrets) == 1
    assert secrets[0] in docs['steps']
    assert '--config .gitleaks.toml --redact --verbose' in secrets[0]['run']
    assert all(not step.get('continue-on-error', False) for step in docs['steps'])
    ai = workflow('verify')['jobs']['docs-checks']['steps']
    ledger = [s for s in ai if 'verify_ai_ledger_consistency.py' in s.get('run', '')]
    assert len(ledger) == 1
    assert ledger[0]['env']['AI_LEDGER_ENFORCE'] == 'strict'
    assert any('verify_source_encoding.py' in s.get('run', '') for s in ai)
    perf = workflow('perf')['jobs']
    assert perf['perf']['continue-on-error'] is True
    assert 'performance' in perf['docs-skip']['steps'][0]['run'].lower()


def run_gate(name, needs, event='push', ref='refs/heads/main'):
    step = workflow(name)['jobs']['gate']['steps'][0]
    assert step['env'] == {'NEEDS_JSON': '${{ toJSON(needs) }}',
                           'EVENT_NAME': '${{ github.event_name }}', 'REF_NAME': '${{ github.ref }}'}
    match = re.fullmatch("python - <<'PY'\n(.*?)\nPY\\s*", step['run'], flags=re.S)
    assert match, 'Run the actual Python heredoc, not a test reimplementation'
    env = dict(os.environ, NEEDS_JSON=json.dumps(needs), EVENT_NAME=event, REF_NAME=ref)
    return subprocess.run([sys.executable, '-c', match.group(1)], env=env,
                          capture_output=True, text=True, timeout=10)


def results(name, docs):
    return {'changes': {'result': 'success', 'outputs': {'docs_only': 'true' if docs else 'false'}},
            DOCS[name]: {'result': 'success' if docs else 'skipped'},
            **{key: {'result': 'skipped' if docs else 'success'} for key in FULL[name]}}


@pytest.mark.parametrize('name', FULL)
@pytest.mark.parametrize('docs', [True, False])
def test_actual_gate_accepts_only_selected_successes(name, docs):
    result = run_gate(name, results(name, docs))
    assert result.returncode == 0, result.stderr
    assert ('docs' if docs else 'full') + ': all required checks succeeded' in result.stdout


@pytest.mark.parametrize('name', FULL)
@pytest.mark.parametrize('docs', [True, False])
@pytest.mark.parametrize('bad', ['failure', 'skipped', 'cancelled', 'missing'])
def test_actual_gate_rejects_each_missing_or_unsuccessful_required_job(name, docs, bad):
    for key in ['changes', *([DOCS[name]] if docs else FULL[name])]:
        needs = results(name, docs)
        if bad == 'missing':
            del needs[key]
        else:
            needs[key]['result'] = bad
        result = run_gate(name, needs)
        if name == 'perf' and not docs and key == 'perf' and bad == 'failure':
            assert result.returncode == 0
            assert '::warning::' in result.stdout
        else:
            assert result.returncode != 0, (name, docs, key, bad, result.stdout)


@pytest.mark.parametrize('name', FULL)
@pytest.mark.parametrize('output', ['', None, 'garbage', 'TRUE'])
def test_actual_gate_unknown_output_requires_full_validation(name, output):
    needs = results(name, False)
    needs['changes']['outputs']['docs_only'] = output
    assert run_gate(name, needs).returncode == 0
    needs[FULL[name][0]]['result'] = 'skipped'
    assert run_gate(name, needs).returncode != 0


@pytest.mark.parametrize('name', FULL)
@pytest.mark.parametrize('event,ref', [('schedule', 'refs/heads/main'),
    ('pull_request', 'refs/pull/1/merge'), ('workflow_dispatch', 'refs/heads/main'),
    ('push', 'refs/heads/other')])
def test_actual_gate_forces_full_for_non_main_push_even_if_output_says_docs(name, event, ref):
    needs = results(name, False)
    needs['changes']['outputs']['docs_only'] = 'true'
    assert run_gate(name, needs, event, ref).returncode == 0
    needs[FULL[name][0]]['result'] = 'skipped'
    assert run_gate(name, needs, event, ref).returncode != 0


FULL_JOB_SNAPSHOTS = {'ci': {'lint-and-static': 'e29a066ab39791082a86d43dd35166f36b9884be44f9832f46c6f41dc3601cfa', 'unit-tests-shard-0': '0a26f1fc07866a57ed15c79d4a93f4d689ea4b0b553c9f838f0c3c192517d8f9', 'unit-tests-shard-1': 'dbc2b587545ac865df0dff025863238f74fd591662e579dfa24f2cb61f2963d6', 'unit-tests-shard-2': 'a175c814841f13c705777a8bd9795189a93fd8de18de10aa464e8f4d69186d4f', 'verify-shard-0': '756f4cd0965ffc090d3b83efa017e5388e50c2e6a788443f62910de45a7f20d8', 'verify-shard-1': '5f672c414cad0f85c77370f8f8eabbe5a5321d19b55a3da9130f946c61f9c219', 'verify-shard-2': '7fe22c8604b138a0f1502b50368e096443d2102a350194914b69d9a4bfd25297', 'verify-shard-3': '9e4d7e9e118b436d95d7a7b2e696e272f275e839bb4d16fa177127612a15b7bc', 'smoke': 'e11741363cf8b8bee6ceb7296ac9b1d53a5043abc3df6881a5ce06967d768f1d'}, 'verify': {'static-checks': 'aeb6c1ab08dae83ce1519272efe117fe27845b9004ab995a33ec9acda8986685', 'ai-core': 'dc9740e367698278609cbaf79f79c64fc0aeb71a7afc22c781a0d5dd1e5471cc'}, 'perf': {'perf': 'c68500bafe6b1f7d3bf444fe69a9c4d0df27eca54c229520c079831394ad2997'}}


@pytest.mark.parametrize('name', FULL)
def test_original_full_validation_payloads_are_preserved(name):
    jobs = workflow(name)['jobs']
    for key, expected in FULL_JOB_SNAPSHOTS[name].items():
        job = copy.deepcopy(jobs[key])
        job.pop('needs', None)
        job.pop('if', None)
        actual = hashlib.sha256(json.dumps(job, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        assert actual == expected, key


def test_performance_advisory_never_hides_classifier_or_docs_failure():
    needs = results('perf', False)
    needs['perf']['result'] = 'failure'
    result = run_gate('perf', needs)
    assert result.returncode == 0
    assert '::warning::Performance baseline failed' in result.stdout
    needs['changes']['result'] = 'failure'
    assert run_gate('perf', needs).returncode != 0
    needs = results('perf', True)
    needs['docs-skip']['result'] = 'failure'
    assert run_gate('perf', needs).returncode != 0
