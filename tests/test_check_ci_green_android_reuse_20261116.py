"""Real private Git objects + mocked Actions API; no WMS, network or credentials."""
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import types
import urllib.error
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/check_ci_green.py'
ANDROID = 'android-build.yml'
INPUTS = ('app/android-native-wms/fixture.txt', '.github/workflows/android-build.yml',
          '.github/workflows/android-update-promote.yml', 'scripts/android_update_release.py',
          'scripts/android_update_channel.py', 'scripts/prepare_android_signing.py')


def git(repo, *args, check=True):
    env = {**os.environ, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
           'GIT_CONFIG_SYSTEM': os.devnull, 'GIT_NO_LAZY_FETCH': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    result = subprocess.run(['git', '-c', 'core.hooksPath=', '-c', 'commit.gpgsign=false',
                             '-c', 'user.name=CI Fixture', '-c', 'user.email=ci@example.invalid', *args],
                            cwd=repo, env=env, capture_output=True, text=True, timeout=20)
    if check:
        assert result.returncode == 0, result.stderr
    return result.stdout.strip() if check else result


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / 'history'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    def commit(relative, content):
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding='utf-8')
        git(repo, 'add', '--', relative)
        git(repo, 'commit', '-qm', 'synthetic fixture')
        return git(repo, 'rev-parse', 'HEAD')
    for number, relative in enumerate(INPUTS):
        file = repo / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text('input-' + str(number), encoding='utf-8')
    git(repo, 'add', '--', *INPUTS)
    git(repo, 'commit', '-qm', 'Android input change')
    source = git(repo, 'rev-parse', 'HEAD')
    built = commit('docs/first.txt', 'built after input change')
    unbuilt = commit('docs/second.txt', 'no build here')
    target = commit('docs/target.txt', 'accepted target')
    future = commit(INPUTS[0], 'a later task changed Android')
    return types.SimpleNamespace(repo=repo, source=source, built=built, unbuilt=unbuilt,
                                 target=target, future=future, commit=commit)


@pytest.fixture
def gate(monkeypatch, history):
    def refuse(*args, **kwargs):
        raise AssertionError('This test forbids network access')
    monkeypatch.setattr(socket.socket, 'connect', refuse)
    monkeypatch.setattr(socket, 'getaddrinfo', refuse)
    module = types.ModuleType('ci_reuse_contract')
    # Old bytes run at the same legitimate script location, so their stdlib HTTP
    # helper import works. Old-red must be a business assertion, never ImportError.
    module.__file__ = str(SCRIPT)
    source = Path(os.environ.get('WMS_GATE_TEST_SOURCE', str(SCRIPT))).read_text(encoding='utf-8-sig')
    exec(compile(source, str(SCRIPT), 'exec'), module.__dict__)
    module.ROOT = history.repo
    module.resolve_token = lambda: None
    return module


def run_record(sha, status='completed', conclusion='success', branch='main'):
    return {'head_sha': sha, 'head_branch': branch, 'status': status, 'conclusion': conclusion,
            'run_number': 42, 'html_url': 'https://example.invalid/run/42'}


def invoke(gate, history, monkeypatch, android=None, *, errors=None, target=None):
    android = android or {}
    errors = errors or {}
    selected = target or history.target
    calls = []
    def api(path, token):
        assert token is None, 'No credential resolver may run'
        parsed = urllib.parse.urlparse(path)
        query = urllib.parse.parse_qs(parsed.query)
        assert query['branch'] == ['main'] and query['per_page'] == ['1']
        sha = query['head_sha'][0]
        assert len(sha) == 40
        workflow = parsed.path.split('/workflows/')[1].split('/')[0]
        calls.append((workflow, sha))
        if (workflow, sha) in errors:
            raise errors[(workflow, sha)]
        if workflow != ANDROID:
            return {'workflow_runs': [run_record(selected)]}
        record = android.get(sha)
        return {'workflow_runs': [record] if record is not None else []}
    monkeypatch.setattr(gate, 'gh_get', api)
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT), '--json', '--target-sha', selected])
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        result = gate.main()
    return result, json.loads(stream.getvalue()), calls


def test_main_uses_later_built_ancestor(gate, history, monkeypatch):
    """The input-changing commit has no run; a later unchanged ancestor does."""
    result, payload, calls = invoke(gate, history, monkeypatch,
                                    {history.built: run_record(history.built)})
    assert result == 0 and payload['ok'], (payload, calls)
    assert payload['results'][0]['head_sha_full'] == history.built
    assert calls[:3] == [(ANDROID, history.target), (ANDROID, history.unbuilt), (ANDROID, history.built)]
    assert all(sha != history.future for _, sha in calls)


def test_last_input_commit_remains_a_valid_candidate(gate, history, monkeypatch):
    result, payload, _ = invoke(gate, history, monkeypatch,
                                {history.source: run_record(history.source)})
    assert result == 0 and payload['results'][0]['head_sha_full'] == history.source, payload


@pytest.mark.parametrize('status,conclusion,state', [('completed', 'failure', 'failed'),
                                                  ('in_progress', None, 'pending'),
                                                  ('queued', None, 'pending')])
def test_first_ancestor_with_a_run_keeps_its_latest_non_green(status, conclusion, state, gate, history, monkeypatch):
    result, payload, calls = invoke(gate, history, monkeypatch, {
        history.built: run_record(history.built, status, conclusion),
        history.source: run_record(history.source),
    })
    assert result == 1 and payload['results'][0]['state'] == state, (payload, calls)
    assert (ANDROID, history.source) not in calls, 'An ancestor failure/pending must not fall through to older green'


@pytest.mark.parametrize('status,conclusion,state', [('completed', 'failure', 'failed'),
                                                  ('in_progress', None, 'pending'),
                                                  ('completed', 'success', 'green')])
def test_target_run_never_enters_ancestor_fallback(status, conclusion, state, gate, history, monkeypatch):
    result, payload, calls = invoke(gate, history, monkeypatch, {
        history.target: run_record(history.target, status, conclusion),
        history.built: run_record(history.built),
    })
    assert payload['results'][0]['state'] == state and result == (0 if state == 'green' else 1)
    assert [sha for workflow, sha in calls if workflow == ANDROID] == [history.target]


def test_ancestor_query_error_cannot_fall_through_to_old_green(gate, history, monkeypatch):
    error = urllib.error.HTTPError('https://example.invalid', 403, 'synthetic API error', {}, None)
    result, payload, calls = invoke(gate, history, monkeypatch,
                                    {history.source: run_record(history.source)},
                                    errors={(ANDROID, history.built): error})
    assert result == 1 and payload['results'][0]['state'] == 'missing' and payload['api_error']
    assert (ANDROID, history.source) not in calls


@pytest.mark.parametrize('replacement', ['source', 'future', 'wrong-branch', 'short-sha'])
def test_ancestor_response_is_bound_to_queried_sha_and_main(replacement, gate, history, monkeypatch):
    record = run_record(history.source if replacement == 'source' else history.future)
    if replacement == 'wrong-branch':
        record = run_record(history.built, branch='feature/untrusted')
    if replacement == 'short-sha':
        record = run_record('abc')
    result, payload, calls = invoke(gate, history, monkeypatch,
                                    {history.built: record, history.source: run_record(history.source)})
    assert result == 1 and payload['results'][0]['state'] == 'missing'
    assert (ANDROID, history.source) not in calls


def test_target_response_cannot_masquerade_as_an_older_green(gate, history, monkeypatch):
    result, payload, calls = invoke(gate, history, monkeypatch,
                                    {history.target: run_record(history.built)})
    assert result == 1 and payload['results'][0]['state'] == 'missing'
    assert [sha for workflow, sha in calls if workflow == ANDROID] == [history.target]


def test_no_ancestor_runs_remains_missing(gate, history, monkeypatch):
    result, payload, _ = invoke(gate, history, monkeypatch)
    assert result == 1 and payload['results'][0]['state'] == 'missing'


@pytest.mark.parametrize('relative', INPUTS)
def test_each_of_six_android_inputs_must_be_unchanged(relative, gate, history, monkeypatch):
    target = history.commit(relative, 'changed current Android input')
    ok, detail = gate.android_reuse_check(history.built, target)
    assert not ok and '已变化' in detail
    result, payload, _ = invoke(gate, history, monkeypatch,
                                {history.built: run_record(history.built)}, target=target)
    assert result == 1 and payload['results'][0]['state'] == 'missing'


def test_unchanged_tree_with_a_missing_blob_is_unverified(gate, history, monkeypatch):
    oid = git(history.repo, 'rev-parse', history.target + ':' + INPUTS[0])
    object_path = history.repo / '.git/objects' / oid[:2] / oid[2:]
    assert object_path.resolve().is_relative_to((history.repo / '.git/objects').resolve())
    assert object_path.is_file()
    object_path.chmod(stat.S_IREAD | stat.S_IWRITE)  # Git marks its own loose objects readonly on Windows.
    object_path.unlink()  # Only this fresh temporary fixture's loose object.
    result, payload, _ = invoke(gate, history, monkeypatch,
                                {history.source: run_record(history.source)})
    assert result == 1 and payload['results'][0]['state'] == 'missing'


def test_shallow_history_cannot_prove_reuse(gate, history, tmp_path):
    clone = tmp_path / 'shallow'
    git(tmp_path, 'clone', '-q', '--depth=1', history.repo.as_uri(), str(clone))
    gate.ROOT = clone
    head = git(clone, 'rev-parse', 'HEAD')
    ok, detail = gate.android_reuse_check(head, head)
    assert not ok and '未核实' in detail


def test_missing_commit_objects_remain_unverified(gate, history):
    ok, detail = gate.android_reuse_check('1' * 40, history.target)
    assert not ok and '缺少' in detail


def test_real_long_ancestor_history_is_bounded(gate, history, monkeypatch):
    parent = history.target
    tree = git(history.repo, 'rev-parse', parent + '^{tree}')
    for number in range(200):
        parent = git(history.repo, 'commit-tree', tree, '-p', parent, '-m', 'unbuilt docs ' + str(number))
    result, payload, calls = invoke(gate, history, monkeypatch,
                                    {history.source: run_record(history.source)}, target=parent)
    assert result == 1 and payload['results'][0]['state'] == 'missing'
    assert [sha for workflow, sha in calls if workflow == ANDROID] == [parent]
