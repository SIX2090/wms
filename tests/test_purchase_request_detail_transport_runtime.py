"""Purchase request detail: actual Jinja buttons, shared action helper and HTTP client."""
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment

ROOT=Path(__file__).resolve().parents[1]


class Controls(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


def render(action):
    source=(ROOT/'app/templates/purchase_request_detail.html').read_text(encoding='utf-8')
    env=Environment(loader=DictLoader({'page':source,'base.html':'{% block content %}{% endblock %}{% block extra_js %}{% endblock %}'}),autoescape=True)
    from utils import format_quantity
    env.filters['quantity'] = format_quantity
    order=SimpleNamespace(id=7,request_no='PR7',date=date(2026,10,23),applicant='fixture',department='采购',urgency='normal',
        expected_date=None,status='pending' if action in ('approve','reject') else 'approved',operator=None,reason='',remark='',total_amount=0)
    items=[SimpleNamespace(id=item_id,material_id=11,material=None,material_code='M'+str(item_id),material_name='物料',spec='',unit=None,
        quantity=quantity,estimated_price=0,estimated_amount=0,supplier=None,supplier_name='') for item_id,quantity in [(13,5.25),(29,3)]]
    return env.get_template('page').render(current_user=SimpleNamespace(role='purchase'),order=order,related_purchase_orders=[],valid_items=items,
        item_execution={},item_purchase_orders={},config={},url_for=lambda endpoint,**kwargs:'/fixture/'+endpoint)


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let requests=[],pending=[],timers=[],confirms=0,prompts=0,sessions=0,reloaded=0,messages=[],focused=0;
class Button {constructor(attrs){this.attrs={...attrs};this.disabled='disabled' in attrs;}getAttribute(key){return this.attrs[key]??null;}setAttribute(key,value){this.attrs[key]=value;}removeAttribute(key){delete this.attrs[key];}}
const buttons=p.buttons.map(attrs=>new Button(attrs));
const checks=p.checks.map(attrs=>({checked:true,disabled:'disabled' in attrs,dataset:{itemId:attrs['data-item-id']}}));
const qtys=Object.fromEntries(p.quantities.map(attrs=>[attrs['data-item-id'],{value:attrs.value,getAttribute:key=>attrs[key]??null,focus:()=>focused++}]));
const rejectButton=buttons.find(b=>b.attrs.onclick.startsWith('rejectOrder('));
const document={addEventListener(){},getElementById(){return null;},querySelector(selector){if(selector.startsWith('meta'))return {content:'fixture-token'};if(selector.includes('data-purchase-request-action="rejectOrder"')||selector.includes('data-document-action="rejectOrder"'))return rejectButton;const id=(selector.match(/data-item-id="([^"]+)"/)||[])[1];return qtys[id]||null;},querySelectorAll(selector){if(selector.startsWith('button[data-document-action=')){const key=(selector.match(/data-document-action="([^"]+)"/)||[])[1];return buttons.filter(button=>button.attrs['data-document-action']===key);}return selector.includes(':checked')?checks.filter(c=>c.checked):selector.includes(':not(:disabled)')?checks.filter(c=>!c.disabled):[];}};
const remark='  <literal> reason &  ';
const ctx={document,Headers,FormData:class{},showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},showToast:(m,t)=>messages.push({m,t}),setTimeout:(fn,delay)=>timers.push({fn,delay}),location:{href:'/original',reload:()=>reloaded++},confirm:()=>{sessions++;return false;},fetch:(url,options)=>{requests.push({url,options,body:options.body===undefined?undefined:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},WMS:{prompt:(message,options)=>{prompts++;assert.equal(options.returnFocus,rejectButton);return Promise.resolve(p.scenario==='cancel'?null:remark);}}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.legacy,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.script,ctx);
const actionName={approve:'approveOrder',revert:'revertOrder',reject:'rejectOrder',complete:'completeOrder',create:'createPurchaseOrder',selected:'createPurchaseOrder'}[p.action];
const button=buttons.find(b=>b.attrs.onclick.startsWith(actionName+'(')&&(p.action!=='selected'||b.attrs.onclick.includes('true')));
assert(button,'use a real role/state-rendered button');
const click=()=>vm.runInContext(button.attrs.onclick,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
function crossActionMutex(work){const count=requests.length,dialogs=confirms+prompts;for(const name of ['approveOrder','rejectOrder','revertOrder','completeOrder','createPurchaseOrder'])assert.equal(ctx[name](7),work,'all action names must reuse the page promise');assert.equal(requests.length,count);assert.equal(confirms+prompts,dialogs);assert(buttons.every(b=>b.disabled));assert(buttons.every(b=>b.getAttribute('aria-busy')==='true'));}
function response(scenario){const status={http:400,http_success:400,html:502,unauthorized:401,expired:419}[scenario]||200;return {ok:status===200,status,json:()=>['html','html200'].includes(scenario)?Promise.reject(new SyntaxError('Invalid JSON')):Promise.resolve(scenario==='null'?null:['business','http'].includes(scenario)?{status:'error',msg:'fixture business refusal'}:{status:'success',id:31,msg:'fixture success',...(scenario==='fallback'?{}:{redirect_url:'/purchase_order/31?source=fixture'})})};}
const finish=async(index,scenario)=>{if(scenario==='network')pending[index].reject(Error('fixture offline'));else pending[index].resolve(response(scenario));await settle();};
async function navigate(work){crossActionMutex(work);const relevant=timers.filter(t=>t.delay!==5000);assert.equal(relevant.length,1);const timer=relevant[0];assert.equal(timer.delay,['create','selected'].includes(p.action)?500:650);timer.fn();await work;await settle();assert(buttons.every(b=>!b.disabled));assert(buttons.every(b=>b.getAttribute('aria-busy')===null));}
(async()=>{
 if(p.action==='selected'&&['zero','over','nan','empty'].includes(p.scenario)){if(p.scenario==='empty')checks.forEach(c=>c.checked=false);else qtys['13'].value={zero:'0',over:'6',nan:'not-number'}[p.scenario];await click();await settle();assert.equal(requests.length,0);assert.equal(confirms,0);assert(messages.some(m=>m.t==='warning'));assert(buttons.every(b=>!b.disabled));process.stdout.write('{}');return;}
 if(['approve','revert','create'].includes(p.action)&&p.scenario==='http_success'){
  const work=click();await settle();assert.equal(requests.length,1);assert.equal(new Headers(requests[0].options.headers).get('X-CSRFToken'),'fixture-token');await finish(0,'http_success');await work;assert(!messages.some(m=>m.t==='success'),'HTTP failure must not report success');assert(!timers.some(t=>t.delay!==5000),'HTTP failure must not schedule navigation');assert.equal(reloaded,0);assert.equal(ctx.location.href,'/original');assert(buttons.every(b=>!b.disabled));process.stdout.write('{}');return;
 }
 const work=click(),again=click();await settle();
 if(p.scenario==='cancel'){await work;assert.equal(requests.length,0);assert.equal(confirms+prompts,1);assert(buttons.every(b=>!b.disabled));process.stdout.write('{}');return;}
 assert.equal(requests.length,1,'repeated click must not send duplicate requests');assert.equal(work,again);crossActionMutex(work);assert.equal(confirms+prompts,1);const request=requests[0];const endpoint=['create','selected'].includes(p.action)?'create_purchase_order':p.action;assert.equal(request.url,'/purchase_request/7/'+endpoint);assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');assert.equal(request.options.headers['X-CSRFToken'],'fixture-token');assert.equal(request.options.headers['X-Requested-With'],'XMLHttpRequest');
 if(p.action==='selected'){assert.deepEqual(request.body,{items:[{purchase_request_item_id:'13',quantity:5.25},{purchase_request_item_id:'29',quantity:3}]});assert.equal(request.options.headers['Content-Type'],'application/json');}else if(p.action==='reject')assert.deepEqual(request.body,{remark});else if(p.action==='complete')assert.deepEqual(request.body,{});else assert.equal(request.options.body,undefined);
 crossActionMutex(work);await finish(0,p.scenario);
 if(['success','fallback'].includes(p.scenario)){await navigate(work);if(['create','selected'].includes(p.action))assert.equal(ctx.location.href,p.scenario==='fallback'?'/purchase_order/31':'/purchase_order/31?source=fixture');else assert.equal(reloaded,1);}
 else {await work;assert.equal(reloaded,0);assert.equal(ctx.location.href,'/original');assert(!timers.some(t=>t.delay!==5000));assert(buttons.every(b=>!b.disabled));assert(messages.some(m=>m.t==='danger'));assert(!messages.some(m=>m.t==='success'));assert(!messages.some(m=>m.m.includes('Cannot read')));if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);const retry=click();await settle();assert.equal(requests.length,2,'failure does not auto resend; manual retry remains available');await finish(1,'success');await navigate(retry);}
 process.stdout.write(JSON.stringify({requests:requests.length,messages}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def source_function(source,name):
    start=source.index('function '+name+'(')
    opening=source.index('{',start)
    depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:
            return source[start:end+1]
    raise AssertionError('Unclosed production legacy helper')


def execute(action,scenario='success'):
    node=shutil.which('node');assert node,'Node.js required for real detail callbacks'
    html=render(action);controls=Controls(html).nodes
    buttons=[attrs for tag,attrs in controls if tag=='button' and attrs.get('onclick','').startswith(('approveOrder(', 'rejectOrder(', 'revertOrder(', 'completeOrder(', 'createPurchaseOrder('))]
    checks=[attrs for tag,attrs in controls if tag=='input' and 'push-item-check' in attrs.get('class','').split()]
    quantities=[attrs for tag,attrs in controls if tag=='input' and 'push-item-qty' in attrs.get('class','').split()]
    script=re.search(r'<script>(.*?)</script>',html,re.S);assert script
    base=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    legacy='\n'.join(source_function(base,name) for name in ('getCsrfToken','csrfFetch'))
    payload=dict(legacy=legacy,action=action,scenario=scenario,buttons=buttons,checks=checks,quantities=quantities,script=script.group(1),
        api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),helper=(ROOT/'app/static/js/document-action.js').read_text(encoding='utf-8'))
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('action',['approve','reject','revert','complete','create','selected'])
@pytest.mark.parametrize('scenario',['success','cancel'])
def test_real_buttons_preserve_manual_boundary_payload_and_shared_lock_until_navigation(action,scenario):
    execute(action,scenario)


@pytest.mark.parametrize('action',['approve','revert','create'])
@pytest.mark.parametrize('scenario',['business','http','http_success','html','null','network'])
def test_migrated_requests_show_failures_without_false_success_and_allow_manual_retry(action,scenario):
    execute(action,scenario)


@pytest.mark.parametrize('action,scenario',[('approve','unauthorized'),('approve','expired'),('create','html200'),('reject','null'),('complete','null')])
def test_session_expiry_invalid_response_and_existing_wrapped_actions_remain_visible(action,scenario):
    execute(action,scenario)


@pytest.mark.parametrize('scenario',['zero','over','nan','empty'])
def test_existing_selected_quantity_validation_prevents_confirmation_and_request(scenario):
    execute('selected',scenario)


def test_create_purchase_order_keeps_id_navigation_fallback():
    execute('create','fallback')
