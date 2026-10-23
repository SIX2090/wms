"""Real material-label editor DOM, request state and production HTTP client."""
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


class Nodes(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],messages=[],prompts=[],store=new Map();let focused=0;
class El {
 constructor(tag,attrs={}){this.tagName=tag.toUpperCase();this.attrs={...attrs};this.dataset=new Proxy({}, {set:(target,key,value)=>{target[key]=String(value);return true;}});this.children=[];this.events={};this.style={fontSize:'',fontWeight:'',color:'',textAlign:'',verticalAlign:''};this._text='';this._html='';this._value=attrs.value??null;this.className=attrs.class||'';this.colSpan=1;this.disabled=false;this.classList={contains:c=>this.className.split(' ').includes(c),add:c=>{if(!this.className.split(' ').includes(c))this.className+=' '+c;},remove:c=>this.className=this.className.split(' ').filter(x=>x!==c).join(' ')};for(const[k,v]of Object.entries(attrs))if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,x)=>x.toUpperCase())]=v;}
 get value(){if(this._value!==null)return this._value;if(this.tagName==='SELECT'){const option=this.children.find(n=>n.selected)||this.children[0];return option?option.value:'';}return '';}
 set value(v){this._value=String(v);}
 set selectedIndex(i){this._value=this.children[i]?.value||'';}
 get rows(){return this.children.filter(n=>n.tagName==='TR');}get cells(){return this.children.filter(n=>n.tagName==='TD');}
 appendChild(n){n.parentNode=this;n.parentElement=this;this.children.push(n);return n;}
 insertRow(){return this.appendChild(new El('tr'));}insertCell(){return this.appendChild(new El('td'));}
 set innerHTML(html){this.children=[];this._html=String(html);this._text='';if(this.tagName==='SELECT')this._value=null;const match=this._html.match(/<span([^>]*)>([\s\S]*?)<\/span>/);if(match){const attrs={};for(const item of match[1].matchAll(/([\w-]+)="([^"]*)"/g))attrs[item[1]]=item[2];const content=new El('span',attrs);content._html=match[2];for(const prop of (attrs.style||'').split(';')){const[k,v]=prop.split(':');if(k&&v)content.style[k.trim().replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v.trim();}this.appendChild(content);this._html='';}}
 get innerHTML(){return this._html+this.children.map(n=>n.innerHTML||n.textContent).join('');}
 set textContent(v){this._text=String(v??'');this._html='';this.children=[];}get textContent(){return this._text+this._html.replace(/<[^>]*>/g,'')+this.children.map(n=>n.textContent).join('');}
 querySelectorAll(selector){const selectors=selector.split(',').map(s=>s.trim().split(' ').at(-1));const matches=n=>selectors.some(name=>name.startsWith('.')?n.classList.contains(name.slice(1)):name.startsWith('[')?n.hasAttribute(name.slice(1,-1)):n.tagName.toLowerCase()===name);return this.children.flatMap(n=>[...(matches(n)?[n]:[]),...n.querySelectorAll(selector)]);}
 querySelector(s){return this.querySelectorAll(s)[0]||null;}closest(){return null;}contains(n){return this===n||this.children.some(c=>c.contains(n));}
 addEventListener(k,fn){(this.events[k]??=[]).push(fn);}removeEventListener(k,fn){this.events[k]=(this.events[k]||[]).filter(f=>f!==fn);}focus(){if(!this.disabled)focused++;}
 setAttribute(k,v){this.attrs[k]=String(v);if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v);}
 hasAttribute(k){return Object.prototype.hasOwnProperty.call(this.attrs,k);}removeAttribute(k){delete this.attrs[k];}getAttribute(k){return this.attrs[k]??null;}
}
const nodes=p.nodes.map(([tag,a])=>new El(tag,a)),ids=Object.fromEntries(nodes.filter(n=>n.attrs.id).map(n=>[n.attrs.id,n]));
ids.labelTemplateModal.children=nodes.filter(n=>n!==ids.labelTemplateModal);
const document={activeElement:null,getElementById:id=>ids[id]||null,createElement:tag=>new El(tag),querySelectorAll:s=>s.includes('.label-cell')?ids.labelTable.querySelectorAll(s):[],querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null,addEventListener(){}};
const ctx={document,Headers,FormData,console:{warn(){}},localStorage:{getItem:k=>store.get(k)||null,setItem:(k,v)=>store.set(k,v),removeItem:k=>store.delete(k)},showToast:(message,type)=>messages.push({message,type}),alert:()=>assert.fail('production toast exists'),confirm:message=>{prompts.push(message);return p.scenario!=='cancel';},setTimeout(){},bootstrap:{Modal:class{show(){}}},fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({url,resolve,reject}));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const list='/label_template/api/list',detail=id=>'/label_template/api/'+id+'/detail';
function tmpl(id,missingStyle=false,literal=false){const width=id==='A'?40:id==='B'?90:60;return{id,name:'template-'+id,width,height:id==='B'?50:20,rows:1,cols:1,layout:{rows:1,cols:1,labelWidth:width,labelHeight:id==='B'?50:20,rowHeights:[45],cells:[{row:0,col:0,text:literal?'<img src=x onerror=fixture()>literal-'+id:'canvas-'+id,field:'name',colSpan:1,...(missingStyle?{}:{style:{fontSize:'15px',fontWeight:'bold',verticalAlign:'middle'}})}]}};}
const entries=[{id:'A',name:'template-A',width:40,height:20,is_default:true},{id:'B',name:'template-B',width:90,height:50},{id:'N',name:'new fixture',width:60,height:20}];
function response(body,s){const status=s==='http_success'?500:s==='http'?400:s==='html'?502:200;return{ok:status===200,status,json:()=>['html','html200'].includes(s)?Promise.reject(Error('fixture HTML')):Promise.resolve(s==='null'?null:s==='business'?{status:'error',msg:'fixture refusal'}:body)};}
async function finish(url,body,s='success'){const r=pending.find(n=>n.url===url&&!n.done);assert(r,'pending '+url);r.done=true;if(s==='network')r.reject(Error('fixture offline'));else r.resolve(response(body,s));await settle();}
const postCalls=()=>calls.filter(c=>c.options.method==='POST');
function select(id){ids.templateSelect.value=id;vm.runInContext(ids.templateSelect.attrs.onchange||'switchTemplate()',ctx);}
function click(name){const button=nodes.find(n=>n.attrs.onclick===name+'()');assert(button,'real '+name+' button');vm.runInContext(button.attrs.onclick,ctx);}
function rendered(id,text='canvas-'+id){assert.equal(ctx.currentTemplateId,id,'loaded identity follows current choice');assert.equal(ids.templateNameInput.value,'template-'+id);assert.equal(ids.labelTable.textContent,text,'actual editor table follows current choice');assert.equal(ids.labelCanvas.style.width,(id==='A'?160:id==='B'?360:240)+'px');assert.equal(ids.labelTable.rows[0].style.height,'45px');const content=ids.labelTable.querySelector('.cell-content');assert.equal(content.dataset.field,'name');}
async function ready(id='A'){ctx.loadTemplateList();await finish(list,{status:'success',templates:entries});if(id!=='A')select(id);await finish(detail(id),{status:'success',template:tmpl(id)});}
function state(){return JSON.stringify({id:ctx.currentTemplateId,name:ids.templateNameInput.value,text:ids.labelTable.textContent,width:ids.labelCanvas.style.width});}
function checkFailure(){assert(messages.some(m=>['danger','error','warning'].includes(m.type)));assert(!messages.some(m=>m.type==='success'));assert(!messages.some(m=>m.message.includes('Cannot read')));}
async function refreshSelection(target){await finish(list,{status:'success',templates:p.action==='delete'?entries.filter(t=>t.id!=='A'):entries});assert(calls.some(c=>c.url===detail(target)),'post-write refresh reloads retained target');await finish(detail(target),{status:'success',template:tmpl(target)});rendered(target);}
(async()=>{
 if(p.action==='race'){
  if(p.scenario==='list'){ctx.loadTemplateList();ctx.loadTemplateList();const old=pending[0];old.done=true;pending[1].done=true;pending[1].resolve(response({status:'success',templates:[entries[1]]}));await settle();await finish(detail('B'),{status:'success',template:tmpl('B')});old.resolve(response({status:'success',templates:[entries[0]]}));await settle();rendered('B');assert(!calls.some(c=>c.url===detail('A')),'late list cannot begin an obsolete detail load');return;}
  ctx.switchTemplateById('A');ctx.switchTemplateById('B');await finish(detail('B'),{status:'success',template:tmpl('B')});await finish(detail('A'),{status:'success',template:tmpl('A')},p.scenario==='old_error'?'network':'success');rendered('B');return;
 }
 if(p.action==='render'){ctx.switchTemplateById('A');await finish(detail('A'),{status:'success',template:tmpl('A',p.scenario==='missing_style',p.scenario==='literal')});rendered('A',p.scenario==='literal'?'<img src=x onerror=fixture()>literal-A':'canvas-A');assert.equal(ids.labelTable.querySelector('.cell-content').style.fontSize,p.scenario==='missing_style'?'12px':'15px');return;}
 if(p.action==='load_failure'){ctx.loadTemplateList();if(p.scenario==='list_null'){await finish(list,{},'null');}else{await finish(list,{status:'success',templates:entries});await finish(detail('A'),{status:'success',template:tmpl('A')},p.scenario);}checkFailure();assert.equal(ctx.currentTemplateId,null);return;}
 await ready();rendered('A');
 if(p.action==='empty'){select('');assert.equal(ctx.currentTemplateId,null,'empty selection starts a new design');assert.equal(ids.templateNameInput.value,'');assert.equal(ids.labelTable.textContent,'canvas-A');return;}
 if(p.action==='load_save'){select('B');click('saveTemplate');await settle();assert.equal(postCalls().length,0,'loading B must not save the previously loaded A');assert.equal(ctx.currentTemplateId,null);await finish(detail('B'),{status:'success',template:tmpl('B')});rendered('B');return;}
 if(p.action==='invalidate'){
  const snap=ctx.__captureSnapshot();snap.cells[0].text='local-'+p.scenario;select('B');
  if(p.scenario==='clear')click('clearTemplate');else if(p.scenario==='close'){for(const handler of ids.labelTemplateModal.events['hide.bs.modal']||[])handler({preventDefault:()=>assert.fail('idle modal close must remain allowed')});}else if(p.scenario==='draft'){store.set('labelTemplateDraft',JSON.stringify(snap));ctx.restoreTemplateDraft();}else{ctx[p.scenario==='undo'?'__undoStack':'__redoStack']=[snap];ctx.__lastSnap=snap;click(p.scenario==='undo'?'undoTemplate':'redoTemplate');}
  const before=state();await finish(detail('B'),{status:'success',template:tmpl('B')});assert.equal(state(),before,'late detail cannot overwrite local clear/draft/history');return;
 }
 if(p.action==='geometry'){const template={id:'G',name:'geometry',width:90,height:50,rows:2,cols:3,layout:p.scenario==='layout'?{width:40,height:20,rows:1,cols:1,cells:[]}:{cells:[]}};ctx.loadTemplateToEditor(template);assert.equal(ids.labelCanvas.style.width,p.scenario==='layout'?'160px':'360px');assert.equal(ids.labelCanvas.style.height,p.scenario==='layout'?'80px':'200px');assert.equal(ids.labelTable.rows.length,p.scenario==='layout'?1:2);assert(ids.labelTable.rows.every(row=>row.cells.length===(p.scenario==='layout'?1:3)));return;}
 if(p.action==='empty_name'){ids.templateNameInput.value='   ';click('saveAsTemplate');await settle();assert.equal(postCalls().length,0);assert.equal(focused,1,'empty name is focused while enabled');assert(!ids.templateNameInput.disabled);return;}
 const name={save:'saveTemplate',add:'saveAsTemplate',default:'setDefaultTemplate',delete:'deleteTemplate',delete_last:'deleteTemplate'}[p.action];assert(name);
 if(p.action==='delete_last'){const draft=ctx.__captureSnapshot();draft.cells[0].text='retained draft';store.set('labelTemplateDraft',JSON.stringify(draft));}
 if(p.action==='add')ids.templateNameInput.value='  new fixture  ';
 click(name);await settle();
 if(p.scenario==='cancel'){assert.equal(postCalls().length,0);assert.equal(prompts.length,1);return;}
 assert.equal(postCalls().length,1);const req=postCalls()[0],endpoint={save:'/label_template/A/save_layout',add:'/label_template/add',default:'/label_template/A/set_default',delete:'/label_template/A/delete',delete_last:'/label_template/A/delete'}[p.action];assert.equal(req.url,endpoint);
 assert.equal(new Headers(req.options.headers).get('X-CSRFToken'),'fixture-token');assert.equal(req.options.headers['X-Requested-With'],'XMLHttpRequest');
 if(p.action==='save'){const body=JSON.parse(req.options.body);assert.equal(body.width,40);assert.equal(body.height,20);assert.equal(body.layout.cells[0].text,'canvas-A');assert.equal(body.layout.cells[0].field,'name');assert.equal(body.layout.cells[0].row,'0');}
 if(p.action==='add'){assert(req.options.body instanceof FormData);assert.equal(req.options.body.get('name'),'new fixture');assert.equal(JSON.parse(req.options.body.get('layout')).cells[0].text,'canvas-A');}
 const before=state();click(name);select('B');click('clearTemplate');ctx.restoreTemplateDraft();click('undoTemplate');click('redoTemplate');await settle();assert.equal(postCalls().length,1,'one in-flight write across editor actions');assert.equal(state(),before,'in-flight writes must keep captured identity and canvas');let prevented=false;for(const handler of ids.labelTemplateModal.events['hide.bs.modal']||[])handler({preventDefault:()=>prevented=true});assert(prevented,'closing modal cannot bypass an in-flight write');
 await finish(endpoint,{status:'success'},p.scenario);
 if(p.scenario==='success'){
  if(p.action==='delete_last'){await finish(list,{status:'success',templates:[]});assert.equal(ctx.currentTemplateId,null);assert.equal(ids.labelTable.textContent,'retained draft','last-template removal restores the real local draft after successful refresh');return;}
  const count=postCalls().length;click(name);await settle();assert.equal(postCalls().length,count,'write remains locked throughout list refresh');const target=p.action==='add'?'N':p.action==='delete'?'B':'A';await refreshSelection(target);
 }else{checkFailure();click(name);await settle();assert.equal(postCalls().length,2,'failed write permits manual retry only');await finish(endpoint,{status:'error',msg:'fixture refusal'},'business');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(action,scenario='success',source_override=None):
    template=(ROOT/'app/templates/material.html').read_text(encoding='utf-8')
    start=template.index('// 标签打印模板相关函数')
    end=template.index('// ==================== 所见即所得预览',start)
    source=source_override if source_override is not None else template[start:end]
    nodes=Nodes(template[template.index('<div class="modal fade" id="labelTemplateModal"'):template.index('<script>',template.index('<div class="modal fade" id="labelTemplateModal"'))]).nodes
    node=shutil.which('node');assert node,'Node required for real label editor'
    payload=dict(action=action,scenario=scenario,nodes=nodes,source=source,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('scenario',['old_success','old_error','list'])
def test_late_list_and_detail_never_overwrite_current_identity_name_and_real_canvas(scenario):
    run('race',scenario)


def test_saving_while_new_template_loads_never_updates_old_template():
    run('load_save')


def test_empty_select_keeps_canvas_but_clears_persisted_identity():
    run('empty')


@pytest.mark.parametrize('scenario',['clear','draft','undo','redo','close'])
def test_local_editor_actions_invalidate_pending_template_loads(scenario):
    run('invalidate',scenario)


@pytest.mark.parametrize('action',['save','add','default','delete'])
def test_write_payload_mutex_and_success_refresh_keep_the_correct_target(action):
    run(action)


@pytest.mark.parametrize('action,scenario',[('save','http_success'),('add','null'),('default','network'),('delete','business')])
def test_failed_writes_are_visible_and_allow_only_manual_retry(action,scenario):
    run(action,scenario)


def test_delete_cancel_never_sends_a_request():
    run('delete','cancel')


@pytest.mark.parametrize('scenario',['list_null','html','network'])
def test_loading_failures_are_visible_and_never_leave_stale_identity(scenario):
    run('load_failure',scenario)


@pytest.mark.parametrize('scenario',['missing_style','literal'])
def test_real_table_loading_handles_missing_style_and_literal_text(scenario):
    run('render',scenario)


@pytest.mark.parametrize('scenario',['top','layout'])
def test_empty_cell_layout_keeps_root_geometry_and_explicit_layout_precedence(scenario):
    run('geometry',scenario)


def test_last_template_deletion_restores_local_draft_after_refresh():
    run('delete_last')


def test_empty_new_name_is_focused_without_a_request_or_busy_lock():
    run('empty_name')
