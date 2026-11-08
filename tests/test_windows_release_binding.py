"""Synthetic committed inputs, ZIPs and fake GitHub responses; no release/network/app."""
import copy,importlib.util,json,subprocess,sys,zipfile
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
A='a'*40;B='b'*40;F='f'*64
def load():
 p=ROOT/'tools/windows_release.py';spec=importlib.util.spec_from_file_location('tested_windows_release',p)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def command(root,*args):return subprocess.check_output(['git','-C',str(root),*args])
@pytest.fixture
def source(tmp_path):
 root=tmp_path/'source';root.mkdir();command(root,'init','-b','main');command(root,'config','user.name','Fixture');command(root,'config','user.email','fixture@example.invalid')
 for name,data in {'app/app.py':'# synthetic app','app/requirements.txt':'Flask==3.1.3','tools/build_portable_dist.ps1':'# fake build input','.github/workflows/windows-release.yml':'name: synthetic','README.md':'first'}.items():
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data,encoding='utf-8')
 command(root,'add','.');command(root,'commit','-m','fixture');return root
@pytest.fixture
def candidate(tmp_path):
 def make():
  m=load();work=tmp_path/'work';work.mkdir();package=tmp_path/'WMS-2026.11.4';package.mkdir()
  for name,data in {'app/app.py':b'# synthetic','python/python.exe':b'fake runtime','tools/helper.py':b'# fake tool'}.items():
   p=package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
  from services.release_manifest import build_release_manifest
  manifest=build_release_manifest(package,source_sha=A,ui_sha=A,includes=['app','tools','python'],application_root='app',overlay_roots=[],runtime_report=dict(success=True,python_version='3.11.9',packages=[],failures=[]),external_operations_paused=False)
  (package/'wms-release.json').write_text(json.dumps(manifest),encoding='utf-8')
  plan=m.select_release('2026.11.4',A,F);plan.update(work_dir=str(work),root=str(tmp_path/'source'),repository='owner/wms')
  receipt=dict(success=True,source_sha=A,artifact_id=manifest['artifact_id'],checks=m.CHECKS)
  (work/plan['names']['runtime']).write_text(json.dumps(receipt),encoding='utf-8')
  archive=work/plan['names']['archive']
  with zipfile.ZipFile(archive,'w') as z:
   for p in package.rglob('*'):
    if p.is_file():z.write(p,package.name+'/'+p.relative_to(package).as_posix())
  proof=m.seal_release(plan,package,archive)
  release=dict(tag_name=plan['names']['tag'],draft=False,target_commitish=A,html_url='https://github.com/owner/wms/releases/tag/'+plan['names']['tag'],assets=[])
  def assets():
   release['assets']=[dict(name=plan['names'][k],state='uploaded',size=(work/plan['names'][k]).stat().st_size,digest='sha256:'+m.file_digest(work/plan['names'][k])) for k in ('archive','checksum','proof','runtime')]
  assets();return m,plan,release,proof,package,work,assets
 return make

def test_build_inputs(source):
 m=load();first=m.build_inputs(source);sha=command(source,'rev-parse','HEAD').decode().strip()
 (source/'README.md').write_text('docs only');command(source,'add','.');command(source,'commit','-m','docs')
 assert m.build_inputs(source)==first==m.build_inputs(source,sha)
 (source/'app/app.py').write_text('# different program');command(source,'add','.');command(source,'commit','-m','code')
 assert m.build_inputs(source)!=first
 with pytest.raises(ValueError):m.build_inputs(source,'HEAD; not allowed')
def test_select_release(candidate):
 m,plan,release,proof,*_=candidate()
 assert plan['state']=='build'
 assert m.select_release(plan['version'],B,F,release,proof)['state']=='reuse_pending_verification'
@pytest.mark.parametrize('case',['missing_proof','draft','other_inputs','other_version','bad_source','bad_digest'])
def test_select_release_rejects_unsafe_reuse(candidate,case):
 m,plan,release,proof,*_=candidate()
 if case=='missing_proof':proof=None
 elif case=='draft':release['draft']=True
 elif case=='other_inputs':proof['input_fingerprint']='0'*64
 elif case=='other_version':proof['version']='2026.11.3'
 elif case=='bad_source':proof['source_sha']='main'
 else:proof['archive_sha256']='bad'
 with pytest.raises(ValueError):m.select_release(plan['version'],A,F,release,proof)
def test_verify_downloads(candidate):
 m,plan,release,proof,package,work,_=candidate()
 assert m.verify_downloads(release,work,plan,A)==proof
@pytest.mark.parametrize('case',['missing','wrong_digest','not_uploaded','duplicate','wrong_tag','wrong_source','corrupt','no_runtime_check','checksum'])
def test_verify_downloads_refuses_incomplete_assets(candidate,case):
 m,plan,release,proof,package,work,assets=candidate()
 if case=='missing':release['assets'].pop()
 elif case=='wrong_digest':release['assets'][0]['digest']='sha256:'+'0'*64
 elif case=='not_uploaded':release['assets'][0]['state']='new'
 elif case=='duplicate':release['assets'].append(copy.deepcopy(release['assets'][0]))
 elif case=='wrong_tag':release['tag_name']='other'
 elif case=='wrong_source':proof['source_sha']=B;(work/plan['names']['proof']).write_text(json.dumps(proof));assets()
 elif case=='corrupt':(work/plan['names']['archive']).write_bytes(b'corrupt')
 elif case=='checksum':(work/plan['names']['checksum']).write_text('wrong');assets()
 else:
  p=work/plan['names']['runtime'];r=json.loads(p.read_text());r['checks']=[];p.write_text(json.dumps(r));proof['runtime_receipt_sha256']=m.file_digest(p);(work/plan['names']['proof']).write_text(json.dumps(proof));assets()
 with pytest.raises((ValueError,zipfile.BadZipFile)):m.verify_downloads(release,work,plan,A)
def test_verify_archive_checks_actual_content(candidate):
 m,plan,release,proof,package,work,assets=candidate();p=work/plan['names']['archive']
 with zipfile.ZipFile(p) as z:data={i.filename:z.read(i) for i in z.infolist()}
 data[package.name+'/app/app.py']=b'# changed source'
 with zipfile.ZipFile(p,'w') as z:
  for name,value in data.items():z.writestr(name,value)
 proof['archive_sha256']=m.file_digest(p);(work/plan['names']['proof']).write_text(json.dumps(proof));(work/plan['names']['checksum']).write_text(proof['archive_sha256']+'  '+plan['names']['archive']+'\n');assets()
 with pytest.raises(ValueError):m.verify_downloads(release,work,plan,A)
def test_seal_release_requires_actual_runtime_receipt(candidate):
 m,plan,release,proof,package,work,_=candidate()
 (work/plan['names']['runtime']).unlink()
 with pytest.raises(FileNotFoundError):m.seal_release(plan,package,work/plan['names']['archive'])
def test_publish_release(candidate,monkeypatch):
 m,plan,release,proof,package,work,assets=candidate();state={'published':False};calls=[]
 def api(endpoint,**kw):
  if endpoint.endswith('/heads/main'):return {'object':{'sha':A}}
  r=copy.deepcopy(release);r['draft']=not state['published'];return [r] if '/releases?' in endpoint else r
 def gh(*args,**kw):
  calls.append(args)
  if args[:2]==('release','edit'):state['published']=True
 monkeypatch.setattr(m,'_json_api',api);monkeypatch.setattr(m,'_gh',gh);monkeypatch.setattr(m,'tag_commit',lambda *a:A if state['published'] else None);monkeypatch.setattr(m,'build_inputs',lambda *a:F)
 assert m.publish_release(plan,work/'notes.txt')['state']=='built_verified'
 assert '--draft' in calls[0] and calls[1][:2]==('release','edit')
@pytest.mark.parametrize('case',['main_changed','broken_asset','changed_during_upload','tag_race'])
def test_publish_release_never_publishes_unverified(candidate,monkeypatch,case):
 m,plan,release,proof,package,work,assets=candidate();calls=[];reads=[0]
 if case=='broken_asset':release['assets'][0]['digest']='sha256:'+'0'*64
 def api(endpoint,**kw):
  if endpoint.endswith('/heads/main'):
   reads[0]+=1;return {'object':{'sha':B if case=='main_changed' or (case=='changed_during_upload' and reads[0]>1) else A}}
  r=copy.deepcopy(release);r['draft']=True;return [r] if '/releases?' in endpoint else r
 monkeypatch.setattr(m,'_json_api',api);monkeypatch.setattr(m,'_gh',lambda *a,**kw:calls.append(a));monkeypatch.setattr(m,'tag_commit',lambda *a:B if case=='tag_race' else None);monkeypatch.setattr(m,'build_inputs',lambda *a:F)
 with pytest.raises(ValueError):m.publish_release(plan,work/'notes.txt')
 assert not any(a[:2]==('release','edit') for a in calls)
def test_release_names():
 m=load();assert m.release_names('2026.11.4')['tag']=='windows-v2026.11.4'
 for bad in ['latest','2026.11.4\nunsafe','../outside',None]:
  with pytest.raises(ValueError):m.release_names(bad)
def test_windows_workflow_uses_verified_build_or_reuse():
 text=(ROOT/'.github/workflows/windows-release.yml').read_text()
 assert 'tools/windows_release.py plan' in text
 assert 'tools/windows_release.py seal' in text and 'tools/windows_release.py publish' in text
 assert '--receipt' in text and "steps.release.outputs.state == 'build'" in text
 assert "steps.release.outputs.exists != 'True'" not in text

@pytest.mark.parametrize('reuse',[False,True])
def test_plan_release(candidate,monkeypatch,tmp_path,reuse):
 import shutil
 m,plan,release,proof,package,work,assets=candidate();dest=tmp_path/'download';requests=[]
 def api(endpoint,missing=False):
  requests.append(endpoint)
  if endpoint.endswith('/heads/main'):return {'object':{'sha':A}}
  if '/releases/tags/' in endpoint:return release if reuse else None
  return {'object':{'type':'commit','sha':A}} if reuse else None
 def gh(*args,**kw):
  assert args[:2]==('release','download')
  for key in ('archive','checksum','proof','runtime'):shutil.copyfile(work/plan['names'][key],dest/plan['names'][key])
 monkeypatch.setattr(m,'_json_api',api);monkeypatch.setattr(m,'_gh',gh);monkeypatch.setattr(m,'build_inputs',lambda *a:F)
 monkeypatch.setattr(m.subprocess,'check_output',lambda *a,**kw:A+'\n')
 monkeypatch.setattr(m.subprocess,'run',lambda *a,**kw:type('Result',(),{'returncode':0})())
 result=m.plan_release(tmp_path/'source','2026.11.4',dest,'owner/wms')
 assert result['state']==('reused_verified' if reuse else 'build') and json.loads((dest/'plan.json').read_text())==result
 assert requests and not (dest/'app').exists()
def test_tag_commit(monkeypatch):
 m=load();seen=[]
 def api(endpoint,**kw):
  seen.append(endpoint);return {'object':{'type':'tag','sha':B}} if len(seen)==1 else {'object':{'type':'commit','sha':A}}
 monkeypatch.setattr(m,'_json_api',api);assert m.tag_commit('owner/wms','windows-v2026.11.4')==A and len(seen)==2
 monkeypatch.setattr(m,'_json_api',lambda *a,**kw:None);assert m.tag_commit('owner/wms','windows-v2026.11.4') is None
def test_file_digest(tmp_path):
 m=load();p=tmp_path/'empty';p.write_bytes(b'')
 assert m.file_digest(p)=='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
def test_gh_errors_are_not_verified_reuse(monkeypatch):
 m=load();fake=type('Result',(),dict(returncode=1,stderr='request failed (HTTP 404)',stdout=''))()
 monkeypatch.setattr(m.subprocess,'run',lambda *a,**kw:fake)
 assert m._gh('api','repos/owner/wms/releases/tags/missing',missing=True) is None
 with pytest.raises(ValueError):m._gh('api','repos/owner/wms/releases/tags/missing')
def test_main(monkeypatch,tmp_path):
 m=load();monkeypatch.setenv('GITHUB_REPOSITORY','owner/wms');out=tmp_path/'outputs'
 plan=m.select_release('2026.11.4',A,F);plan['work_dir']=str(tmp_path/'candidate')
 monkeypatch.setattr(m,'plan_release',lambda *args:plan)
 assert m.main(['plan','--root',str(tmp_path),'--version','2026.11.4','--work',str(tmp_path/'candidate'),'--github-output',str(out)])==0
 assert 'state=build' in out.read_text() and 'tag=windows-v2026.11.4' in out.read_text()
 monkeypatch.setenv('GITHUB_REPOSITORY','invalid value');assert m.main(['plan','--root',str(tmp_path),'--version','2026.11.4','--work',str(tmp_path/'candidate'),'--github-output',str(out)])==1
def runtime_module():
 p=ROOT/'tools/check_portable_runtime.py';s=importlib.util.spec_from_file_location('runtime_receipt_test_target',p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def test_write_runtime_receipt(tmp_path):
 m=runtime_module();path=tmp_path/'runtime.json';identity=dict(success=True,source_sha=A,artifact_id='d'*64,checks=load().CHECKS)
 m.write_runtime_receipt(path,identity);assert json.loads(path.read_text())==identity
 with pytest.raises(FileExistsError):m.write_runtime_receipt(path,identity)
 assert json.loads(path.read_text())==identity
def test_runtime_main_refuses_receipt_before_success(tmp_path,monkeypatch):
 m=runtime_module();path=tmp_path/'runtime.json'
 def fail(*a):raise RuntimeError('synthetic startup failed')
 monkeypatch.setattr(m,'verify_package',fail)
 with pytest.raises(RuntimeError):m.main(['--package',str(tmp_path),'--receipt',str(path)])
 assert not path.exists()
