"""Execute purchase-request list callbacks through the production HTTP client."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_frontend_remaining_page_transport import callback

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=['import','approve','reject','revert','delete','batch']
SCENARIOS=['success','business','http','html','invalid_json','null','primitive','expired401','expired419','network']
CASES=[(a,s) for a in ACTIONS for s in SCENARIOS]
CASES += [(a,'cancel') for a in ACTIONS if a!='import']
CASES += [('import','empty'),('batch','empty'),('reject','empty_prompt')]
CASES += [('batch','mixed_'+s) for s in SCENARIOS if s!='success']
CASES += [('batch','reverse_null')]


@pytest.mark.parametrize('action,scenario',CASES)
def test_purchase_request_list_transport_and_summary(action,scenario):
    node=shutil.which('node')
    assert node,'Node required for the production request transport regression'
    name={'import':'submitPurchaseRequestImport','approve':'approveOrder','reject':'rejectOrder','revert':'revertOrder','delete':'deleteOrder','batch':'batchDelete'}[action]
    handler=callback('purchase_request',('async ' if action in ['approve','revert','delete','batch'] else '')+'function '+name+'(')
    program=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let sent=[],messages=[],timers=[],reloads=0,confirms=0,prompts=0,expired=0,responseScenario=p.scenario;
const upload={files:p.scenario==='empty'?[]:[{name:'fixture.xlsx'}],value:'fixture.xlsx'},form={id:'purchaseRequestImportForm'};
class FormData{constructor(owner){this.owner=owner.id;this.rows=[['csrf_token','fixture-token'],['file','fixture.xlsx']];}}
const ctx={FormData,Headers,Promise,console,document:{getElementById:id=>id==='purchaseRequestImportFile'?upload:form,querySelector:()=>({content:'fixture-token'}),querySelectorAll:()=>p.scenario==='empty'?[]:[{value:'7'},{value:'8'}]},
showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},prompt:()=>{prompts++;return p.scenario==='cancel'?null:p.scenario==='empty_prompt'?'':' <b>驳回&A</b> ';},confirm:()=>{expired++;return false;},
showToast:(m,t,duration)=>messages.push({m,t,duration}),setTimeout:(fn,delay)=>timers.push({fn,delay}),location:{href:'original',reload(){reloads++;}},
fetch:(url,options)=>{sent.push({url,options});let s=responseScenario;if(s.startsWith('mixed_'))s=sent.length%2===1?'success':s.slice(6);if(s==='reverse_null')s=sent.length%2===1?'null':'success';const status=s==='http'?409:s==='html'?503:s==='expired401'?401:s==='expired419'?419:200;
if(s==='network')return Promise.reject(Error('网络已断开'));
return Promise.resolve({status,ok:status===200,json:()=>['html','invalid_json'].includes(s)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(s==='null'?null:s==='primitive'?'unexpected':{status:['business','http'].includes(s)?'error':'success',msg:'服务端拒绝原因',data:{status:'error',msg:'must not unwrap'}})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var action='+p.handler,ctx);
async function invoke(){await ctx.action(7);await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();
if(['cancel','empty'].includes(p.scenario)){assert.equal(sent.length,0);assert.equal(reloads,0);if(p.action==='reject')assert.equal(prompts,1);else if(p.scenario==='cancel')assert.equal(confirms,1);return;}
const count=p.action==='batch'?2:1;assert.equal(sent.length,count);
for(const [i,{url,options}] of sent.entries()){assert.equal(url,p.action==='import'?'/purchase_request/import':'/purchase_request/'+(p.action==='batch'?7+i:7)+'/'+(p.action==='batch'?'delete':p.action));assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'fixture-token');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');
if(p.action==='import'){assert(options.body instanceof FormData);assert.equal(options.body.owner,'purchaseRequestImportForm');assert.equal(options.headers['Content-Type'],undefined);assert.equal(upload.value,'');}
else if(p.action==='reject'){assert.deepEqual(JSON.parse(options.body),{remark:p.scenario==='empty_prompt'?'':' <b>驳回&A</b> '});assert.equal(options.headers['Content-Type'],'application/json');}
else assert.equal(options.body,undefined);}
if(p.action==='reject')assert.equal(prompts,1);else if(p.action!=='import')assert.equal(confirms,1);
assert.equal(messages.length,1,'one visible outcome after the full action');assert(!messages[0].m.includes('undefined'));
const mixed=p.scenario.startsWith('mixed_')||p.scenario==='reverse_null';
const success=['success','empty_prompt'].includes(p.scenario);
if(success||mixed){assert.equal(messages[0].t,mixed?'warning':'success');if(p.action==='batch'){assert(messages[0].m.includes(mixed?'已删除 1 条':'已删除 2 条'));if(mixed){assert(messages[0].m.includes('1 条失败'));assert.equal(messages[0].duration,4200);}}
const refresh=timers.filter(x=>x.delay!==5000);assert.equal(refresh.length,1);assert.equal(refresh[0].delay,mixed?1200:p.action==='import'?900:650);refresh[0].fn();assert.equal(reloads,1);}
else{assert.equal(messages[0].t,'danger');assert.equal(timers.filter(x=>x.delay!==5000).length,0);assert.equal(reloads,0);if(['http','business'].includes(p.scenario))assert(messages[0].m.includes('服务端拒绝原因'));if(p.scenario==='html')assert(messages[0].m.includes('503'));}
if(p.scenario.includes('expired'))assert.equal(expired,1);
if(!success){responseScenario='success';if(p.action==='import')upload.value='fixture.xlsx';await invoke();assert.equal(sent.length,count*2,'failed and partially failed actions can retry');assert.equal(messages.at(-1).t,'success');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result=subprocess.run([node,'--max-old-space-size=64','-e',program],
        input=json.dumps(dict(action=action,scenario=scenario,handler=handler,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),
        capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_purchase_request_list_uses_only_shared_transport():
    source=(ROOT/'app/templates/purchase_request.html').read_text(encoding='utf-8')
    assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(',source)
    assert source.count('WMS.api.postRaw(')==7  # six migrations and the existing completion.
