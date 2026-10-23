"""Execute real shared list helper and both consumers with the production API."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def object_config(source):
    start = source.index('bindListActions({') + len('bindListActions(')
    depth = 0
    for end in range(start, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError('missing config')


@pytest.mark.parametrize('page', ['sales_order', 'sales_outbound_list'])
@pytest.mark.parametrize('mode', ['one', 'batch'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_success_body', 'null', 'html', 'network', 'cancel'])
def test_real_consumers_shared_transport(page, mode, scenario):
    run(page, mode, scenario)


@pytest.mark.parametrize('page', ['sales_order', 'sales_outbound_list'])
def test_batch_partial_keeps_original_refresh(page):
    run(page, 'batch', 'partial')


@pytest.mark.parametrize('scenario', ['success', 'business', 'callback_throw', 'callback_reject'])
def test_custom_copy_callback_and_navigation_lock(scenario):
    run('sales_order', 'copy', scenario)


@pytest.mark.parametrize('scenario', ['401', '419', 'empty'])
def test_session_and_empty_selection(scenario):
    run('sales_order', 'batch', scenario)


def run(page, mode, scenario):
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    start = base.index('    function bindListActions(opts)')
    helper = base[start:base.index('    // SM-P6-03-3: 通用分页', start)]
    config = object_config((ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf-8'))
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let scenario=p.scenario,resolveConfirm,resolveRequest,reloads=0,href='original';const sent=[],confirms=[],messages=[],timers=[],tableEvents={},toolbarEvents={};
const checks=[{value:'7',checked:true,disabled:false},{value:'8',checked:true,disabled:false},{value:'9',checked:false,disabled:true}],master={checked:true,addEventListener:(e,f)=>master[e]=f};
const rows=[{disabled:false,dataset:{}},{disabled:true,dataset:{}}],batchButtons=[{disabled:false,dataset:{batchAction:'batchDelete'}},{disabled:true,dataset:{batchAction:'batchDelete'}}];
const table={contains:b=>rows.includes(b),addEventListener:(e,f)=>tableEvents[e]=f,querySelectorAll:s=>s==='[data-action]'?rows:s.includes(':not(:disabled)')?checks.filter(c=>!c.disabled):s.includes(':checked')?(scenario==='empty'?[]:checks.filter(c=>c.checked)):checks};
const toolbar={addEventListener:(e,f)=>toolbarEvents[e]=f,querySelectorAll:()=>batchButtons};
const doc={getElementById:()=>table,querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:s==='.wms-entry-toolbar'?toolbar:master};
const ctx={Headers,FormData,document:doc,encodeURIComponent,console,showToast:(m,t)=>messages.push({m,t}),
showConfirm:(m,opts)=>{confirms.push({m,opts});return new Promise(r=>resolveConfirm=r);},confirm:()=>false,
setTimeout:(fn,delay)=>timers.push({fn,delay}),location:{get href(){return href;},set href(v){href=v;},reload(){reloads++;}},
fetch:(url,options)=>{sent.push({url,options});return new Promise((resolve,reject)=>resolveRequest=()=>{
 if(scenario==='network'){reject(Error('fixture offline'));return;}
 const status=scenario==='http_success_body'?409:scenario==='html'?503:['401','419'].includes(scenario)?Number(scenario):200;
 const body=scenario==='null'?null:{status:scenario==='business'?'error':scenario==='partial'?'partial':'success',msg:'specific backend explanation',id:12};
 resolve({ok:status===200,status,json:()=>scenario==='html'?Promise.reject(SyntaxError('HTML response')):Promise.resolve(body)});
})}};
// Keep the real legacy dependency runnable for R8: old source must fail on behavior, not a missing helper.
ctx.csrfFetch=(url,options)=>ctx.fetch(url,{credentials:'same-origin',...options,headers:{...options.headers,'X-CSRFToken':'fixture-csrf','X-Requested-With':'XMLHttpRequest'}});
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper,ctx);vm.runInContext('var opts = '+p.config+';',ctx);
const opts=ctx.opts,key=p.mode==='copy'?'copy':p.page==='sales_order'?'confirm':'complete';
rows[0].dataset={action:key,id:'7 /甲'};
const api=ctx.bindListActions(opts);assert.equal(typeof api.selectedIds,'function');assert.equal(typeof api.runOne,'function');assert.equal(typeof api.runBatch,'function');
master.change();assert(checks[0].checked&&checks[1].checked);assert.equal(checks[2].checked,false,'disabled rows never become checked through master');
assert.deepEqual(Array.from(api.selectedIds()),scenario==='empty'?[]:['7','8']);
if(scenario==='callback_throw')opts.endpoints.copy.onSuccess=()=>{throw Error('fixture callback error');};
if(scenario==='callback_reject')opts.endpoints.copy.onSuccess=()=>Promise.reject(Error('fixture callback error'));
const first=()=>p.mode==='batch'?toolbarEvents.click({target:{closest:()=>batchButtons[0]},preventDefault(){}}):tableEvents.click({target:{closest:()=>rows[0]},preventDefault(){}});
const flush=()=>new Promise(r=>setImmediate(r));
const restored=()=>assert.deepEqual([...rows,...batchButtons].map(b=>b.disabled),[false,true,false,true]);
(async()=>{
 first();await flush();
 if(scenario==='empty'){assert.equal(confirms.length,0);assert.equal(sent.length,0);assert.equal(messages.at(-1).t,'warning');restored();return;}
 assert.equal(confirms.length,1);assert(confirms[0].opts.title.includes('销售'));
 // Let the HTTP-success-body regression reach the real legacy transport before asserting its outcome.
 if(scenario!=='http_success_body'){
  assert([...rows,...batchButtons].every(b=>b.disabled),'lock begins before human confirmation');
  api.runOne(opts.endpoints[key],'different');api.runBatch(opts.endpoints.batchDelete);await flush();assert.equal(confirms.length,1,'one binding mutex covers single, another row and batch');
 }
 resolveConfirm(scenario!=='cancel');await flush();
 if(scenario==='cancel'){assert.equal(sent.length,0);restored();return;}
 assert.equal(sent.length,1);const req=sent[0],h=new Headers(req.options.headers);assert.equal(req.options.method,'POST');
 assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');assert.equal(req.options.credentials,'same-origin');
 if(p.mode==='batch'){assert.equal(req.url,opts.endpoints.batchDelete.url);assert.deepEqual(JSON.parse(req.options.body),{ids:['7','8']});}
 else{assert.equal(req.url,opts.endpoints[key].url.replace('{id}',encodeURIComponent('7 /甲')));assert.equal(req.options.body,undefined,'single operation keeps body absent');}
 if(scenario!=='http_success_body'){first();await flush();assert.equal(sent.length,1);assert.equal(confirms.length,1);}
 resolveRequest();await flush();await flush();
 if(['success','partial'].includes(scenario)){
  assert.equal(messages.at(-1).t,'success');assert.equal(timers.length,1);assert.equal(timers[0].delay,p.mode==='copy'?500:600);assert.equal(reloads,0);assert.equal(href,'original');
  first();api.runBatch(opts.endpoints.batchDelete);await flush();assert.equal(sent.length,1);assert.equal(confirms.length,1,'success delay remains locked');
  timers[0].fn();if(p.mode==='copy')assert.equal(href,'/sales/12/edit');else assert.equal(reloads,1);
 }else{
  assert.equal(messages.at(-1).t,'danger');assert.equal(reloads,0);assert.equal(href,'original');assert(!timers.some(t=>[500,600].includes(t.delay)));restored();
  if(['business','http_success_body'].includes(scenario))assert(messages.at(-1).m.includes('specific backend explanation'));if(scenario==='html')assert(messages.at(-1).m.includes('503'));if(scenario.startsWith('callback_'))assert(messages.at(-1).m.includes('fixture callback error'));
  scenario='success';if(p.mode==='copy')opts.endpoints.copy.onSuccess=()=>{};
  first();await flush();resolveConfirm(true);await flush();assert.equal(sent.length,2);resolveRequest();await flush();
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, '-e', program], input=json.dumps({
        'helper': helper, 'config': config, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'page': page, 'mode': mode, 'scenario': scenario,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
