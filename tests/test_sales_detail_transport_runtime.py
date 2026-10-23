"""Sales detail: real Jinja controls and production HTTP/action helpers."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest
from jinja2 import DictLoader, Environment

ROOT=Path(__file__).resolve().parents[1]


class Controls(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


def render(action='confirm',role='sales',status=None,shipped='pending'):
    text=(ROOT/'app/templates/sales_order_detail.html').read_text(encoding='utf-8')
    env=Environment(loader=DictLoader({'page':text,'base.html':'{% block content %}{% endblock %}'}),autoescape=True)
    item=NS(id=13,material=NS(code='M13',name='物料',spec='',unit=None),quantity=5.25,shipped_quantity=1,price=0,tax_rate=0,untaxed_amount=0,tax_amount=0,tax_included_amount=0,amount=0,batch_no='',serial_no='',remark='')
    order=NS(id=7,order_no='SO7',status=status or ('draft' if action in ('confirm','delete') else 'confirmed'),shipment_status=shipped,items=[item],customer=None,salesperson=None,date=None,delivery_date=None,operator=None,created_at=None,remark='',untaxed_amount=0,tax_amount=0,total_amount=0,shipped_amount=0,remaining_amount=0)
    return env.get_template('page').render(order=order,current_user=NS(role=role),shipment_status_label=lambda value:value,related_sales_out_orders=[],url_for=lambda endpoint,**kwargs:'/fixture/'+endpoint)


def function(source,name):
    start=source.index('function '+name+'(');opening=source.index('{',start);depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end+1]
    raise AssertionError(name)


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const requests=[],pending=[],dialogs=[],timers=[],messages=[];let reloaded=0,sessions=0;
const buttons=p.buttons.map(attrs=>({attrs,disabled:false,getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}}));
const inputs=p.inputs.map(attrs=>({dataset:{itemId:attrs['data-item-id']},value:p.scenario==='empty'?'':'2.50'}));
const document={querySelector:()=>({content:'fixture-token'}),querySelectorAll:selector=>selector.includes('selected-outbound-quantity')?inputs:buttons.filter(b=>b.attrs['data-document-action']===(selector.match(/data-document-action="([^"]+)"/)||[])[1]),addEventListener(){}};
const ctx={document,Headers,FormData:class{},location:{href:'/original',reload:()=>reloaded++},setTimeout:(fn,delay)=>timers.push({fn,delay}),showToast:(m,t)=>messages.push({m,t}),showConfirm:(m,o)=>new Promise(resolve=>dialogs.push({resolve,m,o})),confirm:()=>{sessions++;return false;},fetch:(url,options)=>{requests.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;
vm.createContext(ctx);
// Content runs before base footer installs HTTP/action helpers. No top-level dependency allowed.
vm.runInContext(p.script,ctx);vm.runInContext(p.legacy,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper,ctx);
const button=buttons.find(b=>p.action==='selected'?b.attrs.onclick==='createSelectedOutbound()':p.action==='whole'?b.attrs.onclick==='createOutbound()':b.attrs.onclick.includes('/fixture/'+({confirm:'confirm_sales_order',delete:'delete_sales_order',cancel:'cancel_sales_order'}[p.action])));assert(button,'real role/state button');
const click=()=>vm.runInContext(button.attrs.onclick,ctx),settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
function response(s){let status={http:400,http_success:500,html:502,unauthorized:401,expired:419}[s]||200;return {ok:status===200,status,json:()=>['html','html200'].includes(s)?Promise.reject(Error('invalid JSON')):Promise.resolve(s==='null'?null:['business','http'].includes(s)?{status:'error',msg:'fixture refusal'}:{status:'success',msg:p.action==='delete'?'销售订单已删除':'fixture success',url:'/out_order/31'})};}
async function finish(s){if(s==='network')pending.at(-1).reject(Error('fixture offline'));else pending.at(-1).resolve(response(s));await settle();}
function mutex(work){const count=requests.length,d=dialogs.length;assert.equal(ctx.postAction('/fixture/confirm_sales_order','cross'),work);assert.equal(ctx.createOutbound(),work);assert.equal(ctx.createSelectedOutbound(),work);assert.equal(dialogs.length,d);assert.equal(requests.length,count);assert(buttons.every(b=>b.disabled&&b.getAttribute('aria-busy')==='true'));}
async function navigate(work){if(p.action==='delete'){await work;assert.equal(ctx.location.href,'/fixture/sales_order_list');assert.equal(reloaded,0);}else{mutex(work);const t=timers.filter(t=>t.delay===400);assert.equal(t.length,1);t[0].fn();await work;assert.equal(reloaded,p.action==='selected'?0:1);assert.equal(ctx.location.href,p.action==='selected'?'/out_order/31':'/original');}assert(buttons.every(b=>!b.disabled&&b.getAttribute('aria-busy')===null));}
(async()=>{
 const work=click();await settle();
 if(p.scenario==='empty'){await work;assert.equal(dialogs.length,0);assert.equal(requests.length,0);assert(messages.some(m=>m.t==='warning'));assert(buttons.every(b=>!b.disabled));return;}
 assert.equal(dialogs.length,1);assert(dialogs[0].m.includes('？'));assert(dialogs[0].o.title);
 if(p.scenario==='http_success'){dialogs[0].resolve(true);await settle();assert.equal(requests.length,1);assert.equal(new Headers(requests[0].options.headers).get('X-CSRFToken'),'fixture-token');await finish(p.scenario);await work;assert(!messages.some(m=>m.t==='success'),'HTTP failure cannot be successful');assert.equal(reloaded,0);assert.equal(ctx.location.href,'/original');assert(!timers.some(t=>t.delay===400));return;}
 if(p.scenario==='cancel'){const again=click();await settle();assert.equal(dialogs.length,1);assert.equal(again,work);mutex(work);dialogs[0].resolve(false);await work;assert.equal(requests.length,0);assert(buttons.every(b=>!b.disabled));return;}
 dialogs[0].resolve(true);await settle();assert.equal(requests.length,1);
 const again=click();await settle();if(dialogs.length>1){dialogs.at(-1).resolve(true);await settle();}
 assert.equal(requests.length,1,'in-flight repeated action must not dispatch a second POST');assert.equal(dialogs.length,1);assert.equal(again,work);mutex(work);const r=requests[0];assert.equal(r.options.method,'POST');assert.equal(new Headers(r.options.headers).get('X-CSRFToken'),'fixture-token');assert.equal(r.options.headers['X-Requested-With'],'XMLHttpRequest');assert.equal(r.options.credentials,'same-origin');assert.equal(r.url,'/fixture/'+({confirm:'confirm_sales_order',delete:'delete_sales_order',cancel:'cancel_sales_order',whole:'create_sales_outbound_draft',selected:'create_sales_outbound_draft'}[p.action]));
 if(p.action==='selected'){assert.deepEqual(JSON.parse(r.options.body),{items:[{sales_order_item_id:13,quantity:2.5}]});assert.equal(r.options.headers['Content-Type'],'application/json');}else assert.equal(r.options.body,undefined);
 await finish(p.scenario);
 if(p.scenario==='success')await navigate(work);
 else{await work;assert(!messages.some(m=>m.t==='success'));assert(messages.some(m=>m.t==='danger'));assert.equal(reloaded,0);assert.equal(ctx.location.href,'/original');assert(!timers.some(t=>t.delay===400));assert(buttons.every(b=>!b.disabled));if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);assert(!messages.some(m=>m.m.includes('Cannot read')));const retry=click();await settle();assert.equal(dialogs.length,2);dialogs[1].resolve(true);await settle();assert.equal(requests.length,2,'manual retry only');await finish('success');await navigate(retry);}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def execute(action,scenario):
    node=shutil.which('node');assert node,'Node required'
    html=render(action);nodes=Controls(html).nodes
    buttons=[a for tag,a in nodes if tag=='button' and a.get('onclick','').startswith(('postAction(','createOutbound(','createSelectedOutbound('))]
    inputs=[a for tag,a in nodes if tag=='input' and 'selected-outbound-quantity' in a.get('class','')]
    base=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    payload=dict(action=action,scenario=scenario,buttons=buttons,inputs=inputs,script=re.search(r'<script>(.*?)</script>',html,re.S).group(1),legacy='\n'.join(function(base,name) for name in ['getCsrfToken','csrfFetch','csrfPost']),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),helper=(ROOT/'app/static/js/document-action.js').read_text(encoding='utf-8'))
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('action',['confirm','delete','cancel','whole','selected'])
@pytest.mark.parametrize('scenario',['success','cancel','http_success'])
def test_real_operations_keep_payload_confirmation_shared_lock_and_navigation(action,scenario):
    execute(action,scenario)


@pytest.mark.parametrize('action',['confirm','selected'])
@pytest.mark.parametrize('scenario',['business','http','html','html200','null','network','unauthorized','expired'])
def test_failure_visible_without_navigation_and_manual_retry(action,scenario):
    execute(action,scenario)


def test_empty_selection_keeps_original_warning_and_zero_requests():
    execute('selected','empty')


@pytest.mark.parametrize('role',['admin','warehouse','purchase','sales','viewer','finance'])
@pytest.mark.parametrize('status,shipped,expected',[('draft','pending',2),('confirmed','pending',3),('confirmed','shipped',0),('cancelled','pending',0)])
def test_actual_jinja_preserves_existing_roles_and_status_actions(role,status,shipped,expected):
    nodes=Controls(render(role=role,status=status,shipped=shipped)).nodes
    buttons=[a for tag,a in nodes if tag=='button' and a.get('onclick','').startswith(('postAction(','createOutbound(','createSelectedOutbound('))]
    assert len(buttons)==(expected if role in ('admin','warehouse','purchase','sales') else 0)
