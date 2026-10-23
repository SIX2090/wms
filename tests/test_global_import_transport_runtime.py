"""Actual configured global import modal + production API; synthetic file only."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('path', ['/sales/add', '/material'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_json', 'html', 'invalid_json', 'null', 'network', '401', '419', 'form_error', 'no_file'])
def test_global_import_real_modal(path, scenario):
    text = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    modules = text[text.index('const WMS_ACTION_MODULES ='):text.index('function getWmsActionModule()')]
    functions = [re.search(r'^function ' + name + r'\([^\n]*\) \{[\s\S]*?^\}', text, re.M)[0]
                 for name in ['getWmsActionModule', 'showImportModalForModule']]
    source = modules + '\n' + '\n'.join(functions)
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario,resolveRequest,inserted=0,removed=0,shown=0,hidden=0,reloads=0;
const requests=[],messages=[],timers=[],handlers={};
const file={name:'synthetic.xlsx'},input={disabled:false,files:mode==='no_file'?[]:[file]};
const submit={disabled:false,addEventListener:(e,fn)=>handlers.click=fn};
const modalEl={remove(){removed++;}};
const document={querySelector:()=>({content:'fixture-csrf'}),getElementById:id=>id==='cbGlobalImportModal'?(inserted?modalEl:null):id==='cbGlobalImportFile'?input:submit,
body:{insertAdjacentHTML:(pos,html)=>{inserted++;assert(html.includes('data-bs-dismiss="modal"'),'manual dismiss remains available');assert(html.includes('accept=".xlsx,.xls"'));}}};
class TestFormData{constructor(){if(mode==='form_error')throw Error('synthetic FormData error');this.values=[];}append(k,v){assert.equal(input.disabled,false,'capture file before disabling input');this.values.push([k,v]);}}
const ctx={URL,URLSearchParams,Headers,FormData:TestFormData,document,showToast:(m,t)=>messages.push({m,t}),confirm:()=>false,
bootstrap:{Modal:class{show(){shown++;}hide(){hidden++;}}},location:{pathname:p.path,href:'original',reload(){reloads++;}},setTimeout:(fn,delay)=>timers.push({fn,delay}),
fetch:(url,options)=>{requests.push({url,options});return new Promise((resolve,reject)=>resolveRequest=()=>{
 if(mode==='network'){reject(Error('synthetic offline'));return;}
 const status=mode==='http_json'?400:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
 const body=mode==='null'?null:{status:['business','http_json'].includes(mode)?'error':'success',msg:'specific import reason'};
 resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});
})}};
ctx.csrfFetch=(url,options)=>ctx.fetch(url,{credentials:'same-origin',...options,headers:{...options.headers,'X-CSRFToken':'fixture-csrf'}});
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const module=ctx.getWmsActionModule();assert.equal(module.key,p.path==='/material'?'material':'sales');
 ctx.showImportModalForModule(module);assert.equal(inserted,1);assert.equal(shown,1);assert.equal(removed,0);
 const first=handlers.click();await flush();
 if(mode==='no_file'){assert.equal(requests.length,0);assert.equal(messages.at(-1).t,'warning');assert.equal(!!ctx.showImportModalForModule.busy,false);return;}
 if(mode!=='form_error'){
  assert.equal(requests.length,1);assert(submit.disabled);assert(input.disabled);
  await handlers.click();ctx.showImportModalForModule(module);ctx.showImportModalForModule({key:'other',importUrl:'/other/import'});
  assert.equal(requests.length,1);assert.equal(inserted,1,'reopening must not replace an active modal');assert.equal(removed,0);
  const req=requests[0],h=new Headers(req.options.headers);assert.equal(req.url,module.importUrl);assert.equal(req.options.method,'POST');assert.equal(req.options.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');assert(!h.has('Content-Type'));assert(req.options.body instanceof TestFormData);assert.equal(req.options.body.values[0][0],'file');assert.equal(req.options.body.values[0][1],file);
  resolveRequest();await first;await flush();
 }else{await first;assert.equal(requests.length,0);assert(messages.at(-1).m.includes('synthetic FormData error'));}
 if(mode==='success'){
  assert.equal(hidden,1);assert.equal(reloads,0);assert.equal(messages.at(-1).t,'success');assert.equal(timers.length,1);assert.equal(timers[0].delay,800);
  await handlers.click();ctx.showImportModalForModule(module);assert.equal(requests.length,1);assert.equal(inserted,1);timers[0].fn();assert.equal(reloads,1);
 }else{
  assert.equal(hidden,0);assert.equal(reloads,0);assert.equal(messages.at(-1).t,'danger');assert.equal(submit.disabled,false);assert.equal(input.disabled,false);assert.equal(!!ctx.showImportModalForModule.busy,false);assert(!timers.some(t=>t.delay===800));
  if(['business','http_json'].includes(mode))assert(messages.at(-1).m.includes('specific import reason'));if(mode==='html')assert(messages.at(-1).m.includes('503'));
  const before=requests.length;mode='success';const retry=handlers.click();await flush();assert.equal(requests.length,before+1);resolveRequest();await retry;assert.equal(hidden,1);assert.equal(messages.at(-1).t,'success');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'source': source, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'path': path, 'scenario': scenario,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
