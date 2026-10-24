"""Requisition location controls, warehouse changes, payloads, and continuation URLs."""
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
LOCATION = 'A区 & B+ "号"'


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.fields = {}
        self.current_select = None
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.nodes.append((tag,attrs))
        if tag in ('input','select','textarea') and attrs.get('name'):
            self.fields[attrs['name']] = dict(attrs)
            if tag=='select':
                self.current_select = attrs['name']
                self.fields[attrs['name']]['options'] = []
        if tag=='option' and self.current_select:
            field = self.fields[self.current_select]
            field['options'].append(attrs)
            if 'selected' in attrs or len(field['options'])==1:
                field['value'] = attrs.get('value','')
    def handle_endtag(self, tag):
        if tag=='select':
            self.current_select = None


def environment():
    base='<body>{% block content %}{% endblock %}{% block extra_js %}{% endblock %}</body>'
    env=Environment(loader=ChoiceLoader([DictLoader({'base.html':base}),FileSystemLoader(ROOT/'app/templates')]),autoescape=True)
    def url_for(endpoint, **kwargs):
        urls={'save_requisition_table':'/requisition/save_table','complete_requisition':'/requisition/'+str(kwargs.get('id',0))+'/complete',
              'requisition_detail':'/requisition/'+str(kwargs.get('id',7)),'revert_requisition':'/requisition/'+str(kwargs.get('id',0))+'/revert',
              'add_requisition':'/requisition/add','requisition_list':'/requisition','static':'/static/'+kwargs.get('filename','')}
        return urls.get(endpoint,'/'+endpoint)
    env.globals['url_for']=url_for
    return env


def form(enabled=True, completed=False, role='production', location=LOCATION):
    header={'warehouse_id':1,'warehouse':'仓库A','location':location,'bom_id':'2','production_order':'工单1','purpose':'用途','picker':'李四','remark':'备注'}
    html=environment().get_template('document_table_form.html').render(
        current_user=SimpleNamespace(role=role),doc_type='requisition',readonly=completed,can_save=not completed,
        can_complete=not completed,can_revert=completed,order_id=7,order_no='REQ7',date_value='2026-10-23',status='completed' if completed else 'pending',
        page_title='领料',icon='bi-fixture',order_no_label='单号',save_url='/requisition/save_table',complete_url='/requisition/0/complete',
        revert_url='/requisition/7/revert',detail_url='/requisition',list_url='/requisition',header=header,
        materials=[{'id':11,'code':'M1','price':1,'unit_id':1,'unit':{'name':'个'}}],units=[{'id':1,'name':'个'}],existing_items=[],
        warehouses=[SimpleNamespace(id=1,name='仓库A'),SimpleNamespace(id=2,name='仓库B')],default_warehouse=None,boms=[],config={},
        location_management_enabled=enabled,csrf_token=lambda:'fixture')
    return html


@pytest.mark.parametrize('enabled',[False,True])
@pytest.mark.parametrize('completed',[False,True])
@pytest.mark.parametrize('role',['admin','production','finance'])
def test_rendered_location_is_required_only_when_enabled_and_preserves_historical_value(enabled,completed,role):
    markup=Markup(form(enabled,completed,role))
    field=markup.fields.get('location')
    assert field is not None
    assert field['value']==LOCATION
    assert field['type']==('text' if enabled else 'hidden')
    assert ('required' in field)==enabled
    if enabled:
        assert field['maxlength']=='100'
        assert field['id']=='requisitionLocation'
        assert any(tag=='label' and attrs.get('for')==field['id'] for tag,attrs in markup.nodes)
        assert ('readonly' in field)==(completed or role=='finance')


FORM_PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let callbacks={},sent=[],pending=[],messages=[],issues=[],timers=[],focused=0,refresh=[{id:1,name:'仓库A'},{id:2,name:'仓库B'}];
class Field {constructor(attrs={}){this.value=attrs.value||'';this.disabled='disabled' in attrs;this.readOnly='readonly' in attrs;this.handlers={};this.style={};this.textContent='';}addEventListener(type,handler){this.handlers[type]=handler;}dispatchEvent(event){if(this.handlers[event.type])this.handlers[event.type].call(this,event);}focus(){focused++;}set innerHTML(html){const options=[...html.matchAll(/<option value="([^"]*)"([^>]*)>/g)];this.value=(options.find(x=>x[2].includes('selected'))||options[0]||['',''])[1];}}
const fields=Object.fromEntries(Object.entries(p.fields).map(([name,attrs])=>[name,new Field(attrs)]));
const rowValues={'.material-code':'M1','.unit-id':'1','.line-qty':'2','.line-price':'0','.line-usage':'用途','.line-remark':'备注','.row-num':''};
const rows=Array.from({length:30},(_,index)=>{const nodes=Object.fromEntries(Object.entries(rowValues).map(([key,value])=>[key,new Field({value:index?'':value})]));return {querySelector:s=>nodes[s]||null};});
const total={textContent:''},button={disabled:false};
const document={querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:fields[(s.match(/name="([^"]+)"/)||[])[1]]||null,
 querySelectorAll:s=>s==='#docTableBody tr'?rows:s==='.doc-header button, #forceCompleteBtn'?[button]:[],
 getElementById:id=>id==='docTableBody'?{rows}:id==='totalQty'?total:null,addEventListener:(type,fn)=>callbacks[type]=fn};
const ctx={document,FormData:class{},URLSearchParams,Event:class{constructor(type){this.type=type;}},showToast:(m,t)=>messages.push({m,t}),registerDetailRowActions(){},setTimeout:(fn,delay)=>timers.push({fn,delay}),location:{href:'/original'},fetch:(url,options)=>{if(url==='/warehouse/api/list')return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({warehouses:refresh})});sent.push({url,options,body:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;
ctx.showDocumentCompletionIssue=(url,result)=>issues.push({url,result});
vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.select_helper,ctx);vm.runInContext(p.script,ctx);callbacks.DOMContentLoaded();
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const finish=async(index,status='success')=>{pending[index].resolve({ok:true,status:200,json:()=>Promise.resolve({status,id:7,msg:'fixture'})});await settle();};
const submit=()=>vm.runInContext('submitForm(true)',ctx);
(async()=>{
 assert.equal(fields.location.value,p.location,'initial warehouse binding must preserve the rendered location');
 if(p.action==='warehouse'){
  fields.warehouse_id.dispatchEvent(new ctx.Event('change'));assert.equal(fields.location.value,p.location,'same warehouse must preserve location');
  fields.warehouse_id.value='2';fields.warehouse_id.dispatchEvent(new ctx.Event('change'));assert.equal(fields.location.value,'');
  fields.location.value='B区';fields.warehouse_id.dispatchEvent(new ctx.Event('change'));assert.equal(fields.location.value,'B区');
 }else if(p.action==='refresh'){
  ctx.refreshWarehouses();await settle();assert.equal(fields.location.value,p.location);assert.equal(fields.warehouse_id.value,'1');
  refresh=[{id:2,name:'仓库B'}];ctx.refreshWarehouses();await settle();assert.equal(fields.warehouse_id.value,'');assert.equal(fields.location.value,'');
 }else if(p.action==='readonly'){
  fields.warehouse_id.value='2';fields.warehouse_id.dispatchEvent(new ctx.Event('change'));assert.equal(fields.location.value,p.location);submit();assert.equal(sent.length,0);
 }else if(p.action==='missing'){
  fields.location.value='  ';submit();await settle();assert.equal(sent.length,0);assert.equal(button.disabled,false);assert.equal(focused,1);assert(messages.some(x=>x.m.includes('库位')));
  fields.location.value=p.location;submit();assert.equal(sent.length,1);await finish(0);await finish(1);
 }else {
  submit();assert.equal(sent.length,1);assert.equal(sent[0].body.header.location,p.location);assert.equal(sent[0].body.header.warehouse_id,'1');assert.equal(sent[0].body.items[0].price,0);assert.equal(sent[0].options.headers['X-CSRFToken'],'fixture-token');assert.equal(sent[0].options.headers['Content-Type'],'application/json');assert.equal(button.disabled,true);
  if(p.action==='save-error'){await finish(0,'error');assert.equal(sent.length,1);assert.equal(timers.length,0);assert.equal(ctx.location.href,'/original');assert.equal(button.disabled,false);}
  else {await finish(0);assert.equal(sent.length,2);assert.deepEqual(sent[1].body,{force:false});await finish(1,p.action==='complete-error'?'error':'success');if(p.action==='complete-error'){assert(!messages.some(x=>x.t==='success'));assert.equal(timers.length,0);assert.equal(issues.length,1);assert.equal(issues[0].url,'/requisition/7');assert.equal(issues[0].result.msg,'fixture');assert.equal(button.disabled,true);submit();assert.equal(sent.length,2);}else{const timer=timers[0];assert(timer);timer.fn();}}
 }
 process.stdout.write(JSON.stringify({href:ctx.location.href,sent:sent.map(x=>x.body),messages,issues}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def node(program,payload):
    binary=shutil.which('node')
    assert binary,'Node.js required for real frontend callbacks'
    result=subprocess.run([binary,'--max-old-space-size=64','-e',program],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    return json.loads(result.stdout)


def escape_helper():
    source=(ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    start=source.index('function escapeHtml(')
    opening=source.index('{',start)
    depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if depth==0:
            return source[start:end+1]
    raise AssertionError('Unclosed production helper')


def form_run(action,enabled=True,completed=False,location=LOCATION,role='production'):
    html=form(enabled,completed,role,location)
    script=re.search(r'<script>(.*?)</script>',html,re.S)
    assert script
    return node(FORM_PROGRAM,dict(action=action,location=location,fields=Markup(html).fields,script=script.group(1),helper=escape_helper(),select_helper=(ROOT/'app/static/js/select-refresh.js').read_text(encoding='utf-8'),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8')))


@pytest.mark.parametrize('enabled',[False,True])
@pytest.mark.parametrize('location',[LOCATION,'  保留原始空格  '])
def test_actual_save_complete_payload_and_continue_url_keep_location(enabled,location):
    actual=form_run('flow',enabled,location=location)
    parsed=urlparse(actual['href'])
    assert parsed.path=='/requisition/add'
    query=parse_qs(parsed.query)
    assert query['location']==[location]
    assert query['warehouse_id']==['1']
    assert query['picker']==['李四']


def test_disabled_management_empty_location_still_saves_without_new_requirement():
    actual=form_run('flow',False,location='')
    assert actual['sent'][0]['header']['location']==''
    assert 'location' not in parse_qs(urlparse(actual['href']).query)


def test_enabled_management_missing_location_stops_before_any_save_and_allows_manual_retry():
    form_run('missing')


@pytest.mark.parametrize('enabled',[False,True])
@pytest.mark.parametrize('action',['warehouse','refresh'])
def test_warehouse_real_changes_clear_location_without_initialization_or_same_warehouse_loss(enabled,action):
    form_run(action,enabled)


@pytest.mark.parametrize('completed,role',[(True,'production'),(False,'finance')])
def test_view_only_location_never_clears_or_submits_when_warehouse_event_is_dispatched(completed,role):
    form_run('readonly',completed=completed,role=role)


def test_save_error_never_completes_or_navigates():
    form_run('save-error')


def test_complete_error_keeps_saved_draft_reachable_without_losing_feedback():
    actual=form_run('complete-error')
    assert actual['href']=='/original'
    assert actual['issues'][0]['url']=='/requisition/7'


def list_html():
    req=SimpleNamespace(id=7,req_no='REQ7',date=date(2026,10,23),warehouse='仓库A',location=LOCATION,bom_id=None,bom=None,
        production_order='工单1',picker='李四',purpose='用途',remark='',status='pending',operator=None,total_quantity=1)
    pagination=SimpleNamespace(total=1,pages=1,page=1,has_prev=False,has_next=False,prev_num=0,next_num=2,iter_pages=lambda **kw:[1])
    return environment().get_template('requisition.html').render(current_user=SimpleNamespace(role='production'),requisitions=[req],pagination=pagination,
        filters={'status':'','search':'','date_start':'','date_end':''},request=SimpleNamespace(args={}),sort_by='id',sort_order='desc',per_page=20,
        warehouses=[],default_warehouse=None,location_management_enabled=True,boms=[],config={},csrf_token=lambda:'fixture')


LIST_PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));let sent=[],pending=[],timers=[];
const button={dataset:p.dataset,addEventListener:(name,callback)=>{assert.equal(name,'click');button.callback=callback;}};
const ctx={URLSearchParams,FormData:class{},document:{querySelector:s=>({content:'fixture-token'}),querySelectorAll:s=>s==='.complete-btn'?[button]:[]},location:{href:'/original'},showToast(){},showConfirm:()=>Promise.resolve(p.scenario!=='cancel'),setTimeout:(fn,delay)=>timers.push({fn,delay}),fetch:(url,options)=>{sent.push({url,options});return new Promise(resolve=>pending.push(resolve));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
(async()=>{button.callback.call(button);await new Promise(r=>setImmediate(r));if(p.scenario==='cancel'){assert.equal(sent.length,0);}else{assert.equal(sent.length,1);assert.equal(sent[0].url,'/requisition/7/complete');assert.equal(sent[0].options.headers['X-CSRFToken'],'fixture-token');pending[0]({ok:p.scenario!=='http',status:p.scenario==='http'?400:200,json:()=>Promise.resolve({status:p.scenario==='business'?'error':'success'})});for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));if(p.scenario==='success'){assert.equal(timers.length,1);timers[0].fn();}else assert.equal(timers.length,0);}process.stdout.write(JSON.stringify({href:ctx.location.href}));})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


@pytest.mark.parametrize('scenario',['success','cancel','business','http'])
def test_real_list_button_carries_location_and_only_success_continues(scenario):
    html=list_html()
    attrs=next(attrs for tag,attrs in Markup(html).nodes if tag=='button' and 'complete-btn' in attrs.get('class','').split())
    assert attrs.get('data-location')==LOCATION
    dataset={re.sub(r'-([a-z])',lambda match:match.group(1).upper(),key[5:]):value for key,value in attrs.items() if key.startswith('data-')}
    source=(ROOT/'app/templates/requisition.html').read_text(encoding='utf-8')
    helper=source[source.index('function buildRequisitionContinueUrl(button) {'):source.index("document.querySelectorAll('.complete-btn')")]
    handler=source[source.index("document.querySelectorAll('.complete-btn')"):source.index("document.querySelectorAll('.revert-btn')")]
    script="const requisitionUrls={add:'/requisition/add',complete:'/requisition/0/complete'};function urlWithId(url,id){return url.replace('/0','/'+id);}\n"+helper+handler
    actual=node(LIST_PROGRAM,dict(dataset=dataset,scenario=scenario,script=script,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8')))
    if scenario=='success':
        parsed=urlparse(actual['href'])
        assert parsed.path=='/requisition/add'
        assert parse_qs(parsed.query)['location']==[LOCATION]
        assert parse_qs(parsed.query)['warehouse']==['仓库A']
        assert parse_qs(parsed.query)['picker']==['李四']
        assert parse_qs(parsed.query)['production_order']==['工单1']
    else:
        assert actual['href']=='/original'
