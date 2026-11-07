"""B3 correct identity contracts; synthetic metadata only, no system queries."""
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('passive_wms_identity', ROOT/'tools/passive_wms_identity.py')
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def sample():
    root = r'C:\Synthetic Lab\release'
    expected = dict(release_root=root, source_sha='a'*40, python=root+r'\python\python.exe',
                    entry=root+r'\verified_entry.py', task_name='Synthetic-WMS', port=18080)
    action = dict(execute=r'C:\Synthetic Lab\monitor\python.exe',
                  arguments='"C:\\Synthetic Lab\\monitor\\supervise_process.py" --synthetic-only')
    snapshot = dict(port=18080, listeners=[101], task=dict(name='Synthetic-WMS',state='Running',actions=[action]),
                    processes=[dict(pid=101,ppid=100,created_ticks=200,executable=expected['python'],
                                    command='"'+expected['python']+'" "'+expected['entry']+'"'),
                               dict(pid=100,ppid=0,created_ticks=100,executable=action['execute'],
                                    command='"'+action['execute']+'" '+action['arguments'])])
    return snapshot, expected, dict(source_sha='a'*40,ui_sha='a'*40)


def test_check_identity():
    snapshot, expected, manifest = sample()
    before = deepcopy((snapshot,expected,manifest))
    result = identity.check_identity(snapshot,expected,manifest)
    assert result['identity_verified'] is True
    assert result['listener_pid'] == 101 and result['source_sha'] == 'a'*40
    assert result['database_access'] is result['http_request'] is result['service_action'] is False
    assert (snapshot,expected,manifest) == before
    assert '不代表' in result['scope']


@pytest.mark.parametrize('kind', ['other_python','foreign_listener','missing_listener','two_listeners',
    'wrong_entry','wrong_interpreter','wrong_source','wrong_ui','task_stopped','wrong_task',
    'wrong_action','missing_action','two_actions','broken_parent','reused_parent_pid',
    'missing_creation','cycle','duplicate_pid','wrong_port','short_sha','missing_task_name'])
def test_unknown_or_mismatched_identity_is_never_healthy(kind):
    snapshot, expected, manifest = sample()
    child = snapshot['processes'][0]
    if kind == 'other_python': child['command'] = '"'+expected['python']+'" "C:\\Synthetic Lab\\other.py"'
    elif kind == 'foreign_listener': snapshot['listeners'] = [999]
    elif kind == 'missing_listener': snapshot['listeners'] = []
    elif kind == 'two_listeners': snapshot['listeners'] = [101,999]
    elif kind == 'wrong_entry': expected['entry'] = r'C:\Elsewhere\verified_entry.py'
    elif kind == 'wrong_interpreter': child['executable'] = r'C:\Elsewhere\python.exe'
    elif kind == 'wrong_source': manifest['source_sha'] = 'b'*40
    elif kind == 'wrong_ui': manifest['ui_sha'] = 'b'*40
    elif kind == 'task_stopped': snapshot['task']['state'] = 'Ready'
    elif kind == 'wrong_task': snapshot['task']['name'] = 'Another'
    elif kind == 'wrong_action': snapshot['task']['actions'][0]['arguments'] = '"C:\\else.py"'
    elif kind == 'missing_action': snapshot['task']['actions'] = []
    elif kind == 'two_actions': snapshot['task']['actions'] *= 2
    elif kind == 'broken_parent': snapshot['processes'] = [child]
    elif kind == 'reused_parent_pid': snapshot['processes'][1]['created_ticks'] = 201
    elif kind == 'missing_creation': child.pop('created_ticks')
    elif kind == 'cycle': snapshot['processes'][1]['ppid'] = 101
    elif kind == 'duplicate_pid': snapshot['processes'].append(dict(child))
    elif kind == 'wrong_port': snapshot['port'] = 8080
    elif kind == 'short_sha': expected['source_sha'] = 'a'*7
    elif kind == 'missing_task_name': expected.pop('task_name')
    result = identity.check_identity(snapshot,expected,manifest)
    assert result['identity_verified'] is False and result['failures']


def test_read_manifest(tmp_path):
    manifest = tmp_path/'wms-release.json'
    manifest.write_text(json.dumps({'source_sha':'a'*40}),encoding='utf-8-sig')
    assert identity.read_manifest(tmp_path) == {'source_sha':'a'*40}
    manifest.write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError): identity.read_manifest(tmp_path)
    manifest.write_bytes(b'x'*(4*1024*1024+1))
    with pytest.raises(ValueError,match='过大'): identity.read_manifest(tmp_path)


@pytest.mark.parametrize('mode',['exact','wrong_version','unknown_python_option','wrong_state_root'])
def test_controlled_entry_arguments_are_matched_exactly(mode):
    snapshot,expected,manifest = sample()
    expected['entry_arguments'] = '--state-root C:\\Synthetic --version current --serve'
    command = '"'+expected['python']+'" -I -B "'+expected['entry']+'" '+expected['entry_arguments']
    if mode == 'wrong_version': command = command.replace('--version current','--version rollback')
    if mode == 'unknown_python_option': command = command.replace('-I -B','-c')
    if mode == 'wrong_state_root': command = command.replace('C:\\Synthetic --version','C:\\Elsewhere --version')
    snapshot['processes'][0]['command'] = command
    assert identity.check_identity(snapshot,expected,manifest)['identity_verified'] is (mode=='exact')


@pytest.mark.parametrize('kind',['hardlink','reparse','symlink'])
def test_manifest_alias_refused_before_open(tmp_path,monkeypatch,kind):
    manifest = tmp_path/'wms-release.json'
    manifest.write_text('{}',encoding='utf-8')
    original = Path.stat
    def info(path,*args,**kwargs):
        value = original(path,*args,**kwargs)
        if path == manifest:
            return SimpleNamespace(st_mode=0o120777 if kind=='symlink' else value.st_mode,
                st_nlink=2 if kind=='hardlink' else 1,st_file_attributes=0x400 if kind=='reparse' else 0)
        return value
    monkeypatch.setattr(Path,'stat',info)
    with pytest.raises(ValueError): identity.read_manifest(tmp_path)


def test_main_does_not_emit_raw_task_commands(monkeypatch,capsys):
    snapshot,expected,manifest = sample()
    snapshot['task']['actions'][0]['arguments'] += ' --secret=synthetic-never-emit'
    monkeypatch.setattr(sys,'stdin',io.StringIO(json.dumps(dict(snapshot=snapshot,expected=expected))))
    monkeypatch.setattr(identity,'read_manifest',lambda root:manifest)
    assert identity.main() == 1
    output = capsys.readouterr().out
    assert 'synthetic-never-emit' not in output and 'command' not in output
    assert json.loads(output)['identity_verified'] is False


def test_malformed_input_fails_closed(monkeypatch,capsys):
    monkeypatch.setattr(sys,'stdin',io.StringIO('not-json'))
    assert identity.main() == 2
    assert json.loads(capsys.readouterr().out)['identity_verified'] is False
