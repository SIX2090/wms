"""Execute the actual settings page events with production API and synthetic data only."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest
from jinja2 import DictLoader, Environment

ROOT=Path(__file__).resolve().parents[1]


class Nodes(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.parts=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))
    def handle_data(self,data):
        self.parts.append(data)


def function(source,name):
    start=source.index('function '+name+'(');opening=source.index('{',start);depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end+1]
    raise AssertionError(name)


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const requests=[],pending=[],timers=[],toasts=[],confirms=[];let reloaded=0,formFailure=false;
class Node{constructor(tag,attrs){this.tagName=tag.toUpperCase();this.attrs=attrs;this.id=attrs.id;this.name=attrs.name;this.type=attrs.type;this.value=attrs.value||'';this.checked='checked' in attrs;this.disabled='disabled' in attrs;this.innerHTML='original '+(attrs.id||'');this.textContent='';this.events={};this.classes=new Set((attrs.class||'').split(' '));this.classList={add:c=>this.classes.add(c),remove:c=>this.classes.delete(c),contains:c=>this.classes.has(c)};}addEventListener(name,fn){(this.events[name]??=[]).push(fn);}fire(name){for(const fn of this.events[name]||[])fn.call(this,{currentTarget:this,target:this,preventDefault(){}});}getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=v;}removeAttribute(k){delete this.attrs[k];}}
const nodes=p.nodes.map(([tag,a])=>new Node(tag,a)),byId=Object.fromEntries(nodes.filter(n=>n.id).map(n=>[n.id,n]));
const fields=nodes.filter(n=>n.name);byId.systemSettingsForm.elements=fields;
class FD{constructor(form){this.values=[];if(formFailure)throw Error('fixture FormData failed');if(form)for(const n of form.elements){if(!n.disabled&&(n.type!=='checkbox'||n.checked))this.append(n.name,n.value);}}append(k,v){this.values.push([k,String(v)]);}set(k,v){this.values=this.values.filter(row=>row[0]!==k);this.append(k,v);}get(k){return(this.values.find(row=>row[0]===k)||[])[1]??null;}entries(){return this.values[Symbol.iterator]();}}
const document={getElementById:id=>byId[id]||null,querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:null,querySelectorAll:()=>[],addEventListener(){}};
const escape=value=>String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
const ctx={document,Headers,FormData:FD,location:{origin:'http://fixture',href:'/original',reload:()=>reloaded++},bootstrap:{Modal:class{show(){byId.initBusinessDataModal.fire('shown.bs.modal');}}},escapeHtml:escape,wmsGlobalErrorToast(){},setTimeout:(fn,delay)=>timers.push({fn,delay}),showToast:(message,type)=>toasts.push({message,type}),confirm:message=>{confirms.push(message);return p.scenario!=='cancel';},fetch:(url,options)=>{requests.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.interceptor,ctx);vm.runInContext(p.legacy,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
const stats={business:[{label:'<literal>',count:2}],business_items:[],inventory:[],logs:[],ai:[],master:[{label:'master',count:3}],user_count:1};
function response(s,preview=false){const status={http:400,http_success:500,html:502,unauthorized:401,expired:419}[s]||200;return {status,ok:status===200,json:()=>['html','html200'].includes(s)?Promise.reject(Error('fixture HTML')):Promise.resolve(s==='null'?null:['http','business'].includes(s)?{status:'error',msg:'fixture refusal <literal>'}:{status:'success',msg:'fixture success',...(preview?{data:stats,preview_tokens:{'0':'fixture-keep','1':'fixture-clear'}}:{})})};}
async function finish(index,s,preview=false){if(s==='network')pending[index].reject(Error('fixture offline'));else pending[index].resolve(response(s,preview));await settle();}
const click=id=>byId[id].fire('click'),submit=()=>byId.systemSettingsForm.fire('submit');
const actionButton={save:'saveSettingsBtn',text:'testAiLlmBtn',vision:'testAiVisionBtn'};
function write(){if(p.action==='save')submit();else click(actionButton[p.action]);}
function inputs(valid=true){byId.initAdminPassword.value='  fixture password &+  ';byId.initConfirmPhrase.value=valid?'初始化业务数据':'初始化业务数据 ';byId.initAdminPassword.fire('input');byId.initConfirmPhrase.fire('input');}
function assertFD(request,init=false){assert.equal(request.options.method,'POST');assert.equal(new Headers(request.options.headers).get('X-CSRFToken'),'fixture-csrf');assert.equal(new Headers(request.options.headers).get('X-Requested-With'),'XMLHttpRequest');assert.equal(request.options.credentials,'same-origin');assert(request.options.body instanceof FD);assert.equal(new Headers(request.options.headers).get('Content-Type'),null);const body=request.options.body;if(init){assert.equal(body.get('admin_password'),'  fixture password &+  ');assert.equal(body.get('confirm_phrase'),'初始化业务数据');assert.equal(body.get('include_master_data'),p.include?'1':'0');assert.equal(body.get('preview_token'),p.include?'fixture-clear':'fixture-keep');}else{assert.equal(body.get('ai_llm_api_key'),'');assert.equal(body.get('ai_llm_base_url'),'  https://fixture.invalid/v1?x=1&y=2  ');assert.equal(body.get('ai_llm_enabled'),'1');assert.equal(body.get('test_type'),p.action==='vision'?'vision':null);assert.equal(body.get('csrf_token'),'fixture-csrf');}}
function noSuccess(){assert(!toasts.some(t=>t.type==='success'),'HTTP or business failure must not report success');assert.equal(reloaded,0);assert(!timers.some(t=>[500,1500].includes(t.delay)));}
(async()=>{
 if(['save','text','vision'].includes(p.action)){
  if(p.scenario==='form')formFailure=true;
  write();await settle();
  if(p.scenario==='form'){assert.equal(requests.length,0);assert(toasts.some(t=>t.type==='danger'));assert(!byId[actionButton[p.action]].disabled);return;}
  assert.equal(requests.length,1);assertFD(requests[0]);assert.equal(requests[0].url,p.action==='save'?'/system_settings/save':'/system_settings/test_ai_llm');
  if(p.scenario!=='http_success'){write();submit();click('testAiLlmBtn');click('testAiVisionBtn');await settle();assert.equal(requests.length,1,'inflight actions must not resend');assert(byId[actionButton[p.action]].disabled);}
  await finish(0,p.scenario);
  if(p.scenario==='success'){assert(toasts.some(t=>t.type==='success'));if(p.action==='save'){assert(byId.saveSettingsBtn.disabled);write();click('testAiLlmBtn');await settle();assert.equal(requests.length,1,'save navigation delay stays locked');const timer=timers.find(t=>t.delay===500);assert(timer);timer.fn();assert.equal(reloaded,1);}else assert(!byId[actionButton[p.action]].disabled);}
  else{noSuccess();assert(toasts.some(t=>t.type==='danger'));assert(!byId[actionButton[p.action]].disabled);assert(!toasts.some(t=>t.message.includes('Cannot read')));if(p.scenario!=='http_success'){write();await settle();assert.equal(requests.length,2,'only manual retry');await finish(1,'business');}}
  return;
 }
 byId.initIncludeMasterData.checked=p.include;
 click('openInitModalBtn');await settle();assert.equal(requests.length,1,'opening modal starts exactly one preview');assert.equal(requests[0].url,'/system_settings/init_business_data/preview');assert.equal(requests[0].options.method,'GET');
 inputs();assert(byId.confirmInitBtn.disabled,'preview must finish before execution');click('confirmInitBtn');await settle();assert.equal(requests.length,1);
 if(p.action==='late_preview'){submit();await settle();assert.equal(requests.length,2);await finish(1,'success');await finish(0,'success',true);inputs();assert(byId.confirmInitBtn.disabled,'late preview must not unlock an active save');click('confirmInitBtn');assert.equal(requests.length,2);return;}
 if(p.action==='preview'){
  await finish(0,p.scenario,true);inputs();click('confirmInitBtn');await settle();assert(byId.confirmInitBtn.disabled);assert.equal(requests.length,1);assert(!confirms.some(m=>m.includes('最后确认')));assert(!byId.initPreviewArea.innerHTML.includes('Cannot read'));noSuccess();return;
 }
 await finish(0,'success',true);assert(byId.initPreviewArea.innerHTML.includes('&lt;literal&gt;'));
 if(p.scenario==='summary'){const count=()=>Number((byId.initPreviewArea.innerHTML.match(/fw-bold text-danger">(\d+) 条/)||[])[1]);assert.equal(count(),p.include?5:2);assert.equal(byId.initPreviewArea.innerHTML.includes('主数据（保留）'),!p.include);byId.initIncludeMasterData.checked=!p.include;byId.initIncludeMasterData.fire('change');assert.equal(count(),p.include?2:5);assert.equal(requests.length,1,'checkbox rerenders cached preview without another GET');assert.equal(confirms.length,0);return;}
 if(p.scenario==='reopen'){inputs();assert(!byId.confirmInitBtn.disabled);click('openInitModalBtn');await settle();assert.equal(byId.initAdminPassword.value,'');assert.equal(byId.initConfirmPhrase.value,'');assert.equal(byId.initIncludeMasterData.checked,p.include);assert(byId.confirmInitBtn.disabled);assert.equal(requests.length,2);return;}
 inputs(false);assert(byId.confirmInitBtn.disabled);click('confirmInitBtn');await settle();assert.equal(requests.length,1,'exact phrase required');inputs();click('confirmInitBtn');await settle();
 if(p.scenario==='cancel'){assert.equal(requests.length,1);assert(confirms.some(m=>m.includes('最后确认')));noSuccess();return;}
 assert.equal(requests.length,2);assert.equal(requests[1].url,'/system_settings/init_business_data/execute');assertFD(requests[1],true);const native=confirms.filter(m=>m.includes('最后确认'));assert.equal(native.length,1);
 if(p.scenario!=='http_success'){inputs();click('confirmInitBtn');click('openInitModalBtn');submit();click('testAiLlmBtn');click('testAiVisionBtn');await settle();assert(byId.confirmInitBtn.disabled,'input must not unlock executing init');assert.equal(requests.length,2,'reopening and submit must not repeat execute or other writes');}
 if(p.scenario==='checkbox_retry'){byId.initIncludeMasterData.checked=true;byId.initIncludeMasterData.fire('change');await finish(1,'business');assert(byId.initPreviewArea.innerHTML.match(/fw-bold text-danger">5 条/),'failed execute must re-render current checkbox in preview');click('confirmInitBtn');await settle();assert.equal(requests.length,2,'failed preview cannot be reused');click('openInitModalBtn');await settle();await finish(2,'success',true);inputs();click('confirmInitBtn');await settle();assert.equal(requests.length,4);assert.equal(requests[3].options.body.get('include_master_data'),'1');assert.equal(requests[3].options.body.get('preview_token'),'fixture-clear');assert.equal(confirms.filter(m=>m.includes('最后确认')).length,2);await finish(3,'business');return;}
 await finish(1,p.scenario);
 if(p.scenario==='success'){assert(toasts.some(t=>t.type==='success'));inputs();click('confirmInitBtn');click('openInitModalBtn');await settle();assert.equal(requests.length,2,'init navigation delay stays locked');assert(byId.confirmInitBtn.disabled);const timer=timers.find(t=>t.delay===1500);assert(timer);timer.fn();assert.equal(reloaded,1);}
 else{noSuccess();assert(!byId.initErrorArea.classList.contains('d-none'));assert(byId.initErrorArea.textContent);if(p.scenario==='network')assert(byId.initErrorArea.textContent.includes('请先核对执行结果'));assert(!byId.initErrorArea.textContent.includes('Cannot read'));assert(byId.confirmInitBtn.disabled,'failed execution invalidates preview');if(p.scenario!=='http_success'){click('confirmInitBtn');assert.equal(requests.length,2);click('openInitModalBtn');await settle();await finish(2,'success',true);inputs();click('confirmInitBtn');await settle();assert.equal(requests.length,4,'failure requires a fresh preview and another human confirmation');await finish(3,'business');}}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def render():
    source=(ROOT/'app/templates/system_settings.html').read_text(encoding='utf-8')
    env=Environment(loader=DictLoader({'page':source,'base.html':'{% block content %}{% endblock %}{% block extra_js %}{% endblock %}'}),autoescape=True)
    group=NS(key='ai_assistant',icon='',title='Fixture',description='',settings=[NS(key='ai_llm_api_key',type='secret',has_value=True,wide=False,label='Secret',remark=''),NS(key='ai_llm_base_url',type='text',value='  https://fixture.invalid/v1?x=1&y=2  ',wide=False,label='Endpoint',remark=''),NS(key='ai_llm_enabled',type='bool',checked=True,wide=False,label='Enabled',remark='')])
    html=env.get_template('page').render(setting_groups=[group],csrf_token=lambda:'fixture-csrf',url_for=lambda *args,**kwargs:'/fixture')
    return html


def run(action,scenario='success',include=True,script_override=None):
    html=render()
    base=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    script=re.search(r'<script>(.*?)</script>',html,re.S);assert script
    start=base.index('    (function() {\n        var csrfToken =')
    end=base.index('    })();',start)+len('    })();')
    payload=dict(interceptor=base[start:end],action=action,scenario=scenario,include=include,nodes=Nodes(html).nodes,script=script_override or script.group(1),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),legacy='\n'.join(function(base,name) for name in ('getCsrfToken','csrfFetch')))
    node=shutil.which('node');assert node,'Node required for real settings events'
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('action',['save','text','vision'])
@pytest.mark.parametrize('scenario',['success','http_success'])
def test_real_settings_events_preserve_form_payload_and_never_trust_failed_http(action,scenario):
    run(action,scenario)


@pytest.mark.parametrize('action,scenario',[('save','null'),('save','html200'),('text','unauthorized'),('text','network'),('vision','expired'),('vision','http'),('vision','business'),('vision','html'),('vision','form')])
def test_settings_failures_recover_without_automatic_retry(action,scenario):
    run(action,scenario)


@pytest.mark.parametrize('include',[False,True])
def test_init_preserves_password_phrase_and_checkbox_and_locks_through_navigation(include):
    run('init',include=include)


@pytest.mark.parametrize('scenario',['http_success','http','null','html','html200','unauthorized','expired','network','business'])
def test_init_failures_are_visible_and_require_fresh_human_retry(scenario):
    run('init',scenario)


@pytest.mark.parametrize('scenario',['null','http_success','html','network'])
def test_failed_preview_never_enables_or_executes_init(scenario):
    run('preview',scenario)


@pytest.mark.parametrize('scenario',['cancel','reopen'])
def test_init_cancel_and_modal_reopen_preserve_manual_boundary(scenario):
    run('init',scenario,include=False)


@pytest.mark.parametrize('include',[False,True])
def test_preview_checkbox_uses_cached_stats_and_excludes_retained_master_rows(include):
    run('init','summary',include)


def test_late_preview_does_not_unlock_save_in_navigation_delay():
    run('late_preview')


def test_rendered_init_copy_matches_preservation_and_reset_contract():
    text=''.join(Nodes(render()).parts)
    assert '用户账号与密码保留' in text
    assert '系统参数重置为默认值' in text
    assert '本次初始化审计保留' in text
    assert '操作前先备份' in text
    assert '历史审计保留' in text
    assert '完整数据库备份及校验，失败则禁止清理' in text
    assert '导出可能失败' not in text
    assert 'revert_' not in text


def test_checkbox_changed_during_init_failure_updates_preview_before_human_retry():
    run('init','checkbox_retry',include=False)
