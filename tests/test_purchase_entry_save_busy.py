"""Purchase entry saves share one in-flight action and preserve its navigation intent."""
import json
from pathlib import Path
import shutil
import subprocess

from bs4 import BeautifulSoup
import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ['pending', 'navigation', 'business', 'http', 'network', 'html',
             'null', 'missing_id', 'invalid_id', 'validation', 'form_throw', 'collect_throw']
CASES = [(kind, mode, save_new, scenario)
         for kind in ['order', 'request'] for mode in ['add', 'edit']
         for save_new in ([False, True] if kind == 'order' else [False])
         for scenario in SCENARIOS]


@pytest.mark.parametrize('kind,mode,save_new,scenario', CASES)
def test_purchase_save_busy_and_recovery(kind, mode, save_new, scenario):
    page = 'purchase_' + kind + '_add'
    source = (ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf-8')
    soup = BeautifulSoup(source, 'html.parser')
    buttons = [dict(button.attrs) for button in soup.select('button[onclick^="submitForm("]')]
    assert len(buttons) == (2 if kind == 'order' else 1)
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let sent=[],waiting=[],timers=[],messages=[],scenario=p.scenario,constructs=0;
const fields=p.kind==='order'?{order_id:p.mode==='edit'?'7':'',order_no:'PO-FIXTURE',date:'2026-10-24',supplier_id:'3',supplier_name:'Supplier',expected_date:'2026-10-28',remark:'note'}:
{request_id:p.mode==='edit'?'7':'',request_no:'PR-FIXTURE',date:'2026-10-24',applicant:'Applicant',department:'Production',urgency:'urgent',expected_date:'2026-10-28',reason:'Reason',remark:'note'};
const lines=[{material_id:'9',material_code:'M9',material_name:'Material',quantity:2,price:0,estimated_price:0,unit_id:'2',supplier_id:'3'}];
function button(attrs,toolbar=false){return {attrs:{...attrs},toolbar,disabled:'disabled' in attrs,
getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=String(v);},removeAttribute(k){delete this.attrs[k];},click(){if(!this.disabled)ctx.submitForm(this.attrs.onclick==='submitForm(true)');}};}
const buttons=p.buttons.map(a=>button(a));
const toolbar=button({title:'保存'},true);buttons.push(toolbar);
const originallyDisabled=button({onclick:'submitForm(false)','aria-busy':'false',disabled:''});buttons.push(originallyDisabled);
const unrelated=button({title:'新增'},true);
const original=buttons.map(b=>({disabled:b.disabled,busy:b.getAttribute('aria-busy')}));
const ctx={Headers,URL,FormData:class{constructor(){constructs++;if(scenario==='form_throw')throw Error('form failed');assert(buttons.slice(0,-1).every(b=>!b.disabled),'capture payload before disabling');}get(k){return fields[k];}},
document:{getElementById:id=>({id}),querySelector:()=>({content:'fixture-csrf'}),querySelectorAll:selector=>{
assert.equal(selector,'button[onclick^="submitForm("], #cbGlobalActionBar button[title="保存"]');return buttons;}},
collectItems:()=>{if(scenario==='collect_throw')throw Error('collect failed');return scenario==='validation'?[]:lines;},
collectPurchaseValidationErrors:()=>scenario==='validation'?[{message:'invalid'}]:[],showPurchaseValidation:()=>{},
showToast:(m,t)=>messages.push({m,t}),setTimeout:(fn,ms)=>{timers.push({fn,ms});},location:{origin:'http://isolated',href:'original'},
fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>waiting.push({resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.handler,ctx);vm.runInContext(p.saveCurrentPage,ctx);
const tick=()=>new Promise(r=>setImmediate(r));
function reply(which,kind){const w=waiting[which];if(kind==='network'){w.reject(Error('offline'));return;}
let body={status:'success',id:17};if(kind==='business')body={status:'error',msg:'Rejected'};
if(kind==='null')body=null;if(kind==='missing_id')body={status:'success'};if(kind==='invalid_id')body={status:'success',id:'../wrong'};
w.resolve({ok:kind!=='http',status:kind==='http'?500:200,json:()=>kind==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve(body)});}
function restored(){buttons.forEach((b,i)=>{assert.equal(b.disabled,original[i].disabled);assert.equal(b.getAttribute('aria-busy'),original[i].busy);});assert.equal(unrelated.disabled,false);}
function busy(){buttons.forEach(b=>{assert.equal(b.disabled,true);assert.equal(b.getAttribute('aria-busy'),'true');});assert.equal(unrelated.disabled,false);}
(async()=>{
ctx.submitForm(p.save_new);
if(['validation','form_throw','collect_throw'].includes(scenario)){
assert.equal(sent.length,0);restored();if(scenario!=='validation')assert(messages.some(m=>m.t==='danger'));scenario='pending';ctx.submitForm(p.save_new);assert.equal(sent.length,1);busy();return;}
assert.equal(sent.length,1);busy();
const payload=JSON.parse(sent[0].o.body);assert.deepEqual(payload,{...fields,[p.kind==='order'?'order_id':'request_id']:p.mode==='edit'?'7':null,items:lines});
assert.equal(sent[0].u,p.kind==='order'?'/purchase_order/save':'/purchase_request/add');assert.equal(sent[0].o.method,'POST');assert.equal(sent[0].o.credentials,'same-origin');assert.equal(new Headers(sent[0].o.headers).get('X-CSRFToken'),'fixture-csrf');
ctx.submitForm(!p.save_new);ctx.saveCurrentPage();assert.equal(sent.length,1,'all entry points share pending lock');assert.equal(constructs,1);
reply(0,['pending','navigation'].includes(scenario)?'success':scenario);await tick();
if(['pending','navigation'].includes(scenario)){
assert(messages.some(m=>m.t==='success'));assert.equal(timers.length,1);busy();
ctx.submitForm(!p.save_new);ctx.saveCurrentPage();assert.equal(sent.length,1,'success keeps lock until navigation');
timers[0].fn();assert.equal(ctx.location.href,p.kind==='request'?'/purchase_request/17':p.save_new?'http://isolated/purchase_order/add?supplier_id=3':'/purchase_order/17');
assert.equal(timers[0].ms,p.kind==='request'?600:p.save_new?400:500);
}else{
assert(messages.some(m=>m.t==='danger'));assert(!messages.some(m=>m.t==='success'));assert.equal(timers.length,0);assert.equal(ctx.location.href,'original');restored();
if(['missing_id','invalid_id'].includes(scenario))assert(messages.some(m=>m.m.includes('核对')));
scenario='pending';ctx.submitForm(p.save_new);assert.equal(sent.length,2,'manual retry after failure');busy();reply(1,'success');await tick();assert(messages.some(m=>m.t==='success'));busy();
}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node is required for runtime regression'
    app_source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    start = app_source.index('function saveCurrentPage()')
    save_current = app_source[start:app_source.index('function getSelectedIds(', start)]
    payload = dict(kind=kind, mode=mode, save_new=save_new, scenario=scenario, buttons=buttons,
                   handler=callback(page, 'function submitForm('), saveCurrentPage=save_current,
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True,
                            text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
