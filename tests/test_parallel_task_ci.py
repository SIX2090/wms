"""F2.8-PARALLEL-001: target acceptance survives newer independent tasks."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.parse

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'a' * 40
NEWER = 'c' * 40


@pytest.fixture
def checker():
    spec=importlib.util.spec_from_file_location('parallel_ci_checker',ROOT/'scripts/check_ci_green.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(sha,conclusion='success',status='completed'):
    return dict(head_sha=sha,head_branch='main',status=status,conclusion=conclusion)


@pytest.mark.parametrize('new_status,new_conclusion',[
    ('queued',None),('in_progress',None),('completed','failure'),('completed','cancelled'),
])
def test_older_task_accepts_own_green_while_newer_task_is_not_green(checker,monkeypatch,capsys,new_status,new_conclusion):
    calls=[]
    def api(path,token):
        query=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        calls.append(query)
        # The old implementation omitted head_sha, so it receives B's red/pending run.
        selected=run(TARGET) if query.get('head_sha')==[TARGET] else run(NEWER,new_conclusion,new_status)
        return {'workflow_runs':[selected]}
    monkeypatch.setattr(checker,'gh_get',api)
    monkeypatch.setattr(checker,'resolve_token',lambda:None)
    monkeypatch.setattr(sys,'argv',['check_ci_green.py','--json','--target-sha',TARGET])
    assert checker.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['ok'] and result['target_sha']==TARGET
    assert all(item['head_sha_full']==TARGET for item in result['results'])
    assert len(calls)==3
    assert all(query['branch']==['main'] and query['head_sha']==[TARGET] for query in calls)


@pytest.mark.parametrize('conclusion,status',[('failure','completed'),('cancelled','completed'),(None,'in_progress')])
def test_own_non_green_cannot_be_hidden_by_another_tasks_green(checker,monkeypatch,capsys,conclusion,status):
    def api(path,token):
        query=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        selected=run(TARGET,conclusion,status) if query.get('head_sha')==[TARGET] else run(NEWER)
        return {'workflow_runs':[selected]}
    monkeypatch.setattr(checker,'gh_get',api)
    monkeypatch.setattr(checker,'resolve_token',lambda:None)
    monkeypatch.setattr(sys,'argv',['check_ci_green.py','--json','--target-sha',TARGET])
    assert checker.main()==1
    result=json.loads(capsys.readouterr().out)
    assert not result['ok']
    assert all(item['head_sha_full']==TARGET and item['state']!='green' for item in result['results'])


def git(repo,*args):
    result=subprocess.run(['git','-c','core.hooksPath=','-c','commit.gpgsign=false',*args],cwd=repo,
                          capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stderr
    return result.stdout.strip()


def test_android_source_is_from_older_targets_history_not_newer_main(checker,monkeypatch,capsys,tmp_path):
    git(tmp_path,'init','-q','-b','main')
    def commit(path,text):
        dest=tmp_path/path
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(text,encoding='utf-8')
        git(tmp_path,'add','--',path)
        git(tmp_path,'-c','user.name=CI Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture')
        return git(tmp_path,'rev-parse','HEAD')
    source=commit('app/android-native-wms/fixture.txt','old Android inputs')
    target=commit('README.md','task A')
    newer=commit('app/android-native-wms/fixture.txt','task B Android inputs')
    calls=[]
    def api(path,token):
        query=urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
        sha=query.get('head_sha',[None])[0]
        calls.append((path.split('/workflows/')[1].split('/')[0],sha))
        if 'android-build.yml' in path:
            runs=[] if sha==target else [run(source)] if sha==source else [run(newer,'failure')]
        else:
            runs=[run(target)] if sha==target else [run(newer,'failure')]
        return {'workflow_runs':runs}
    monkeypatch.setattr(checker,'ROOT',tmp_path)
    monkeypatch.setattr(checker,'gh_get',api)
    monkeypatch.setattr(checker,'resolve_token',lambda:None)
    monkeypatch.setattr(sys,'argv',['check_ci_green.py','--json','--target-sha',target])
    assert checker.main()==0
    result=json.loads(capsys.readouterr().out)
    assert result['results'][0]['head_sha_full']==source
    assert ('android-build.yml',source) in calls
    assert all(sha in (source,target) for _,sha in calls)
    assert checker.android_source_sha(target)==source
    assert checker.android_source_sha(newer)==newer


@pytest.mark.parametrize('workflow',['ci.yml','verify.yml','android-build.yml','perf.yml'])
def test_independent_workflow_runs_have_no_cross_commit_cancellation_or_queue(workflow):
    body=yaml.safe_load((ROOT/'.github/workflows'/workflow).read_text(encoding='utf-8'))
    assert 'concurrency' not in body
    assert all('concurrency' not in job for job in body['jobs'].values())


def test_push_still_rejects_changed_release_inputs_without_version_bump(tmp_path):
    git(tmp_path,'init','-q','-b','main')
    material=tmp_path/'app/fixture.txt'
    material.parent.mkdir()
    material.write_text('before',encoding='utf-8')
    git(tmp_path,'add','app/fixture.txt')
    def commit():
        git(tmp_path,'-c','user.name=CI Fixture','-c','user.email=fixture@example.invalid','commit','-qam','fixture')
        return git(tmp_path,'rev-parse','HEAD')
    baseline=commit()
    material.write_text('after',encoding='utf-8')
    target=commit()
    bash=shutil.which('bash')
    if not bash:
        binary=shutil.which('git')
        bundled=Path(binary).resolve().parent.parent/'bin/bash.exe' if binary else None
        if not bundled or not bundled.is_file():
            pytest.skip('Bash unavailable')
        bash=str(bundled)
    env=dict(os.environ)
    env.pop('WMS_SKIP_RELEASE_VERSION_GATE',None)
    result=subprocess.run([bash,str(ROOT/'.githooks/pre-push')],cwd=tmp_path,
        input=f'refs/heads/main {target} refs/heads/main {baseline}\n',
        capture_output=True,text=True,encoding='utf-8',env=env,timeout=30)
    assert result.returncode!=0
    assert 'app/version.py 未递增' in result.stderr
