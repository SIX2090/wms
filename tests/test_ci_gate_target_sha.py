"""Target-specific CI evidence and actual pre-push remote-baseline behavior."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / 'scripts/check_ci_green.py'
HOOK = ROOT / '.githooks/pre-push'
TARGET = 'a' * 40
OLD = 'b' * 40
LOCAL = 'c' * 40


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location('target_gate_under_test', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def good_run(sha=TARGET, **changes):
    return dict(status='completed',conclusion='success',head_sha=sha,head_branch='main',html_url='https://example.invalid/run/7',run_number=7,**changes)


def invoke(gate,monkeypatch,capsys,runs=None,target=TARGET):
    monkeypatch.setattr(gate,'resolve_token',lambda:None)
    if runs is None:
        runs={wf:good_run() for _,wf in gate.REQUIRED_WORKFLOWS}
    monkeypatch.setattr(gate,'latest_run',lambda wf,token:runs[wf])
    monkeypatch.setattr(sys,'argv',[str(CHECKER),'--json']+(['--target-sha',target] if target else []))
    rc=gate.main()
    return rc,json.loads(capsys.readouterr().out)


def test_explicit_target_does_not_resolve_local_or_remote_head(gate,monkeypatch,capsys):
    monkeypatch.setattr(gate,'resolve_target_sha',lambda token:pytest.fail('explicit baseline needs no extra ref request'))
    rc,data=invoke(gate,monkeypatch,capsys)
    assert rc==0 and data['ok']
    assert data['target_sha']==TARGET and data['target_source']=='explicit'
    assert all(r['head_sha_full']==TARGET for r in data['results'])


def test_default_target_reads_fresh_remote_main_not_local_head(gate,monkeypatch,capsys):
    calls=[]
    def remote(path,token):
        calls.append(path)
        assert path=='/repos/SIX2090/wms/branches/main'
        return {'commit':{'sha':TARGET}}
    monkeypatch.setattr(gate,'gh_get',remote)
    rc,data=invoke(gate,monkeypatch,capsys,target=None)
    assert rc==0 and data['target_sha']==TARGET
    assert calls==['/repos/SIX2090/wms/branches/main']
    assert data['target_source']=='remote_main_api'


@pytest.mark.parametrize('wf',['.github/workflows/ci.yml','.github/workflows/verify.yml'])
def test_old_green_is_not_current_target_evidence(gate,monkeypatch,capsys,wf):
    runs={name:good_run() for _,name in gate.REQUIRED_WORKFLOWS}
    runs[wf]=good_run(OLD)
    rc,data=invoke(gate,monkeypatch,capsys,runs)
    result=next(r for r in data['results'] if r['file']==wf)
    assert rc==1 and not data['ok']
    assert result['state']=='missing' and '不一致' in result['detail']


@pytest.mark.parametrize('workflow',[0,1,2])
@pytest.mark.parametrize('status,conclusion',[('completed','failure'),('in_progress',None),('queued',None),('completed','cancelled')])
def test_latest_failure_or_pending_blocks_even_when_an_older_sha(workflow,status,conclusion,gate,monkeypatch,capsys):
    runs={wf:good_run() for _,wf in gate.REQUIRED_WORKFLOWS}
    wf=gate.REQUIRED_WORKFLOWS[workflow][1]
    runs[wf]={'status':status,'conclusion':conclusion,'head_sha':OLD,'head_branch':'main'}
    monkeypatch.setattr(gate,'android_reuse_check',lambda *args:pytest.fail('non-green run cannot be reused'))
    rc,data=invoke(gate,monkeypatch,capsys,runs)
    result=next(r for r in data['results'] if r['file']==wf)
    assert rc==1
    assert result['state']==('pending' if status!='completed' else 'failed')


@pytest.mark.parametrize('code',[401,403,404,429])
def test_api_query_failure_is_unverified_not_a_failed_workflow(gate,monkeypatch,capsys,code):
    def unavailable(wf,token):
        raise urllib.error.HTTPError('https://example.invalid',code,'query unavailable',{},None)
    monkeypatch.setattr(gate,'resolve_token',lambda:None)
    monkeypatch.setattr(gate,'latest_run',unavailable)
    monkeypatch.setattr(sys,'argv',[str(CHECKER),'--json','--target-sha',TARGET])
    assert gate.main()==1
    data=json.loads(capsys.readouterr().out)
    assert not data['ok'] and data['api_error']
    assert all(r['state']=='missing' and '未核实' in r['detail'] for r in data['results'])


def test_unknown_remote_target_cannot_pass_with_green_runs(gate,monkeypatch,capsys):
    def unavailable(token):
        raise urllib.error.URLError('offline')
    monkeypatch.setattr(gate,'resolve_target_sha',unavailable)
    rc,data=invoke(gate,monkeypatch,capsys,target=None)
    assert rc==1 and data['target_sha'] is None
    assert all(r['state']=='missing' for r in data['results'])


@pytest.mark.parametrize('value',['abc','--help','a'*39,'a'*41,'g'*40,'0'*40,'a'*40+';echo nope'])
def test_target_argument_rejects_abbreviations_options_and_injection(gate,monkeypatch,value):
    monkeypatch.setattr(sys,'argv',[str(CHECKER),'--target-sha',value])
    with pytest.raises(SystemExit) as error:
        gate.main()
    assert error.value.code==2


@pytest.mark.parametrize('changes',[{'head_sha':'abc'},{'head_sha':None},{'head_branch':'feature/not-main'}])
def test_malformed_run_identity_is_not_green_evidence(gate,monkeypatch,capsys,changes):
    runs={wf:good_run() for _,wf in gate.REQUIRED_WORKFLOWS}
    runs['.github/workflows/ci.yml'].update(changes)
    rc,data=invoke(gate,monkeypatch,capsys,runs)
    assert rc==1
    assert next(r for r in data['results'] if r['file'].endswith('/ci.yml'))['state']=='missing'


def git(repo,*args):
    result=subprocess.run(['git','-c','core.hooksPath=','-c','commit.gpgsign=false',*args],cwd=repo,capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stderr
    return result.stdout.strip()


@pytest.fixture
def history(tmp_path):
    repo=tmp_path/'history'
    repo.mkdir()
    git(repo,'init','-q','-b','main')
    def commit(path,content):
        file=repo/path
        file.parent.mkdir(parents=True,exist_ok=True)
        file.write_text(content,encoding='utf-8')
        git(repo,'add','--',path)
        git(repo,'-c','user.name=Gate Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
        return git(repo,'rev-parse','HEAD')
    source=commit('app/android-native-wms/fixture.txt','android one')
    docs=commit('docs/fixture.txt','docs only')
    return repo,source,docs,commit


def test_android_old_green_reuses_only_proved_unchanged_ancestor(gate,monkeypatch,capsys,history):
    repo,source,target,_=history
    monkeypatch.setattr(gate,'ROOT',repo)
    runs={wf:good_run(target) for _,wf in gate.REQUIRED_WORKFLOWS}
    runs['.github/workflows/android-build.yml']=good_run(source)
    rc,data=invoke(gate,monkeypatch,capsys,runs,target)
    assert rc==0
    android=data['results'][0]
    assert android['state']=='green' and '祖先' in android['detail'] and '未变' in android['detail']
    assert android['head_sha_full']==source


@pytest.mark.parametrize('path',['app/android-native-wms/fixture.txt','.github/workflows/android-build.yml'])
def test_android_or_build_workflow_change_rejects_old_build(gate,monkeypatch,capsys,history,path):
    repo,source,_,commit=history
    target=commit(path,'changed Android inputs')
    monkeypatch.setattr(gate,'ROOT',repo)
    runs={wf:good_run(target) for _,wf in gate.REQUIRED_WORKFLOWS}
    runs['.github/workflows/android-build.yml']=good_run(source)
    rc,data=invoke(gate,monkeypatch,capsys,runs,target)
    assert rc==1 and data['results'][0]['state']=='missing'
    assert '已变化' in data['results'][0]['detail']


def test_android_run_from_a_descendant_is_not_ancestor_proof(gate,monkeypatch,history):
    repo,source,target,_=history
    monkeypatch.setattr(gate,'ROOT',repo)
    ok,detail=gate.android_reuse_check(target,source)
    assert not ok and '祖先' in detail


@pytest.mark.parametrize('missing_source',[True,False])
def test_android_missing_objects_fail_closed(gate,monkeypatch,history,missing_source):
    repo,source,target,_=history
    monkeypatch.setattr(gate,'ROOT',repo)
    ok,detail=gate.android_reuse_check(OLD if missing_source else source,target if missing_source else OLD)
    assert not ok and '缺少' in detail


def test_android_git_comparison_error_is_unknown(gate,monkeypatch):
    def unavailable(*args,**kwargs):
        raise OSError('git not available')
    monkeypatch.setattr(gate.subprocess,'run',unavailable)
    ok,detail=gate.android_reuse_check(OLD,TARGET)
    assert not ok and '未核实' in detail


def test_pending_output_explicitly_allows_read_only_preparation(gate,monkeypatch,capsys):
    monkeypatch.setattr(gate,'resolve_token',lambda:None)
    monkeypatch.setattr(gate,'latest_run',lambda *args:{'status':'in_progress','conclusion':None})
    monkeypatch.setattr(sys,'argv',[str(CHECKER),'--target-sha',TARGET])
    assert gate.main()==1
    output=capsys.readouterr().out
    assert '禁止代码写入、提交、推送或发布' in output
    assert '允许只读检查与准备' in output
    assert '不代表失败' in output


def bash_binary():
    found=shutil.which('bash')
    if found:
        return found
    git_path=shutil.which('git')
    if git_path:
        bundled=Path(git_path).resolve().parent.parent/'bin/bash.exe'
        if bundled.is_file():
            return str(bundled)
    pytest.skip('Bash required for actual hook behavior')


def hook_run(tmp_path,push_input,returncode=0,broken_alias=False):
    args_file=tmp_path/'gate-args.txt'
    script=r'''
python3() { if [ "${WMS_TEST_BAD_ALIAS}" = "1" ]; then return 99; fi; python "$@"; }
python() { if [ "$1" = "-c" ]; then return 0; fi; printf '%s\n' "$@" > "${WMS_TEST_ARGS}"; return "${WMS_TEST_RESULT}"; }
source "$1"
'''
    env=dict(os.environ)
    env.pop('WMS_SKIP_CI_GATE',None)
    env.update(WMS_TEST_ARGS=str(args_file),WMS_TEST_RESULT=str(returncode),WMS_TEST_BAD_ALIAS='1' if broken_alias else '0')
    result=subprocess.run([bash_binary(),'-c',script,'gate-test',str(HOOK)],input=push_input,capture_output=True,text=True,encoding='utf-8',env=env,cwd=ROOT,timeout=30)
    return result,args_file.read_text(encoding='utf-8').splitlines() if args_file.exists() else None


@pytest.mark.parametrize('broken_alias',[False,True])
def test_pre_push_passes_remote_baseline_not_local_unbuilt_sha(tmp_path,broken_alias):
    result,args=hook_run(tmp_path,f'refs/heads/main {LOCAL} refs/heads/main {TARGET}\n',broken_alias=broken_alias)
    assert result.returncode==0,result.stderr
    assert args==['scripts/check_ci_green.py','--quiet','--target-sha',TARGET]
    assert LOCAL not in args


def test_no_ref_updates_are_read_only_noop_without_ci_query(tmp_path):
    result,args=hook_run(tmp_path,'',returncode=1)
    assert result.returncode==0 and args is None


@pytest.mark.parametrize('remote_sha',['0'*40,'abc','--help'])
def test_pre_push_rejects_missing_or_malformed_remote_baseline(tmp_path,remote_sha):
    result,args=hook_run(tmp_path,f'refs/heads/main {LOCAL} refs/heads/main {remote_sha}\n')
    assert result.returncode!=0 and args is None
    assert '基线SHA' in result.stderr


def test_pre_push_pending_or_unknown_gate_blocks_actual_write(tmp_path):
    result,args=hook_run(tmp_path,f'refs/heads/main {LOCAL} refs/heads/main {TARGET}\n',returncode=1)
    assert result.returncode!=0
    assert args[-1]==TARGET
    assert 'CI 门禁未通过' in result.stderr
