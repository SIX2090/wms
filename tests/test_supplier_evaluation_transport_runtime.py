"""Actual supplier loader + shared HTTP client, fake DOM/HTTP only."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = r'''
// WMS_AUDIT_SUPPLIER_RUNTIME: no network/DB/credential/device APIs exposed to VM.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(process.argv[1]);
const template=fs.readFileSync(p.root+'/app/templates/ai_supplier_evaluation.html','utf8');
const start=template.indexOf('function loadSupplierEvaluation()');
const end=template.indexOf('function renderEvalTable',start);
assert(start>=0&&end>start);
const ids=['loadEvalBtn','aiAnalysisCard','aiAnalysisContent','evalCard','emptyStateCard','summaryCards','totalSuppliers','totalAmount','priceUnstable'];
const nodes=Object.fromEntries(ids.map(id=>[id,{style:{display:''},disabled:false,innerHTML:'',textContent:''}]));
const calls=[],renders=[],pending=[];
let confirmCalls=0;
const context={document:{getElementById:id=>nodes[id],querySelector:selector=>selector.includes('csrf-token')?{content:'synthetic-csrf'}:null},
 FormData:class{},setTimeout,confirm(){confirmCalls++;return false;},location:{href:''},currentEvalData:[],
 escapeHtml:text=>String(text??'').replace(/[<>&"']/g,c=>({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;'}[c])),
 renderEvalTable:rows=>renders.push(rows),fetch(url,options){calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
context.window=context;vm.createContext(context);
vm.runInContext(fs.readFileSync(p.root+'/app/static/js/api.js','utf8'),context);
vm.runInContext(template.slice(start,end),context);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
const good={status:'success',summary:{total:1,total_amount:20,price_unstable:0},evaluations:[{supplier_name:'QA-only'}],ai_analysis:'<script>synthetic</script>'};
const response=(status,body)=>({status,ok:status>=200&&status<300,json:async()=>body});
(async()=>{
 context.loadSupplierEvaluation();await settle();assert.equal(calls.length,1);
 if(p.scenario==='duplicate'){context.loadSupplierEvaluation();await settle();assert.equal(calls.length,1,'loader must not duplicate an active model request');}
 if(p.scenario==='network')pending[0].reject(new Error('synthetic network failure'));
 else if(p.scenario==='http500')pending[0].resolve(response(500,good));
 else if(p.scenario==='http401')pending[0].resolve(response(401,good));
 else if(p.scenario==='business')pending[0].resolve(response(200,{status:'error',msg:'synthetic business failure'}));
 else if(p.scenario==='malformed')pending[0].resolve(response(200,{...good,evaluations:{bad:true}}));
 else if(p.scenario==='invalid-summary')pending[0].resolve(response(200,{...good,summary:{...good.summary,total:-1}}));
 else if(p.scenario==='empty')pending[0].resolve(response(200,{status:'success',evaluations:[],msg:'暂无供应商数据'}));
 else pending[0].resolve(response(200,good));
 await settle();assert.equal(nodes.loadEvalBtn.disabled,false,'failed/successful request must release button');
 const success=['success','duplicate'].includes(p.scenario);
 if(success){assert.equal(renders.length,1);assert.equal(nodes.evalCard.style.display,'block');assert.equal(nodes.summaryCards.style.display,'flex');assert(nodes.aiAnalysisContent.innerHTML.includes('&lt;script&gt;'));}
 else if(p.scenario==='empty'){assert.equal(renders.length,0);assert(nodes.aiAnalysisContent.innerHTML.includes('暂无供应商数据'));}
 else{assert.equal(renders.length,0,'failed HTTP/schema must not render successful report');assert.notEqual(nodes.summaryCards.style.display,'flex');assert.notEqual(nodes.evalCard.style.display,'block');assert(!nodes.aiAnalysisContent.innerHTML.includes('spinner-border'));}
 if(p.scenario==='http401')assert.equal(confirmCalls,1,'shared client must preserve expired-session prompt');
 if(p.scenario==='network'||p.scenario==='business'){
   assert.equal(calls.length,1,'no automatic retry');context.loadSupplierEvaluation();await settle();assert.equal(calls.length,2);
   pending[1].resolve(response(200,good));await settle();assert.equal(renders.length,1,'explicit retry can recover');
 }
 process.stdout.write('ok '+p.scenario);
})().catch(error=>{console.error(error);process.exitCode=1;});
'''


@pytest.mark.parametrize('scenario', [
    'success', 'empty', 'http500', 'http401', 'business', 'network',
    'malformed', 'invalid-summary', 'duplicate',
])
def test_supplier_loader_rejects_transport_and_schema_failures(scenario):
    node = shutil.which('node')
    assert node, 'Node is required for the actual JavaScript runtime regression'
    completed = subprocess.run([node, '-e', SCRIPT, json.dumps({'root': ROOT.as_posix(), 'scenario': scenario})],
                               capture_output=True, text=True, timeout=15)
    assert completed.returncode == 0, completed.stdout + completed.stderr
