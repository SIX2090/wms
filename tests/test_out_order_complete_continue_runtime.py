"""Ordinary requisition: real submit/API and the production toolbar proxy."""
from datetime import date
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from jinja2 import DictLoader, Environment

ROOT=Path(__file__).resolve().parents[1]


class Nodes(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


def function(source,name):
    start=source.index('function '+name+'(');opening=source.index('{',start);depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if not depth:return source[start:end+1]
    raise AssertionError(name)


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],messages=[];let bar;
const fields=Object.fromEntries(Object.entries({date:'2026-10-20',department_id:'3',picker:'fixture picker',warehouse_id:'2',business_type:p.kind==='normal'?'领料单':p.kind==='sale'?'销售出库':p.kind==='other'?'其他出库':'采购退货出库',order_id:'',order_no:'OUT-OLD-FIXTURE',remark:'old remarks',customer:'fixture customer'}).map(([name,value])=>[name,{value,focus(){}}]));
const row={querySelector:s=>{const data={'.material-code':'M-OLD','.material-qty':'2.5','.material-price':'0','.line-contract-no':'old contract','.line-project-name':'old project','.material-remark':'old line'};return s in data?{value:data[s],style:{}}:null;}};
function node(tag,attrs={}){return{tag,attrs,disabled:false,children:[],getAttribute:k=>attrs[k]??null,setAttribute(k,v){attrs[k]=v;},classList:{add(){},contains(){return false;}},appendChild(child){this.children.push(child);},addEventListener(type,fn){this[type]=fn;},click(){if(this.clickHandler)this.clickHandler();}};}
const buttons=p.buttons.map(attrs=>node('button',attrs));const primary=buttons.find(n=>n.attrs['data-wms-save-complete']);
const content={insertBefore:n=>bar=n};
const document={body:{classList:{contains:c=>c==='embedded-page'&&p.embedded,add(){}}},querySelector:s=>{if(s==='meta[name="csrf-token"]')return {content:'fixture-token'};const name=(s.match(/name="([^"]+)"/)||[])[1];if(name)return fields[name]||null;if(s==='meta[name="csrf-token"]')return {content:'fixture-token'};if(s==='button[data-wms-save-complete]')return primary||null;if(s==='.embedded-content')return content;if(s==='#addForm, #docForm')return{};return null;},querySelectorAll:s=>s==='#materialTableBody tr'?[row]:buttons.concat(bar?bar.children:[]),getElementById:()=>null,createElement:tag=>{const n=node(tag);n.addEventListener=(type,fn)=>{if(type==='click')n.clickHandler=fn;};return n;}};
const ctx={document,Headers,FormData,URL,URLSearchParams,location:{origin:'http://fixture',pathname:'/out_order/add',search:p.embedded?'?embedded=1':'',href:'http://fixture/out_order/add'+(p.embedded?'?embedded=1':'')},showToast:(message,type)=>messages.push({message,type}),confirm:()=>true,fetch:(url,options)=>{calls.push({url,options,body:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},isWmsEmbeddedPage:()=>p.embedded,isWmsListPage:()=>false,pageHasOwnButton:()=>false,trimWmsActionbarDividers:rows=>rows,createDocumentNavigationGroup:()=>null,saveCurrentPage:()=>assert.fail('toolbar must proxy actual primary submit')};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);
vm.runInContext('const isSaleOrder='+JSON.stringify(p.kind==='sale')+',isOtherOut='+JSON.stringify(p.kind==='other')+',isPurchaseReturn='+JSON.stringify(p.kind==='return')+',purchaseReturnRequiresOrder=false,returnAddUrl="/out_order/add";let outOrderSubmitting=false;',ctx);
vm.runInContext(p.helpers,ctx);vm.runInContext(p.submit,ctx);
for(const button of buttons)button.clickHandler=()=>vm.runInContext(button.attrs.onclick,ctx);
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
function response(stage){const outcome=p.scenario;const status=outcome==='complete_http'&&stage==='complete'?500:200;const body=stage==='save'?{status:outcome==='save_error'?'error':'success',id:7,order_no:'OUT-7',msg:'fixture refusal'}:{status:outcome==='complete_error'?'error':outcome==='warning'?'warning':'success',msg:'fixture refusal'};return{ok:status===200,status,json:()=>Promise.resolve(body)};}
(async()=>{
 let click;
 if(p.embedded){ctx.insertGlobalActionBar();const proxy=bar.children.find(n=>n.attrs['data-wms-save-complete-proxy']==='1');assert(proxy,'production toolbar has a primary proxy');assert.equal(proxy.title,'保存完成并新增领料单');click=()=>proxy.click();}
 else if(p.kind==='normal'){assert(primary);click=()=>primary.click();}
 else if(p.kind==='other')click=()=>ctx.submitForm(false,false);
 else click=()=>buttons.find(n=>n.attrs.onclick==='submitForm()').click();
 const original=ctx.location.href;click();await settle();click();assert.equal(calls.length,1,'double click does not duplicate the save');assert.equal(calls[0].url,'/out_order/add');assert.equal(calls[0].body.items[0].quantity,2.5);assert.equal(calls[0].body.items[0].price,0);assert.equal(calls[0].body.date,'2026-10-20');assert.equal(calls[0].body.order_no,'OUT-OLD-FIXTURE');assert.equal(calls[0].options.headers['X-CSRFToken'],'fixture-token');
 pending[0].resolve(response('save'));await settle();
 if(p.scenario==='save_error'){assert.equal(calls.length,1);assert.equal(ctx.location.href,original);assert(!buttons.some(n=>n.disabled));return;}
 if(p.kind!=='normal'){assert.equal(calls.length,1);assert.equal(new URL(ctx.location.href,ctx.location.origin).pathname,'/out_order/7');return;}
 assert.equal(calls.length,2);assert.equal(calls[1].url,'/out_order/7/complete');assert.deepEqual(calls[1].body,{});click();assert.equal(calls.length,2,'complete in flight does not resave');
 if(p.scenario==='complete_network')pending[1].reject(Error('fixture offline'));else pending[1].resolve(response('complete'));await settle();
 const result=new URL(ctx.location.href,ctx.location.origin);
 if(p.scenario==='success'){assert.equal(result.pathname,'/out_order/add','completed ordinary requisition must open a fresh entry page');assert.equal(result.search,p.embedded?'?embedded=1':'');assert.equal(result.searchParams.get('order_id'),null);assert.equal(result.searchParams.get('date'),null);assert.equal(result.searchParams.get('items'),null);assert(messages.some(m=>m.type==='success'));}
 else{assert.equal(result.pathname,'/out_order/7','uncertain/failed completion remains on the saved detail');assert(!calls.some(c=>c.url.includes('force')));assert(messages.some(m=>m.type==='warning'));}
 click();await settle();assert.equal(calls.length,2,'navigation phase stays locked');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(scenario='success',embedded=False,kind='normal',submit_override=None):
    source=(ROOT/'app/templates/out_order_add.html').read_text(encoding='utf-8')
    header=source.split('{% block content %}',1)[1].split('<div class="card">',1)[0]
    env=Environment(loader=DictLoader({'header':header,'_other_order_toolbar.html':''}),autoescape=True)
    html=env.get_template('header').render(is_other_out=kind=='other',is_sale_order=kind=='sale',is_purchase_return=kind=='return')
    buttons=[attrs for tag,attrs in Nodes(html).nodes if tag=='button' and attrs.get('onclick','').startswith('submitForm(')]
    shared=(ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    config=shared[shared.index('const WMS_ACTION_MODULES = {'):shared.index('\n};',shared.index('const WMS_ACTION_MODULES = {'))+3]
    helpers=config+'\n'+'\n'.join(function(shared,name) for name in ['getWmsActionModule','isFormPage','withEmbeddedParam','preserveEmbeddedUrl','escapeHtml','insertGlobalActionBar'])
    payload=dict(scenario=scenario,embedded=embedded,kind=kind,buttons=buttons,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),helpers=helpers,submit=submit_override or function(source,'submitForm'))
    node=shutil.which('node');assert node,'Node required for actual requisition submit'
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('embedded',[False,True])
def test_completed_ordinary_requisition_opens_clean_entry_via_primary_or_toolbar(embedded):
    run(embedded=embedded)


@pytest.mark.parametrize('scenario',['complete_error','warning','complete_http','complete_network','save_error'])
def test_failed_or_uncertain_completion_never_opens_new_entry_or_forces_stock(scenario):
    run(scenario)


@pytest.mark.parametrize('kind',['sale','other','return'])
def test_other_outbound_entry_modes_keep_existing_save_to_detail_behavior(kind):
    run(kind=kind)


def test_fresh_get_has_today_new_number_no_old_id_or_details(monkeypatch):
    import app as wms
    monkeypatch.setitem(wms.app.config,'TESTING',True)
    monkeypatch.setitem(wms.app.config,'WTF_CSRF_ENABLED',False)
    with wms.app.app_context():
        assert str(wms.db.engine.url)=='sqlite:///:memory:'
        wms.db.session.remove();wms.db.drop_all();wms.db.create_all()
        try:
            user=wms.User(username='continue-fixture',password_hash='fixture-not-a-real-credential',role='admin',must_change_password=False)
            old=wms.OutOrder(order_no='OUT-OLD-FIXTURE',date=date(2025,1,2),business_type='领料单',status='completed')
            material=wms.Material(code='M-OLD',name='Old fixture material')
            wms.db.session.add_all([user,old,material]);wms.db.session.flush()
            wms.db.session.add(wms.OutOrderItem(out_order_id=old.id,material_id=material.id,quantity=2.5,price=0,amount=0))
            wms.db.session.commit()
            client=wms.app.test_client()
            with client.session_transaction() as session:
                session['_user_id']=str(user.id);session['_fresh']=True
            response=client.get('/out_order/add')
            assert response.status_code==200
            html=response.get_data(as_text=True)
            fields={attrs.get('name'):attrs for tag,attrs in Nodes(html).nodes if tag=='input' and attrs.get('name')}
            assert fields['order_id']['value']==''
            assert fields['date']['value']==date.today().isoformat()
            assert fields['order_no']['value'] and fields['order_no']['value']!='OUT-OLD-FIXTURE'
            assert re.search(r'const editItems =\s*\[\]\s*;',html)
            assert wms.OutOrder.query.count()==1
        finally:
            wms.db.session.remove();wms.db.drop_all()
