from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""006/007 local HTTP and pure front-end dispatch, never real image/search I/O."""
from pathlib import Path
import copy
import html
import io
import json
import re
import shutil
import socket
import subprocess

import pytest
import requests
from PIL import Image
from sqlalchemy import event,select

import app as m
from tests.audit_regressions.http_fixture import http_case

ROOT=Path(__file__).resolve().parents[1]
REAL_SAVE=m._save_material_image_from_url
GOOD='https://qa40.invalid/image.png';THUMB='https://qa40.invalid/thumb.png';SOURCE='https://qa40.invalid/info'
MARKER='QA40_SYNTHETIC_TRANSPORT_ERROR'


@pytest.mark.parametrize('value,expected', [
    (None, ''), (['https://qa40.invalid/x'], ''),
    ('javascript:qa40', ''), ('https:///missing.png', ''),
    ('https://qa40.invalid:99999/x', ''), ('https://qa40.invalid/a\r\nb', ''),
    (' https://qa40.invalid/image.png ', GOOD),
    ('https://qa40.invalid/image.png?size=2', 'https://qa40.invalid/image.png?size=2'),
])
def test_candidate_http_url(value, expected):
    from services.material_image_candidates import candidate_http_url
    assert candidate_http_url(value) == expected


def snapshot():
    with m.app.app_context():
        return {t.name:[list(r) for r in m.db.session.execute(select(t).order_by(*t.primary_key.columns))]
            for t in m.db.metadata.tables.values()}


@pytest.fixture
def image_case(http_case,monkeypatch,tmp_path):
    monkeypatch.setattr(m.app, "static_folder", str(tmp_path / "static"))
    clients,ids,_=http_case
    monkeypatch.setattr(m,'_save_material_image_from_url',REAL_SAVE)
    dns=[]
    def local_dns(host,*a,**k):
        assert host=='qa40.invalid','No real or sensitive DNS target permitted'
        dns.append(host)
        return [(socket.AF_INET,socket.SOCK_STREAM,socket.IPPROTO_TCP,'',('93.184.216.34',0))]
    monkeypatch.setattr(m.socket,'getaddrinfo',local_dns)
    with m.app.app_context():engine=m.db.engine
    def deny_delete(conn,cursor,sql,params,context,many):
        if sql.lstrip().upper().startswith('DELETE'):raise AssertionError('No DELETE authorized')
    event.listen(engine,'before_cursor_execute',deny_delete)
    try:yield clients,ids,dns
    finally:event.remove(engine,'before_cursor_execute',deny_delete)


class Response:
    def __init__(self,record):
        self.record=record;self.status_code=record.get('status',200)
        self.text=record.get('text','');self.headers={'Content-Type':'image/png'}
        self.is_redirect=self.is_permanent_redirect=False
    def raise_for_status(self):
        if self.status_code>=400:raise requests.exceptions.HTTPError(MARKER)
    def json(self):return copy.deepcopy(self.record.get('body'))
    def iter_content(self,chunk_size=1):yield self.record['bytes']
    def close(self):pass


def local_get(monkeypatch,records):
    calls=[]
    def get(url,**kwargs):
        calls.append((url,kwargs));assert len(calls)<=len(records),'Unexpected request beyond local transport budget'
        item=records[len(calls)-1]
        if isinstance(item,Exception):raise item
        return Response(item)
    monkeypatch.setattr(m.requests,'get',get)
    return calls


def bing(items):
    return ''.join('<div m="'+html.escape(json.dumps(item),quote=True)+'"></div>' for item in items)


def good_baidu():return {'body':{'data':[{'middleURL':GOOD,'thumbURL':THUMB,'fromURL':SOURCE,'fromPageTitle':'合成图'}]}}


CASES={
    'baidu_mixed_bad_required':([{'body':{'data':[{'middleURL':[7]},good_baidu()['body']['data'][0]]}}, {'text':''}],
        {'image_url':GOOD,'thumb_url':THUMB,'source_url':SOURCE,'title':'合成图'},1),
    'baidu_bad_optional_fields':([{'body':{'data':[{'middleURL':GOOD,'thumbURL':[7],
        'fromURL':7,'fromPageTitle':{'bad':1}}]}},{'text':''}],
        {'image_url':GOOD,'thumb_url':GOOD,'source_url':'','title':''},1),
    'bing_mixed_bad_required':([{'body':{'data':[]}}, {'text':bing([{'murl':7},
        {'murl':GOOD,'turl':THUMB,'purl':SOURCE,'t':'合成Bing'}])}],
        {'image_url':GOOD,'thumb_url':THUMB,'source_url':SOURCE,'title':'合成Bing'},2),
    'bing_optional_urls_and_invalid_host':([{'body':{'data':[]}}, {'text':bing([
        {'murl':'https:///bad.png'}, {'murl':GOOD,'turl':'javascript:qa40',
         'purl':'data:text/plain,qa40','t':'合成Bing'}])}],
        {'image_url':GOOD,'thumb_url':GOOD,'source_url':'','title':'合成Bing'},2),
}


def save(name,value):
    (evidence_dir()/('image-'+name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')


@pytest.mark.parametrize('name',list(CASES))
def test_normalize_image_candidate(image_case,monkeypatch,name):
    clients,ids,dns=image_case;records,expected,budget=CASES[name]
    calls=local_get(monkeypatch,records);before=snapshot()
    r=clients().get(f"/material/{ids['material']}/image_candidates")
    save(name,{'http':r.status_code,'body':r.json,'local_search_calls':len(calls),'all_rows_unchanged':snapshot()==before})
    assert r.status_code==200 and r.json['status']=='success',r.json
    assert r.json['candidates']==[expected],r.json
    assert len(calls)==budget and dns==[] and snapshot()==before
    assert all(isinstance(v,str) for v in r.json['candidates'][0].values())


def test_search_empty_after_two_timeouts_then_explicit_reopen_recovers(image_case,monkeypatch):
    clients,ids,dns=image_case
    calls=local_get(monkeypatch,[requests.exceptions.ReadTimeout(MARKER),requests.exceptions.ReadTimeout(MARKER),good_baidu()])
    c=clients();before=snapshot();url=f"/material/{ids['material']}/image_candidates"
    first=c.get(url)
    assert first.status_code==200 and first.json['candidates']==[] and len(calls)==2
    second=c.get(url)
    assert second.status_code==200 and len(second.json['candidates'])==1 and len(calls)==3
    assert MARKER not in json.dumps(first.json) and snapshot()==before and dns==[]
    save('search-recovery',{'http':[200,200],'search_calls':[2,1],'all_rows_unchanged':True,'no_image_download':True})


@pytest.mark.parametrize('name,failed',[('read_timeout',requests.exceptions.ReadTimeout(MARKER)),('http_503',{'status':503})])
def test_selection_fetch_failure_is_json_and_explicit_retry_binds_synthetic_image(image_case,monkeypatch,name,failed):
    clients,ids,dns=image_case;output=io.BytesIO();Image.new('RGB',(32,32),'white').save(output,format='PNG')
    calls=local_get(monkeypatch,[failed,{'bytes':output.getvalue()}]);before=snapshot();c=clients()
    url=f"/material/{ids['material']}/image_select"
    failure=c.post(url,json={'image_url':GOOD})
    save('select-'+name,{'http':failure.status_code,'json':failure.is_json,'all_rows_unchanged':snapshot()==before,
        'synthetic_fetch_calls':len(calls)})
    assert failure.status_code==502 and failure.is_json and failure.json['status']=='error'
    assert MARKER not in json.dumps(failure.json) and len(calls)==1 and snapshot()==before
    success=c.post(url,json={'image_url':GOOD})
    assert success.status_code==200 and success.json['status']=='success',success.json
    assert len(calls)==2
    for fetched,options in calls:
        assert fetched==GOOD and options['allow_redirects'] is False and options['stream'] is True
    after=snapshot();assert {t for t in before if before[t]!=after[t]} <= {'material','operation_log'}
    assert len(after['operation_log'])==len(before['operation_log'])+1
    with m.app.app_context():
        material=m.db.session.get(m.Material,ids['material'])
        assert material.image==success.json['image'] and material.stock==30
        path=(Path(m.app.static_folder)/material.image).resolve()
        assert Path(m.app.static_folder).resolve() in path.parents and path.is_file()
        with Image.open(path) as picture:assert picture.format=='JPEG' and picture.size==(32,32)
    save('select-'+name,{'http':[502,200],'failed_fetch_calls':1,'manual_retry_fetch_calls':1,
        'failure_all_rows_unchanged':True,'success_changed_tables':['material','operation_log'],
        'only_synthetic_png_to_local_jpeg':True,'stock_config_credentials_unchanged':True})


@pytest.mark.parametrize('url',['https:///missing.png','ftp://qa40.invalid/image.png'])
def test_invalid_selection_url_is_rejected_without_dns_or_transport(image_case,monkeypatch,url):
    clients,ids,dns=image_case;calls=local_get(monkeypatch,[]);before=snapshot()
    r=clients().post(f"/material/{ids['material']}/image_select",json={'image_url':url})
    assert r.status_code==400 and r.is_json and r.json['status']=='error'
    assert calls==dns==[] and snapshot()==before


def test_toolbar_and_row_dispatch_same_implementation_with_correct_id():
    source=(ROOT/'app/templates/material.html').read_text(encoding='utf-8')
    functions=[]
    for name in ('getSelectedMaterialIds','getSelectedSingleId','toolbarFindImage'):
        start=source.index('function '+name+'(');opening=source.index('{',start);depth=0
        for end in range(opening,len(source)):
            depth+=(source[end]=='{')-(source[end]=='}')
            if depth==0:break
        functions.append(source[start:end+1])
    assert 'onclick="findMaterialImage({{ mat.id }})"' in source
    program=r'''const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('fs').readFileSync(0,'utf8'));
let selected=[],calls=[];const ctx={document:{querySelectorAll(){return selected.map(value=>({value}));}},findMaterialImage(id){calls.push(String(id));}};vm.createContext(ctx);vm.runInContext(p.source,ctx);
for(const ids of [[],['17','18']]){selected=ids;ctx.toolbarFindImage();assert.equal(calls.length,0);}
selected=['17'];ctx.toolbarFindImage();assert.deepEqual(calls,['17']);calls=[];selected=[];vm.runInContext('findMaterialImage(17)',ctx);assert.deepEqual(calls,['17']);'''
    result=subprocess.run([shutil.which('node'),'--max-old-space-size=64','-e',program],
        input=json.dumps({'source':'\n'.join(functions)}),text=True,encoding='utf-8',capture_output=True,timeout=12)
    assert result.returncode==0,result.stderr
    save('two-entry-dispatch',{'front_end_simulation':True,'real_browser':False,
        'toolbar_no_or_multiple_selection_no_search':True,'single_and_row_same_handler_and_id':True})
