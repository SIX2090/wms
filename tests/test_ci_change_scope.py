"""BUG-2026-10-22-016: fail-closed CI scope selection with real Git histories."""
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/ci_change_scope.py'


@pytest.fixture
def scope():
    spec = importlib.util.spec_from_file_location('ci_change_scope_fixture', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def command(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo).decode().strip()


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    command(repo, 'init', '-b', 'main')
    command(repo, 'config', 'user.name', 'CI Fixture')
    command(repo, 'config', 'user.email', 'ci@example.invalid')
    for name in ['README.md','docs/ledger/a.md','docs/audit/a.md','app/app.py','AGENTS.md','DEVELOPMENT_RULES.md','requirements.txt','tests/test_old.py','scripts/old.py','.github/workflows/ci.yml']:
        path=repo/name; path.parent.mkdir(parents=True,exist_ok=True);path.write_text('initial\n')
    command(repo,'add','.');command(repo,'commit','-qm','base')
    base=command(repo,'rev-parse','HEAD')
    (repo/'README.md').write_text('documentation\n')
    command(repo,'commit','-qam','docs')
    return repo,base,command(repo,'rev-parse','HEAD')


def event(base, head):
    return {'before':base,'after':head,'ref':'refs/heads/main','deleted':False,'forced':False,'repository':{'full_name':'SIX2090/wms'}}


def entry(base, filename='ci.yml', ident=2, **changes):
    value=dict(id=ident,run_attempt=1,name='WMS CI' if filename=='ci.yml' else 'WMS AI Verification',path='.github/workflows/'+filename,head_sha=base,head_branch='main',status='completed',conclusion='success',created_at=f'2026-10-22T00:00:{ident:02}Z')
    value.update(changes)
    return value


def fetch_green(base, calls=None):
    def fetch(url, token):
        parsed=urllib.parse.urlparse(url);query=urllib.parse.parse_qs(parsed.query)
        assert query['head_sha']==[base] and query['branch']==['main']
        assert token=='fixture-token'
        if calls is not None:calls.append(url)
        filename=parsed.path.split('/')[-2]
        return {'total_count':1,'workflow_runs':[entry(base,filename)]}
    return fetch


def classify(scope, history, **overrides):
    repo,base,head=history
    opts=dict(event=event(base,head),event_name='push',repository='SIX2090/wms',token='fixture-token',cwd=repo,fetch=fetch_green(base))
    opts.update(overrides)
    return scope.classify(**opts)


def test_main_docs_requires_two_exact_green_base_workflows(scope, history):
    calls=[];out=classify(scope,history,fetch=fetch_green(history[1],calls))
    assert out['mode']=='docs' and out['docs_only'] is True
    assert len(calls)==2 and any('/ci.yml/' in url for url in calls) and any('/verify.yml/' in url for url in calls)


@pytest.mark.parametrize('path', ['README.md','docs/ledger/a.md','docs/ledger/2026/deep/a.md','docs/audit/a.md'])
def test_allowlisted_paths(scope,path):
    assert scope.allowed_path(path)


@pytest.mark.parametrize('path', ['readme.md','README.MD','AGENTS.md','DEVELOPMENT_RULES.md','docs/README.md','docs/ledgerx/a.md','docs/audit/a.py','docs/audit/a.MD','docs/ledger/../../app.py','docs/ledger/./a.md','docs//ledger/a.md','/docs/ledger/a.md','docs\\ledger\\a.md','docs/ledger/a.md\nmode=docs','docs/ledger/\x00x.md','.github/workflows/ci.yml','docs/ledger/a.md/evil.py'])
def test_paths_never_normalize_into_allowlist(scope,path):
    assert not scope.allowed_path(path)


@pytest.mark.parametrize('kind,expected', [('docs_add','docs'),('docs_delete','docs'),('docs_rename','docs'),('code_delete','full'),('code_rename_into_docs','full'),('code','full'),('rules','full'),('dependencies','full'),('tests','full'),('scripts','full'),('workflow','full')])
def test_real_git_changes_include_deletes_and_both_rename_paths(scope,history,kind,expected):
    repo,base,_=history
    if kind=='docs_add':(repo/'docs/ledger/new.md').write_text('new')
    elif kind=='docs_delete':(repo/'docs/audit/a.md').unlink()
    elif kind=='docs_rename':command(repo,'mv','docs/audit/a.md','docs/ledger/renamed.md')
    elif kind=='code_delete':(repo/'app/app.py').unlink()
    elif kind=='code_rename_into_docs':command(repo,'mv','app/app.py','docs/audit/moved.md')
    else:
        name={'code':'app/app.py','rules':'AGENTS.md','dependencies':'requirements.txt','tests':'tests/test_old.py','scripts':'scripts/old.py','workflow':'.github/workflows/ci.yml'}[kind]
        (repo/name).write_text('changed')
    command(repo,'add','-A');command(repo,'commit','-qm',kind)
    out=classify(scope,(repo,base,command(repo,'rev-parse','HEAD')))
    assert out['mode']==expected


@pytest.mark.parametrize('event_name',['schedule','pull_request','workflow_dispatch','repository_dispatch','unknown',''])
def test_non_push_always_full_without_api(scope,history,event_name):
    assert classify(scope,history,event_name=event_name,fetch=lambda *a:pytest.fail('API must not be queried'))['mode']=='full'


@pytest.mark.parametrize('field,value',[('before','0'*40),('after','0'*40),('before','a'*39),('after','z'*40),('after','a'*40+'\n'),('ref','refs/heads/dev'),('deleted',True),('forced',True)])
def test_untrusted_push_metadata_requires_full(scope,history,field,value):
    payload=event(history[1],history[2]);payload[field]=value
    assert classify(scope,history,event=payload)['mode']=='full'


def test_empty_diff_checkout_mismatch_and_missing_history(scope,history):
    repo,base,head=history
    assert classify(scope,history,event=event(head,head))['mode']=='full'
    assert classify(scope,history,event=event(base,base))['mode']=='full'
    assert classify(scope,history,event=event('f'*40,head))['mode']=='full'
    assert classify(scope,history,cwd=repo.parent)['mode']=='full'


def test_nonancestor_real_commit_fails_closed(scope,history):
    repo,base,head=history
    tree=command(repo,'rev-parse',base+'^{tree}')
    disconnected=command(repo,'commit-tree',tree,'-m','unrelated root')
    assert classify(scope,history,event=event(disconnected,head))['mode']=='full'


@pytest.mark.parametrize('field,value',[('head_sha','a'*40),('head_branch','dev'),('path','.github/workflows/other.yml'),('name','another'),('status','queued'),('status','in_progress'),('conclusion','failure'),('conclusion','cancelled'),('conclusion','skipped'),('id',None),('created_at','not-time')])
def test_baseline_filters_are_verified_not_trusted(scope,history,field,value):
    base=history[1]
    def fetch(url,token):
        filename=urllib.parse.urlparse(url).path.split('/')[-2]
        return {'total_count':1,'workflow_runs':[entry(base,filename,**{field:value})]}
    assert classify(scope,history,fetch=fetch)['mode']=='full'


@pytest.mark.parametrize('latest_green',[False,True])
def test_newest_run_wins_over_historical_result_even_unsorted(scope,history,latest_green):
    base=history[1]
    def fetch(url,token):
        filename=urllib.parse.urlparse(url).path.split('/')[-2]
        old=entry(base,filename,ident=1,conclusion='failure' if latest_green else 'success')
        new=entry(base,filename,ident=3,status='completed' if latest_green else 'in_progress',conclusion='success' if latest_green else None)
        return {'total_count':2,'workflow_runs':[old,new]}
    assert classify(scope,history,fetch=fetch)['docs_only'] is latest_green


def test_latest_retry_cannot_reuse_old_green_attempt(scope,history):
    base=history[1]
    def fetch(url,token):
        filename=urllib.parse.urlparse(url).path.split('/')[-2]
        old=entry(base,filename,run_attempt=1)
        retry=entry(base,filename,run_attempt=2,status='in_progress',conclusion=None)
        return {'total_count':2,'workflow_runs':[old,retry]}
    assert classify(scope,history,fetch=fetch)['mode']=='full'


def test_api_failure_missing_workflow_and_incomplete_pages_require_full(scope,history):
    def failed(*args):raise OSError('untrusted\nmode=docs\nsecret-token')
    for fetch in [failed,lambda *a:{'total_count':0,'workflow_runs':[]},lambda *a:{'total_count':3,'workflow_runs':[]},lambda *a:{'total_count':0,'workflow_runs':[entry(history[1])]}]:
        out=classify(scope,history,fetch=fetch)
        assert out['mode']=='full' and 'secret-token' not in json.dumps(out)


def test_verify_workflow_failure_is_not_hidden_by_ci_green(scope,history):
    green=fetch_green(history[1])
    def fetch(url,token):
        data=green(url,token)
        if '/verify.yml/' in url:data['workflow_runs'][0]['status']='queued'
        return data
    assert classify(scope,history,fetch=fetch)['mode']=='full'


def test_successful_docs_base_is_transitively_eligible(scope,history):
    repo,_,base=history
    (repo/'docs/ledger/a.md').write_text('second docs commit')
    command(repo,'commit','-qam','another docs-only change')
    assert classify(scope,(repo,base,command(repo,'rev-parse','HEAD')))['mode']=='docs'


def test_token_and_repository_metadata_require_verification(scope,history):
    assert classify(scope,history,token='')['mode']=='full'
    assert classify(scope,history,repository='other/repo')['mode']=='full'
    payload=event(history[1],history[2]);payload['repository']=None
    assert classify(scope,history,event=payload)['mode']=='full'


def test_github_output_is_single_line_per_key_and_rejects_forged_mode(scope,tmp_path):
    output=tmp_path/'output'
    scope.write_output(output,{'mode':'full','docs_only':False,'reason':'untrusted\nmode=docs\r\ndocs_only=true\0'})
    lines=output.read_text().splitlines()
    assert len(lines)==3 and lines[:2]==['mode=full','docs_only=false']
    assert lines[2].startswith('reason=')
    before=output.read_bytes()
    with pytest.raises(ValueError):scope.write_output(output,{'mode':'docs\nextra=true','docs_only':True,'reason':'bad'})
    assert output.read_bytes()==before


def test_api_request_uses_only_explicit_normal_token(scope,monkeypatch):
    seen=[]
    def open_request(request,timeout):
        seen.append(request)
        return io.StringIO('{"total_count":0,"workflow_runs":[]}')
    monkeypatch.setattr(scope.urllib.request,'urlopen',open_request)
    scope.read_api('https://api.github.com/repos/SIX2090/wms/actions/runs','fixture-token')
    assert seen[0].get_header('Authorization')=='Bearer fixture-token'
    assert seen[0].get_header('Accept')=='application/vnd.github+json'


@pytest.mark.parametrize('event_kind',['schedule','malformed','missing'])
def test_cli_safe_full_and_no_output_injection(tmp_path,event_kind):
    event_file=tmp_path/'event.json';output=tmp_path/'github-output'
    if event_kind=='malformed':event_file.write_text('{bad\nmode=docs')
    elif event_kind!='missing':event_file.write_text(json.dumps({'ref':'refs/heads/main\nmode=docs'}))
    env=dict(os.environ,GITHUB_EVENT_NAME='schedule',GITHUB_REPOSITORY='SIX2090/wms',GITHUB_TOKEN='do-not-print')
    run=subprocess.run([sys.executable,str(SCRIPT),'--event-file',str(event_file),'--github-output',str(output)],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)['mode']=='full'
    assert output.read_text().splitlines()[:2]==['mode=full','docs_only=false']
    assert len(output.read_text().splitlines())==3
    assert 'do-not-print' not in run.stdout+run.stderr+output.read_text()


def test_cli_output_write_failure_is_nonzero(tmp_path):
    event_file=tmp_path/'event.json';event_file.write_text('{}')
    run=subprocess.run([sys.executable,str(SCRIPT),'--event-file',str(event_file),'--github-output',str(tmp_path/'no-dir'/'output')],capture_output=True,text=True)
    assert run.returncode!=0
    assert json.loads(run.stdout)['mode']=='full'


def test_script_cli_exists_and_local_json_default_is_full(tmp_path):
    run=subprocess.run([sys.executable,str(SCRIPT),'--event-file',str(tmp_path/'missing.json')],capture_output=True,text=True)
    assert run.returncode==0,run.stderr
    assert json.loads(run.stdout)['docs_only'] is False


@pytest.mark.parametrize('mode,docs_only', [('docs',False),('full',True),('full','false'),('docs',1)])
def test_output_rejects_inconsistent_or_nonboolean_flags(scope,tmp_path,mode,docs_only):
    output=tmp_path/'output';output.write_text('existing\n')
    before=output.read_bytes()
    with pytest.raises(ValueError):
        scope.write_output(output,{'mode':mode,'docs_only':docs_only,'reason':'safe'})
    assert output.read_bytes()==before


@pytest.mark.parametrize('latest_green',[True,False])
def test_baseline_reads_every_page_before_selecting_latest(scope,latest_green):
    base='a'*40;calls=[]
    def fetch(url,token):
        parsed=urllib.parse.urlparse(url);query=urllib.parse.parse_qs(parsed.query)
        filename=parsed.path.split('/')[-2];page=int(query['page'][0]);calls.append((filename,page))
        assert query['head_sha']==[base] and query['branch']==['main']
        if page==1:
            runs=[entry(base,filename,ident=i,created_at='2026-10-21T00:00:00Z') for i in range(1,101)]
        else:
            runs=[entry(base,filename,ident=101,created_at='2026-10-22T00:00:00Z',status='completed' if latest_green else 'queued',conclusion='success' if latest_green else None)]
        return {'total_count':101,'workflow_runs':runs}
    assert scope.baseline_green('SIX2090/wms',base,'fixture-token',fetch=fetch) is latest_green
    assert calls[:2]==[('ci.yml',1),('ci.yml',2)]
    if latest_green:assert calls[2:]==[('verify.yml',1),('verify.yml',2)]


@pytest.mark.parametrize('identity', ['name','path','head_sha','head_branch'])
def test_review_unknown_newer_identity_cannot_hide_behind_old_green(scope,identity):
    base='a'*40
    def fetch(url,token):
        filename=urllib.parse.urlparse(url).path.split('/')[-2]
        old=entry(base,filename,ident=1)
        newer=entry(base,filename,ident=3,conclusion='failure',**{identity:'unknown'})
        return {'total_count':2,'workflow_runs':[old,newer]}
    assert scope.baseline_green('SIX2090/wms',base,'fixture-token',fetch=fetch) is False


@pytest.mark.parametrize('suffix', ['', '@main', '@refs/heads/main', '@dev', '@refs/heads/dev', '@main/other'])
def test_review_workflow_path_accepts_only_explicit_main_suffix(scope,suffix):
    base='a'*40
    def fetch(url,token):
        filename=urllib.parse.urlparse(url).path.split('/')[-2]
        return {'total_count':1,'workflow_runs':[entry(base,filename,path='.github/workflows/'+filename+suffix)]}
    assert scope.baseline_green('SIX2090/wms',base,'fixture-token',fetch=fetch) is (suffix in ('','@main','@refs/heads/main'))


@pytest.mark.parametrize('cross_page',[False,True])
def test_review_duplicate_run_ids_cannot_complete_api_page_count(scope,cross_page):
    base='a'*40
    def fetch(url,token):
        parsed=urllib.parse.urlparse(url);filename=parsed.path.split('/')[-2]
        page=int(urllib.parse.parse_qs(parsed.query)['page'][0])
        if cross_page:
            runs=[entry(base,filename,ident=i,created_at='2026-10-21T00:00:00Z') for i in range(1,101)] if page==1 else [entry(base,filename,ident=100,created_at='2026-10-21T00:00:00Z')]
            return {'total_count':101,'workflow_runs':runs}
        return {'total_count':2,'workflow_runs':[entry(base,filename),entry(base,filename)]}
    assert scope.baseline_green('SIX2090/wms',base,'fixture-token',fetch=fetch) is False
