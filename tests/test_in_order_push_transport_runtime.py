"""Run the actual inbound-push DOM listeners and production HTTP client in Node."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let calls=[],pending=[],messages=[],uuidCount=0,sessions=0,buildError=false;
class Control {constructor(value=''){this.value=value;this.disabled=false;this.checked=true;this.handlers={};this.dataset={};this.classList={toggle(){}};}addEventListener(name,fn){this.handlers[name]=fn;}fire(name){return this.handlers[name].call(this);}}
const values={targetType:p.target||'requisition',purpose:'  purpose & <literal>  ',departmentId:'5',picker:'  picker  ',customerId:'9',reason:'  reason  ',lineSearch:'',createDraft:'',selectAll:'',clearAll:'',customerWrap:'',reasonWrap:'',purposeWrap:'',departmentWrap:'',pickerWrap:''};
const nodes=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,new Control(v)]));
const checks=[26,7].map((id,index)=>{const check=new Control();check.dataset.itemId=String(id);const quantity=new Control(index?'2.000':'0.12345678901234567890');const row={hidden:false,dataset:{search:index?'B':'A'},querySelector:selector=>{assert.equal(selector,'.line-quantity');if(buildError)throw new Error('构建载荷失败');return quantity;}};check.closest=()=>row;check.row=row;check.quantity=quantity;return check;});
const document={title:'',getElementById:id=>nodes[id],querySelector:selector=>selector.startsWith('meta')?{content:'fixture-token'}:null,querySelectorAll:selector=>selector==='.line-check:checked'?checks.filter(c=>c.checked):selector==='.line-check:not(:disabled)'?checks.filter(c=>!c.disabled):selector==='.line-check'?checks:selector==='#pushTable tbody tr'?checks.map(c=>c.row):(()=>{throw Error(selector);})()};
const ctx={document,showToast:(message,type)=>messages.push({message,type}),fetch:(url,options)=>{calls.push({url,options,body:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},Promise,location:{href:'/fixture/push'},Date,Math,confirm:()=>{sessions++;return false;},setTimeout:()=>0,FormData:class{}};ctx.window=ctx;
if(p.action!=='fallback')ctx.crypto={randomUUID(){if(p.action==='uuid-error'&&uuidCount++===0)throw Error('UUID 构建失败');return 'fixture-request-'+(++uuidCount);}};
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const click=()=>nodes.createDraft.fire('click');
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const evil='业务拒绝 <img src=x onerror="alert(1)">';
function response(scenario){const status={http:400,http_success:400,html:502,unauthorized:401,expired:419}[scenario]||200;return {ok:status===200,status,json:()=>['html','html200','malformed'].includes(scenario)?Promise.reject(Error('Invalid JSON')):Promise.resolve(scenario==='null'?null:['business','http'].includes(scenario)?{status:'error',msg:evil}:{status:'success',msg:'仅创建草稿，库存未变',url:'/out_order/72',replayed:scenario==='replayed'})};}
const finish=async(index,scenario,work)=>{if(scenario==='network')pending[index].reject(Error('网络失败'));else pending[index].resolve(response(scenario));await work;await settle();};
const payload=(index)=>{const call=calls[index];assert.equal(call.url,'/in_order/41/push');assert.equal(call.options.method,'POST');assert.equal(call.options.headers['Content-Type'],'application/json');assert.equal(call.options.headers['X-CSRFToken'],'fixture-token');assert.equal(call.options.credentials,'same-origin');const body={...call.body};assert.equal(typeof body.request_id,'string');assert(body.request_id.length>0&&body.request_id.length<=100);delete body.request_id;assert.deepEqual(body,{target_type:p.target||'requisition',purpose:'purpose & <literal>',department_id:'5',picker:'picker',customer_id:'9',reason:'reason',items:[{source_item_id:26,quantity:'0.12345678901234567890'},{source_item_id:7,quantity:'2.000'}]});};
(async()=>{
 if(p.action==='transport'){
  const work=click();await click();assert.equal(calls.length,1);assert.equal(nodes.createDraft.disabled,true);payload(0);await finish(0,p.scenario,work);
  if(['success','replayed'].includes(p.scenario)){assert.equal(ctx.location.href,'/out_order/72');assert.equal(nodes.createDraft.disabled,true);await click();assert.equal(calls.length,1);assert(messages.some(m=>m.type==='success'));}
  else {assert.equal(ctx.location.href,'/fixture/push');assert.equal(nodes.createDraft.disabled,false);assert(messages.some(m=>m.type==='danger'));if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);const next=click();assert.equal(calls.length,2);assert.equal(calls[0].body.request_id,calls[1].body.request_id);await finish(1,'replayed',next);assert.equal(ctx.location.href,'/out_order/72');}
 }else if(p.action==='lost-response'){
  const server=new Map();const first=click();server.set(calls[0].body.request_id,72);await finish(0,'network',first);const next=click();const id=calls[1].body.request_id;if(!server.has(id))server.set(id,73);assert.equal(server.size,1,'lost response retry must reuse the original server request');await finish(1,'replayed',next);assert.equal(ctx.location.href,'/out_order/72');
 }else if(p.action==='changed-content'){
  const first=click();await finish(0,'network',first);const a=calls[0].body.request_id;
  const control=p.field==='quantity'?checks[0].quantity:p.field==='selection'?checks[1]:nodes[p.field];const original=p.field==='selection'?control.checked:control.value;
  if(p.field==='selection')control.checked=false;else control.value=p.field==='targetType'?'other_out':original+'-changed';
  const second=click();await finish(1,'network',second);assert.notEqual(calls[1].body.request_id,a);
  if(p.field==='selection')control.checked=original;else control.value=original;
  const third=click();await finish(2,'network',third);assert.equal(calls[2].body.request_id,a,'A to B to A must reuse A request');
 }else if(p.action==='filter-only'){
  const first=click();await finish(0,'network',first);nodes.lineSearch.value='B';nodes.lineSearch.fire('input');const next=click();assert.equal(calls[1].body.request_id,calls[0].body.request_id);await finish(1,'network',next);
 }else if(p.action==='empty'){
  checks.forEach(c=>c.checked=false);await click();assert.equal(calls.length,0);assert.equal(nodes.createDraft.disabled,false);assert(messages.some(m=>m.type==='warning'));checks[0].checked=true;const next=click();await finish(0,'success',next);
 }else if(['uuid-error','build-error'].includes(p.action)){
  buildError=p.action==='build-error';await click();assert.equal(calls.length,0);assert.equal(nodes.createDraft.disabled,false);assert(messages.some(m=>m.type==='danger'));buildError=false;const next=click();assert.equal(calls.length,1);await finish(0,'success',next);
 }else if(p.action==='fallback'){
  const work=click();assert.equal(calls.length,1);payload(0);await finish(0,'network',work);const next=click();assert.equal(calls[1].body.request_id,calls[0].body.request_id);await finish(1,'success',next);
 }else throw Error('Unknown action');
 process.stdout.write(JSON.stringify({calls:calls.length,messages}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(action, scenario='success', target='requisition', field='purpose'):
    node = shutil.which('node')
    assert node, 'Node.js required to execute inbound push callbacks'
    source = (ROOT / 'app/templates/in_order_push.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', source, re.S)
    assert script
    rendered = Environment().from_string(script.group(1)).render(
        order=SimpleNamespace(order_no='IN-FIXTURE', id=41),
        csrf_token=lambda: 'fixture-token', url_for=lambda endpoint, id: f'/in_order/{id}/push')
    result = subprocess.run([node, '--max-old-space-size=64', '-e', PROGRAM],
                            input=json.dumps(dict(action=action, scenario=scenario, target=target, field=field,
                                script=rendered, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('target', ['requisition', 'other_out', 'after_sale_out'])
@pytest.mark.parametrize('scenario', ['success', 'replayed', 'business', 'http', 'http_success', 'html',
                                     'html200', 'malformed', 'null', 'unauthorized', 'expired', 'network'])
def test_actual_create_listener_transport_fields_retry_and_navigation(target, scenario):
    run('transport', scenario, target)


def test_committed_request_with_lost_response_reuses_the_same_draft_on_manual_retry():
    run('lost-response')


@pytest.mark.parametrize('field', ['targetType', 'purpose', 'departmentId', 'picker', 'customerId', 'reason', 'quantity', 'selection'])
def test_changed_payload_gets_new_id_and_returning_to_original_reuses_original_id(field):
    run('changed-content', field=field)


def test_filter_only_changes_do_not_rotate_request_id():
    run('filter-only')


@pytest.mark.parametrize('action', ['empty', 'uuid-error', 'build-error', 'fallback'])
def test_local_validation_uuid_fallback_and_build_errors_recover_for_manual_retry(action):
    run(action)
