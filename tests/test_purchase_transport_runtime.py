"""Execute purchase list/request callbacks with production API and error handling."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]


CASES = [(action, scenario) for action in ['import', 'delete', 'copy', 'batch', 'request']
         for scenario in ['success', 'business', 'http', 'html', 'expired401', 'expired419', 'network']]
CASES += [(action, 'cancel') for action in ['delete', 'copy', 'batch']]
CASES += [(action, 'empty') for action in ['import', 'batch', 'request']]
CASES += [('copy', 'success_fallback')]


@pytest.mark.parametrize('action,scenario', CASES)
def test_purchase_actions_preserve_confirmation_payload_feedback_and_retry(action, scenario):
    page = 'purchase_request_add' if action == 'request' else 'purchase_order'
    name = dict(import_='submitImportForm', delete='deletePurchaseOrder', copy='copyPurchaseOrder', batch='batchDeletePurchaseOrders', request='submitForm')['import_' if action == 'import' else action]
    handler = callback(page, 'function ' + name + '(')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let sent=[],messages=[],timers=[],reloads=0,confirmations=0,expired=0;let responseScenario=p.scenario;
const formFields={request_id:'stable-request',request_no:'PR-A',date:'2026-10-22',applicant:'Fixture',department:'Production',urgency:'urgent',expected_date:'2026-10-29',reason:'reason',remark:'note'};
const lines=[{material_id:'7',material_code:'M-7',material_name:'Fixture',unit_id:'2',quantity:'3',estimated_price:'4',supplier_id:'9',supplier_name:'Supplier'}];
class FormData{constructor(form){this.owner=form.id;}get(k){return formFields[k];}}
const file={files:p.scenario==='empty'?[]:[{name:'fixture.xlsx'}],value:'fixture.xlsx',disabled:false};
const ctx={FormData,Headers,document:{getElementById:id=>id==='importFile'?file:{id},querySelector:()=>({content:'fixture-csrf'}),querySelectorAll:()=>[]},
collectItems:()=>p.scenario==='empty'?[]:lines,selectedPurchaseOrderIds:()=>p.scenario==='empty'?[]:['7','8'],showConfirm:()=>{confirmations++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>{expired++;return false;},
showToast:(m,t)=>messages.push({m,t}),setTimeout:fn=>timers.push(fn),location:{href:'original',reload(){reloads++;}},
fetch:(u,o)=>{sent.push({u,o});const status=responseScenario==='http'?400:responseScenario==='html'?503:responseScenario==='expired401'?401:responseScenario==='expired419'?419:200;
return responseScenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:status===200,status,json:()=>responseScenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({status:['business','http'].includes(responseScenario)?'error':'success',msg:'fixture explanation',id:17,redirect_url:responseScenario==='success_fallback'?undefined:'/purchase_order/17/edit?copied=1'})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.handler,ctx);
async function invoke(){await ctx[p.name](7);await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();
if(p.scenario==='cancel'||p.scenario==='empty'){assert.equal(sent.length,0);assert.equal(reloads,0);assert.equal(ctx.location.href,'original');if(p.scenario==='empty'&&p.action!=='import')assert(messages.some(m=>m.t==='warning'));return;}
assert.equal(sent.length,1);const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
if(p.action==='import'){assert(req.o.body instanceof FormData);assert.equal(req.o.body.owner,'importForm');assert(!h.has('Content-Type'));assert.equal(file.value,'','file input reset on all outcomes');assert.equal(file.disabled,false);}
else {const body=JSON.parse(req.o.body);assert.equal(typeof body,'object','JSON encoded exactly once');if(p.action==='batch')assert.deepEqual(body,{ids:['7','8']});else if(p.action==='request')assert.deepEqual(body,{...formFields,items:lines});else assert.deepEqual(body,{});}
if(['delete','copy','batch'].includes(p.action))assert.equal(confirmations,1);
if(p.scenario.startsWith('success')){assert(messages.some(m=>m.t==='success'));for(const fn of timers)fn();if(p.action==='copy')assert.equal(ctx.location.href,p.scenario==='success_fallback'?'/purchase_order/17/edit':'/purchase_order/17/edit?copied=1');else if(p.action==='request')assert.equal(ctx.location.href,'/purchase_request/17');else assert.equal(reloads,1);}
else {assert(messages.some(m=>m.t==='danger'));assert.equal(reloads,0);assert.equal(ctx.location.href,'original');if(['http','business'].includes(p.scenario))assert(messages.some(m=>m.m.includes('fixture explanation')));if(p.scenario==='html')assert(messages.some(m=>m.m.includes('503')));if(p.scenario.startsWith('expired'))assert.equal(expired,1);
responseScenario='success';if(p.action==='import')file.value='fixture.xlsx';await invoke();assert.equal(sent.length,2,'failure leaves action available for retry');assert.equal(messages.at(-1).t,'success');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for real API runtime verification'
    payload = dict(action=action, scenario=scenario, handler=handler, name=name, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
