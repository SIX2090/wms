"""Shared document transport, action mutex, risk confirmation, and rendered roles."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment

ROOT = Path(__file__).resolve().parents[1]
ROLES = ['admin', 'warehouse', 'production', 'purchase', 'sales', 'viewer', 'finance', 'user']
DOCS = ['bom', 'transfer', 'check', 'requisition']


class Controls(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.nodes = []
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


def render(doc, role='admin', completed=False):
    source = (ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    base = '<body class="{% block body_class %}{% endblock %}">{% block content %}{% endblock %}{% block extra_js %}{% endblock %}</body>'
    env = Environment(loader=DictLoader({'base.html': base, 'page': source}), autoescape=True)
    status = ('inactive' if completed else 'active') if doc == 'bom' else ('completed' if completed else 'pending')
    return env.get_template('page').render(current_user=SimpleNamespace(role=role), doc_type=doc,
        readonly=(completed and doc != 'bom') or (doc == 'bom' and role not in ('admin', 'production')),
        can_save=(not completed or doc == 'bom') and (doc != 'bom' or role in ('admin', 'production')),
        can_complete=not completed and doc != 'bom', can_revert=completed and doc != 'bom',
        status=status, page_title='Fixture', icon='bi-fixture', order_id=7, order_no='FIXTURE-7',
        save_url=f'/{doc}/save_table', complete_url='' if doc == 'bom' else f'/{doc}/0/complete',
        revert_url='' if doc == 'bom' else f'/{doc}/7/revert', list_url=f'/{doc}', detail_url=f'/{doc}',
        date_value='2026-10-22', order_no_label='编号', header={'warehouse_id':1,'remark':'fixture'},
        materials=[{'id':11,'code':'M1','price':9,'unit_id':1,'unit':{'name':'个'}}],
        units=[{'id':1,'name':'个'}], existing_items=[], warehouses=[], boms=[], batch_meta=None,
        default_warehouse=None, complete_label='完成', revert_label='反提交', config={},
        csrf_token=lambda:'fixture', url_for=lambda endpoint, **kwargs:'/static/'+kwargs.get('filename',''))


@pytest.mark.parametrize('doc', DOCS)
@pytest.mark.parametrize('role', ROLES)
@pytest.mark.parametrize('completed', [False, True])
def test_actual_template_roles_match_existing_backend_and_preserve_print_view(doc, role, completed):
    html = render(doc, role, completed)
    nodes = Controls(html).nodes
    allowed = role in (['admin','production'] if doc in ('bom','requisition') else ['admin','warehouse'])
    actions = [attrs.get('onclick','') for tag,attrs in nodes if tag=='button']
    assert any(tag=='a' and attrs.get('href')==f'/{doc}/7/print' for tag,attrs in nodes)
    assert any(tag=='a' and attrs.get('href')==f'/{doc}' for tag,attrs in nodes)
    body = next(attrs for tag,attrs in nodes if tag=='body')
    assert ('wms-no-global-actionbar' in body['class']) == (not allowed)
    assert ('const readonly = true;' in html) == (not allowed or completed and doc!='bom')
    if not allowed:
        assert not any(action.startswith(('submitForm(', 'completeDocument(', 'revertDocument(', 'addNewRow(', 'showPasteModal(')) for action in actions)
        for tag,attrs in nodes:
            if attrs.get('name') in ('date','product_code','product_name','version','remark','production_order','picker','purpose'):
                assert 'readonly' in attrs
            if tag=='select':
                assert 'disabled' in attrs
    elif completed and doc!='bom':
        assert 'revertDocument()' in actions
        assert not any(action.startswith(('submitForm(', 'completeDocument(')) for action in actions)
    else:
        assert any(action.startswith('submitForm(') for action in actions)
        assert 'revertDocument()' not in actions


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let pending=[],calls=[],messages=[],issues=[],timers=[],modals={},forceButton=null,sessions=0,confirms=0;
const buttons=p.actions.map(action=>({action,disabled:false}));
const fieldValues={order_id:'7',order_no:'FIXTURE-7',date:'2026-10-22',warehouse_id:'1',bom_id:'2',production_order:'工单 & 1',picker:'张三',purpose:'领料',remark:'备注',from_location:'W1',to_location:'W2',product_code:'P1',product_name:'产品',version:'V1',status:'active'};
const fields=Object.fromEntries(Object.entries(fieldValues).map(([name,value])=>[name,{value}]));
const rowValues={'.material-code':'M1','.unit-id':'1','.line-area':'区域','.system-stock':'2','.actual-stock':'3','.line-reason':'盘盈','.line-qty':'2','.line-price':'0','.line-usage':'用途','.line-remark':'行备注'};
const rowFields=Object.fromEntries(Object.entries(rowValues).map(([key,value])=>[key,{value,style:{}}]));
const row={dataset:{counted:'true'},querySelector:selector=>rowFields[selector]||null};
const document={querySelector:selector=>selector.startsWith('meta')?{content:'fixture-token'}:fields[(selector.match(/name="([^"]+)"/)||[])[1]]||null,
 querySelectorAll:selector=>selector==='#docTableBody tr'?[row]:selector==='.doc-header button, #forceCompleteBtn'?[...buttons,...(forceButton?[forceButton]:[])]:[],
 addEventListener(){},getElementById:id=>id==='forceCompleteBtn'?forceButton:modals[id]||null,
 createElement:()=>({id:'',style:{},innerHTML:'',remove(){delete modals[this.id];forceButton=null;}}),
 body:{appendChild(modal){modals[modal.id]=modal;forceButton={disabled:false,onclick:null};}}};
const ctx={document,FormData:class{},URLSearchParams,showToast:(m,t)=>messages.push({m,t}),confirm:message=>{if(message.includes('登录')){sessions++;return false;}confirms++;return p.scenario!=='cancel';},setTimeout:(fn,delay)=>{timers.push({fn,delay});},location:{href:'/original',reload(){ctx.reloaded=true;}},fetch:(url,options)=>{calls.push({url,options,body:options.body===undefined?undefined:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;
ctx.showDocumentCompletionIssue=(url,result)=>issues.push({url,result});
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const invoke=action=>vm.runInContext(action,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
const evil='业务失败 <img src=x onerror="alert(1)">';
function response(scenario){const status={http:400,http_success:400,html:502,unauthorized:401,expired:419}[scenario]||200;return {ok:status===200,status,json:()=>['html','html200','malformed'].includes(scenario)?Promise.reject(Error('Invalid JSON')):Promise.resolve(scenario==='null'?null:scenario==='confirm'?{status:'confirm',msg:evil,count:1,total:2,samples:[{code:evil,name:evil}]}:['business','http'].includes(scenario)?{status:'error',msg:evil}:{status:'success',id:7,msg:'成功'})};}
const finish=async(index,scenario)=>{if(scenario==='network')pending[index].reject(Error('网络失败'));else pending[index].resolve(response(scenario));await settle();};
function mutex(){const count=calls.length,confirmed=confirms;invoke('submitForm(true)');invoke("runComplete('/force/7',true,7)");invoke('completeDocument()');invoke('revertDocument()');assert.equal(calls.length,count,'all write actions share one mutex');assert.equal(confirms,confirmed);}
function protocol(index,kind){const call=calls[index];assert.equal(call.options.method,'POST');assert.equal(call.options.credentials,'same-origin');assert.equal(call.options.headers['X-CSRFToken'],'fixture-token');if(kind==='revert'){assert.equal(call.body,undefined);assert.equal(call.url,'/'+p.doc+'/7/revert');}else {assert.equal(call.options.headers['Content-Type'],'application/json');if(kind==='complete'){assert.deepEqual(call.body,{force:false});assert.equal(call.url,'/'+p.doc+'/7/complete');}else if(kind==='force'){assert.deepEqual(call.body,{force:true});assert.equal(call.url,'/'+p.doc+'/7/complete');}else {assert.equal(call.url,'/'+p.doc+'/save_table');assert.equal(call.body.order_id,'7');assert.equal(call.body.order_no,'FIXTURE-7');assert.equal(call.body.date,'2026-10-22');assert.equal(call.body.items[0].material_id,11);if(p.doc==='check'){assert.equal(call.body.items[0].actual_stock,3);assert.equal(call.body.header.warehouse_id,'1');}else{assert.equal(call.body.items[0].quantity,2);assert.equal(call.body.items[0].price,0);}if(p.doc==='requisition'){assert.equal(call.body.header.picker,'张三');assert.equal(call.body.header.production_order,'工单 & 1');}}}}
(async()=>{
 if(p.mode==='denied'){invoke('submitForm(true)');invoke("runComplete('/bad',true,7)");invoke('completeDocument()');invoke('revertDocument()');await settle();assert.equal(calls.length,0);assert.equal(confirms,0);process.stdout.write('{}');return;}
 const initial=p.mode==='save'?'submitForm(false)':p.mode==='revert'?'revertDocument()':'submitForm(true)';
 assert(p.actions.includes(initial),initial+' must have a real rendered button');invoke(initial);
 if(p.scenario==='cancel'){assert.equal(calls.length,0);assert.equal(confirms,1);process.stdout.write('{}');return;}
 assert.equal(calls.length,1);mutex();assert(buttons.every(b=>b.disabled));protocol(0,p.mode==='revert'?'revert':'save');
 let index=0,kind=p.mode==='revert'?'revert':'save';
 if(p.mode==='complete'||p.mode==='force'||p.mode==='risk-cancel'){
  await finish(0,'success');assert.equal(calls.length,2);mutex();protocol(1,'complete');index=1;kind='complete';
 }
 if(p.mode==='force'||p.mode==='risk-cancel'){
  await finish(1,'confirm');assert(modals.completeConfirmModal);assert.equal(calls.length,2,'risk confirmation never automatically forces');assert.equal(vm.runInContext('submitForm.pending',ctx),false);assert(!modals.completeConfirmModal.innerHTML.includes('<img'));assert(modals.completeConfirmModal.innerHTML.includes('&lt;img'));
  if(p.mode==='risk-cancel'){modals.completeConfirmModal.remove();assert.equal(calls.length,2);assert.equal(ctx.location.href,'/original');assert(buttons.every(b=>!b.disabled));process.stdout.write('{}');return;}
  const force=forceButton;force.onclick();force.onclick();await settle();assert.equal(calls.length,3);mutex();protocol(2,'force');index=2;kind='force';
 }
 await finish(index,p.scenario);
 if(p.scenario==='success'){
  assert(messages.length>0);assert.equal(issues.length,0);
  mutex();assert(buttons.every(b=>b.disabled));const timer=timers.find(t=>t.delay!==5000);assert(timer);timer.fn();if(p.mode==='revert'){assert(ctx.reloaded);assert.equal(timer.delay,650);}else if(p.doc==='requisition'&&p.scenario==='success'){assert(ctx.location.href.startsWith('/requisition/add?'));const query=new URLSearchParams(ctx.location.href.split('?')[1]);assert.equal(query.get('picker'),'张三');assert.equal(query.get('production_order'),'工单 & 1');}else assert.equal(ctx.location.href,'/'+p.doc+'/7');
 }else if(['complete','force'].includes(p.mode)){
  assert.equal(ctx.location.href,'/original');assert(!timers.some(t=>t.delay!==5000));
  assert.equal(issues.length,1);assert.equal(issues[0].url,'/'+p.doc+'/7');
  if(['business','http'].includes(p.scenario))assert.equal(issues[0].result.message||issues[0].result.msg,evil);
  if(p.scenario==='network')assert.equal(issues[0].result.message,'网络失败');
  mutex();assert(buttons.every(b=>b.disabled));
  if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);
 }else{
  assert(messages.length>0);assert.equal(issues.length,0);
  assert.equal(ctx.location.href,'/original');assert(!timers.some(t=>t.delay!==5000));assert(buttons.every(b=>!b.disabled));assert.equal(vm.runInContext('submitForm.pending',ctx),false);assert(messages.some(m=>m.t==='danger'));if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);
  const count=calls.length;invoke(p.mode==='force'?"runComplete('/check/7/complete',true,7)":initial);assert.equal(calls.length,count+1,'only a fresh manual action retries');await finish(count,'success');if(p.mode==='complete'){assert.equal(calls.length,count+2);await finish(count+1,'success');}
 }
 process.stdout.write(JSON.stringify({calls:calls.length,messages}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def execute(doc, mode, scenario='success', role='admin'):
    node = shutil.which('node')
    assert node, 'Node.js required for shared form callback regression'
    html = render(doc, role, completed=mode=='revert')
    scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
    assert len(scripts)==1
    actions = [attrs['onclick'] for tag,attrs in Controls(html).nodes if tag=='button' and attrs.get('onclick','').startswith(('submitForm(', 'completeDocument(', 'revertDocument('))]
    result = subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(dict(
        doc=doc,mode=mode,scenario=scenario,script=scripts[0],actions=actions,
        api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('doc,mode', [('bom','save'),('requisition','complete'),('check','force'),('transfer','revert')])
@pytest.mark.parametrize('scenario',['success','business','http','http_success','html','html200','malformed','null','unauthorized','expired','network'])
def test_actual_buttons_production_api_feedback_mutex_retry_and_navigation(doc,mode,scenario):
    execute(doc,mode,scenario)


@pytest.mark.parametrize('doc,mode',[('transfer','save'),('check','save'),('transfer','complete'),('check','complete'),('requisition','revert'),('check','revert')])
def test_remaining_shared_document_success_paths(doc,mode):
    execute(doc,mode)


def test_risk_confirmation_cancel_never_forces_or_navigates():
    execute('check','risk-cancel')


def test_revert_confirmation_cancel_never_requests():
    execute('transfer','revert','cancel')


@pytest.mark.parametrize('doc',DOCS)
def test_direct_shared_write_functions_do_nothing_for_finance(doc):
    execute(doc,'denied',role='finance')
