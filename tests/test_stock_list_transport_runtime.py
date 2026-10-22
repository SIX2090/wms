"""BUG-2026-10-22-011: execute stock-list bindings with the real shared API."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = [('adjustment', a) for a in ('complete', 'delete', 'revert', 'batch', 'import')] + [('transfer', a) for a in ('add', 'edit', 'delete', 'copy', 'revert', 'batch', 'import')]
CONFIRMED = [(p, a) for p, a in ACTIONS if a in ('complete', 'delete', 'revert', 'batch', 'copy')]


@pytest.mark.parametrize('page,action', ACTIONS)
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'html', 'expired401', 'expired419', 'network'])
def test_stock_list_transport(page, action, scenario):
    run_action(page, action, scenario)


@pytest.mark.parametrize('page,action', CONFIRMED)
def test_cancellation_sends_nothing(page, action):
    run_action(page, action, 'cancel')


@pytest.mark.parametrize('page,action', [(p, a) for p, a in ACTIONS if a in ('batch', 'import')])
def test_empty_selection_sends_nothing(page, action):
    run_action(page, action, 'empty')


@pytest.mark.parametrize('page', ['adjustment', 'transfer'])
def test_no_legacy_transport_left(page):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(|\$\.(?:ajax|post|get)\s*\(', source)


def run_action(page, action, scenario):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    scripts = '\n'.join(re.findall(r'<script\b[^>]*>([\s\S]*?)</script>', source))
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let requests=[],messages=[],timers=[],reloads=0,hidden=0,scenario=p.scenario,handlers={};
const form={id:'test-form',action:'/'+p.page+'/import',fields:{remark:'备注 & 中文',from_warehouse:'A',to_warehouse:'B',from_location:'A01',to_location:'B01'}};
const file={files:scenario==='empty'?[]:[{name:'stock.xlsx'}],value:'stock.xlsx'};
const selected=scenario==='empty'?[]:[{value:'11'},{value:'12'}];
const buttons={};for(const key of ['complete','delete','revert'])buttons[key]={dataset:{id:'7'},addEventListener(n,f){this[n]=f;}};
class FormData {constructor(f){this.form=f;this.fields={...f.fields};}get(k){return this.fields[k];}}
const document={getElementById:id=>id==='file'?file:id==='form'?form:{id},
 querySelector:s=>s.includes('csrf-token')?{content:'stock-csrf'}:null,
 querySelectorAll(s){if(s.includes('check-item:checked'))return selected;if(s==='.completeBtn')return[buttons.complete];if(s==='.delBtn')return[buttons.delete];if(s==='.revertBtn')return[buttons.revert];return [];}};
function $(arg){if(arg===document)return{ready(f){f();}};return{
 change(f){handlers[arg]=f;},submit(f){handlers[arg]=f;},click(f){handlers[arg]=f;},
 data(k){return arg.dataset?.[k];},val(v){return v===undefined?(typeof arg==='object'?arg.value:'7'):undefined;},
 each(f){selected.forEach(cb=>f.call(cb));},prop(){return false;},serialize(){throw Error('Legacy serialize transport');}};}
const ctx={document,$,FormData,Headers,initCheckAll(){},showToast:(m,t)=>messages.push({m,t}),
 showConfirm:()=>Promise.resolve(scenario!=='cancel'),confirm:()=>scenario!=='cancel',setTimeout:(f,ms)=>{timers.push({f,ms});return timers.length;},
 bootstrap:{Modal:{getInstance:()=>({hide(){hidden++;}})}},location:{href:'original',reload(){reloads++;}},
 fetch:(url,options)=>{requests.push({url,options});const status=scenario==='http'?400:scenario==='html'?503:scenario==='expired401'?401:scenario==='expired419'?419:200;
 return scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({status,ok:status===200,json:()=>scenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({status:['business','http'].includes(scenario)?'error':'success',msg:'fixture explanation',data:{nested:'must not unwrap'}})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
async function invoke(){
 if(p.action==='import')ctx.submitDocumentImport('form','file');
 else if(p.page==='adjustment'){
  if(p.action==='batch')ctx.batchAdjustmentDelete();
  else await buttons[p.action].click.call(buttons[p.action]);
 }else{
  const keys={add:'#addForm',edit:'#editForm',delete:'.delBtn',copy:'.copyBtn',revert:'.revertBtn',batch:'#batchDeleteBtn'};
  await handlers[keys[p.action]].call(p.action==='add'||p.action==='edit'?form:{dataset:{id:'7'}},{preventDefault(){}});
 }
 await flush();await flush();
}
(async()=>{
 await invoke();
 if(['cancel','empty'].includes(scenario)){assert.equal(requests.length,0);assert.equal(reloads,0);assert.equal(timers.length,0);return;}
 assert.equal(requests.length,1);
 const request=requests[0],h=new Headers(request.options.headers);
 assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');
 assert.equal(h.get('X-CSRFToken'),'stock-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
 const suffix={complete:'complete',delete:'delete',revert:'revert',copy:'copy',edit:'update'}[p.action];
 const expected=p.action==='import'?'/'+p.page+'/import':p.action==='add'?'/transfer/add':p.action==='batch'?'/'+p.page+'/batch_delete':'/'+p.page+'/7/'+suffix;
 assert.equal(request.url,expected);
 if(p.action==='import'||p.action==='add'||p.action==='edit'){
  assert(request.options.body instanceof FormData);assert.equal(request.options.body.form,form);assert(!h.has('Content-Type'));
  assert.equal(request.options.body.get('remark'),'备注 & 中文');
  if(p.action==='add'){assert.equal(request.options.body.get('from_warehouse'),'A');assert.equal(request.options.body.get('from_location'),'A01');assert.equal(request.options.body.get('to_warehouse'),'B');assert.equal(request.options.body.get('to_location'),'B01');}
 }else if(p.action==='batch'){
  assert.deepEqual(JSON.parse(request.options.body),{ids:['11','12']});assert.equal(h.get('Content-Type'),'application/json');
 }else assert.equal(request.options.body,undefined);
 if(p.action==='import')assert.equal(file.value,'','picker must reset on every result');
 if(scenario==='success'){
  const deferred=p.action==='import'||p.page==='adjustment'||['edit','copy','revert'].includes(p.action);
  if(deferred){assert.equal(reloads,0);assert.equal(timers.length,1);assert.equal(timers[0].ms,p.action==='import'?900:650);timers[0].f();}
  assert.equal(reloads,1);assert.equal(hidden,p.action==='edit'?1:0);
 }else{
  assert.equal(reloads,0);assert.equal(hidden,0);assert.equal(timers.length,0);
  assert(messages.some(m=>m.t==='danger'),'failure must be visible');
  if(['business','http'].includes(scenario))assert(messages.some(m=>m.m.includes('fixture explanation')),'server explanation preserved');
  if(scenario==='html')assert(messages.some(m=>m.m.includes('503')),'non-JSON status preserved');
  if(scenario==='network')assert(messages.some(m=>m.m.includes('offline')),'network explanation preserved');
  if(scenario.startsWith('expired'))assert.equal(ctx.location.href,'/login');
  if(['business','http','html','network'].includes(scenario)){
   scenario='success';file.value='stock.xlsx';await invoke();assert.equal(requests.length,2,'failure remains retryable');
   timers.forEach(t=>t.f());assert.equal(reloads,1);if(p.action==='import')assert.equal(file.value,'');
  }
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node is required to exercise real frontend bindings'
    env = dict(os.environ, NODE_OPTIONS='--max-old-space-size=64')
    result = subprocess.run([node, '-e', program, json.dumps(dict(page=page, action=action, scenario=scenario, script=scripts, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')))], capture_output=True, encoding='utf-8', timeout=15, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
