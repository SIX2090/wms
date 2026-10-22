"""BUG-2026-10-22-015: standalone print-template pages load and use the real API."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = [('in_order', a) for a in ['upload','useTemplate','setAsDefault','deleteTemplate']] + [('out_order', a) for a in ['upload','setDefault','deleteTemplate']]


@pytest.mark.parametrize('page,action', ACTIONS)
@pytest.mark.parametrize('scenario', ['success','business','http','http_success','html','expired401','expired419','network','null'])
def test_actual_standalone_callbacks(page, action, scenario):
    run(page, action, scenario)


@pytest.mark.parametrize('page,action', [(p,a) for p,a in ACTIONS if a not in ('upload','useTemplate')])
def test_confirmation_cancel_posts_nothing(page, action):
    run(page, action, 'cancel')


@pytest.mark.parametrize('page', ['in_order','out_order'])
@pytest.mark.parametrize('scenario', ['empty','deferred'])
def test_empty_file_and_upload_busy_restore(page, scenario):
    run(page, 'upload', scenario)


@pytest.mark.parametrize('page', ['in_order','out_order'])
def test_standalone_versioned_api_precedes_business_script(page):
    from jinja2 import Environment
    source = (ROOT / f'app/templates/{page}_print_template.html').read_text(encoding='utf-8')
    assert '{% extends' not in source
    assert "filename='js/app.js'" not in source and 'js/app.js' not in source
    scripts = re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', source)
    api_index = next(i for i,(attrs,body) in enumerate(scripts) if "filename='js/api.js'" in attrs)
    business_index = next(i for i,(attrs,body) in enumerate(scripts) if 'addTemplateForm' in body)
    assert api_index < business_index
    attrs = Environment(autoescape=True).from_string(scripts[api_index][0]).render(config={'STATIC_VERSION':'release-test'},url_for=lambda name,filename:'/static/'+filename)
    assert '/static/js/api.js?v=release-test' in attrs and 'async' not in attrs and 'defer' not in attrs
    assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(', source)


def run(page, action, scenario):
    source = (ROOT / f'app/templates/{page}_print_template.html').read_text(encoding='utf-8')
    if action == 'upload':
        assert 'id="addTemplateForm"' in source and 'type="submit"' in source
    else:
        assert f'onclick="{action}(' in source, 'Only test real markup entry points'
    script = '\n'.join(body for attrs,body in re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', source) if 'src=' not in attrs)
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let scenario=p.scenario,requests=[],messages=[],alerts=[],reloads=0,timers=[],handlers={},pending;
const file={name:scenario==='empty'?'':'fixture.xlsx',size:scenario==='empty'?0:32};
const button={disabled:false,innerHTML:'<i>原始按钮</i> 保存模板'};
const fileInput={files:[file],value:scenario==='empty'?'':'fixture.xlsx'};
const nodes={excelFile:fileInput,addTemplateForm:{addEventListener(n,f){handlers[n]=f;},querySelector(){return button;}},fileInfo:{style:{}},fileName:{textContent:''}};
const document={querySelector:s=>s.includes('csrf-token')?{content:'template-csrf'}:null,querySelectorAll:()=>[],getElementById:id=>nodes[id]||{style:{},classList:{add(){},remove(){}}},addEventListener(){},createElement:()=>({textContent:'',style:{},remove(){}}),body:{appendChild(el){messages.push(el);}}};
class FormData{constructor(form){this.form=form;}get(k){return k==='excel_file'?file:k==='name'?'模板 中文 & +':k==='csrf_token'?'template-csrf':null;}}
const ctx={document,FormData,Headers,console,confirm:()=>scenario!=='cancel',alert(m){assert.equal(reloads,0);alerts.push(m);},location:{href:'original',reload(){reloads++;}},setTimeout:(f,ms)=>{timers.push({f,ms});},
fetch:(url,options)=>{requests.push({url,options});if(scenario==='deferred')return new Promise(resolve=>pending=()=>resolve(response('success')));if(scenario==='network')return Promise.reject(Error('offline'));return Promise.resolve(response(scenario));}};
function response(kind){const status=['http','http_success'].includes(kind)?409:kind==='html'?502:kind==='expired401'?401:kind==='expired419'?419:200;return{status,ok:status===200,json:()=>kind==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve(kind==='null'?null:['business','http'].includes(kind)?{status:'error',msg:'服务器说明 <img src=x onerror=bad()> 中文'}:{status:'success',msg:'ok',data:{status:'error',msg:'must keep root'}})};}
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
async function invoke(){return p.action==='upload'?handlers.submit.call(nodes.addTemplateForm,{preventDefault(){}}):ctx[p.action](7);}
(async()=>{
 if(scenario==='deferred'){
  const work=invoke();await flush();assert.equal(button.disabled,true);assert(button.innerHTML.includes('保存中'));assert.equal(reloads,0);assert.equal(alerts.length,0);assert.equal(fileInput.files[0],file);
  pending();await work;assert.equal(button.disabled,false);assert.equal(button.innerHTML,'<i>原始按钮</i> 保存模板');assert.equal(reloads,1);return;
 }
 await invoke();await flush();
 if(['empty','cancel'].includes(scenario)){assert.equal(requests.length,0);assert.equal(reloads,0);assert.equal(button.disabled,false);return;}
 assert.equal(requests.length,1);const request=requests[0],headers=new Headers(request.options.headers);
 assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');assert.equal(headers.get('X-CSRFToken'),'template-csrf');assert.equal(headers.get('X-Requested-With'),'XMLHttpRequest');
 const target=p.action==='upload'?'add':p.action==='deleteTemplate'?'7/delete':'7/set_default';assert.equal(request.url,'/'+p.page+'_print_template/'+target);
 if(p.action==='upload'){assert(request.options.body instanceof FormData);assert.equal(request.options.body.form,nodes.addTemplateForm);assert.equal(request.options.body.get('excel_file'),file);assert.equal(request.options.body.get('name'),'模板 中文 & +');assert(!headers.has('Content-Type'));assert.equal(button.disabled,false);assert.equal(button.innerHTML,'<i>原始按钮</i> 保存模板');assert.equal(fileInput.files[0],file);assert.equal(fileInput.value,'fixture.xlsx');}
 else assert.equal(request.options.body,undefined);
 if(scenario==='success'){assert.equal(reloads,1);assert.equal(alerts.length,1);}
 else{
  assert.equal(reloads,0);assert.equal(alerts.length,0);assert(messages.length>0);
  if(['business','http'].includes(scenario)){assert(messages.some(m=>m.textContent.includes('服务器说明 <img src=x onerror=bad()> 中文')));assert(messages.every(m=>m.innerHTML===undefined),'messages must be text, never injected HTML');}
  if(scenario==='html')assert(messages.some(m=>m.textContent.includes('502')));
  if(scenario.startsWith('expired'))assert.equal(ctx.location.href,'/login');
  scenario='success';await invoke();assert.equal(requests.length,2);assert.equal(reloads,1,'failed upload/action remains retryable');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node'); assert node, 'Node required'
    result = subprocess.run([node,'-e',program,json.dumps(dict(page=page,action=action,scenario=scenario,script=script,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8')))],capture_output=True,encoding='utf-8',env=dict(os.environ,NODE_OPTIONS='--max-old-space-size=64'),timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
