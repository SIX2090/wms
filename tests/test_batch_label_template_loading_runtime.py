"""Real batch-label rendering under asynchronous template switches; no printing or HTTP."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace as NS

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]


class Nodes(HTMLParser):
    def __init__(self,html):
        super().__init__();self.nodes=[];self.feed(html)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],opened=[],logs=[],timers=[];let printed=0,closed=0;
class El{constructor(tag,attrs={}){this.tagName=tag.toLowerCase();this.attrs=attrs;this.children=[];this.events={};this.value=attrs.value||'';this.style={setProperty:(k,v)=>this.style[k]=v};this._text='';this._html='';this.disabled=false;}set innerHTML(v){this._html=String(v);this._text='';this.children=[];if(/<[a-z][\s\S]*>/i.test(this._html)){const child=new El('html-fragment');child._html=this._html;child.parentNode=this;this.children.push(child);this._html='';}}get innerHTML(){return this._html+this.children.map(c=>c.innerHTML||c.textContent).join('');}set textContent(v){this._text=String(v);this._html='';this.children=[];}get textContent(){return this._text+this._html.replace(/<[^>]*>/g,'')+this.children.map(c=>c.textContent).join('');}appendChild(child){this.children.push(child);child.parentNode=this;return child;}addEventListener(type,fn){(this.events[type]??=[]).push(fn);}fire(type){for(const fn of this.events[type]||[])fn.call(this,{target:this});}removeAttribute(k){delete this.attrs[k];}setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k]??null;}}
const nodes=p.nodes.map(([tag,attrs])=>new El(tag,attrs)),ids=Object.fromEntries(nodes.filter(n=>n.attrs.id).map(n=>[n.attrs.id,n]));const root=new El('html'),body=new El('body');root.appendChild(body);
const events={};const document={readyState:'loading',body,getElementById:id=>ids[id]||body.children.find(n=>n.id===id)||null,createElement:tag=>new El(tag),documentElement:root,addEventListener:(type,fn)=>(events[type]??=[]).push(fn),querySelector:()=>({content:'fixture-token'})};
const ctx={document,Headers,FormData,URLSearchParams,location:{search:p.search||'',href:'/original'},console:{error:(...args)=>logs.push(args)},confirm:()=>false,setTimeout:(fn,delay)=>timers.push({fn,delay,done:false}),close:()=>closed++,print:()=>printed++,open:(url,target)=>opened.push({url,target}),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({url,resolve,reject}));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);for(const script of p.scripts)vm.runInContext(script,ctx);
for(const fn of events.DOMContentLoaded||[])fn();
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const excel='/doc_print_templates/material_label.json',list='/label_template/api/list',detail=id=>'/label_template/api/'+id+'/detail';
function template(id,width=id==='A'?40:70){return {id,width,height:id==='A'?20:30,rows:1,cols:1,layout:{marginLeft:1,rowHeights:[60,30],cells:[{row:0,col:0,text:'template-'+id,colSpan:2,style:{fontSize:14,fontWeight:'bold',verticalAlign:'middle'}},{row:1,col:0,field:'name'},{row:1,col:1,field:'barcode',barcodeWidth:25,barcodeHeight:7}]}};}
function response(body,kind='success'){const status=kind==='http_success'?500:kind==='http'?400:kind==='html'?502:200;return {ok:status===200,status,json:()=>['html','html200'].includes(kind)?Promise.reject(Error('fixture invalid JSON')):Promise.resolve(kind==='null'?null:kind==='business'?{status:'error',msg:'fixture refusal'}:body)};}
async function finish(url,body,kind='success'){const request=pending.find(r=>r.url===url&&!r.done);assert(request,'pending '+url);request.done=true;if(kind==='network')request.reject(Error('fixture offline'));else request.resolve(response(body,kind));await settle();}
const select=id=>{ids.templateSelect.value=id;ids.templateSelect.fire('change');};
function fire(type){for(const fn of events[type]||[])fn();}function tick(delay){const timer=timers.find(t=>!t.done&&(delay===undefined||t.delay===delay));assert(timer,'pending timer '+delay);timer.done=true;timer.fn();}function drainUntilPrint(){for(let i=0;i<8&&printed===0;i++)tick();assert.equal(printed,1);}
const all=(node,tag)=>node.children.flatMap(child=>[...(child.tagName===tag?[child]:[]),...all(child,tag)]);
function rendered(id,width){const cards=ids.labelsContainer.children;assert.equal(cards.length,2);assert.equal(cards[0].style.width,width+'mm','visible label must match current template');assert(cards[0].textContent.includes('template-'+id));assert(cards[0].textContent.includes('fixture material'));assert.equal(root.style['--label-width'],width+'mm');assert(ids.sizeInfo.textContent.includes(String(width)));const trs=all(cards[0],'tr');assert.equal(trs.length,2,'actual out-of-bounds cell row remains rendered');assert.equal(trs[0].style.height,((id==='A'?20:id==='C'?50:30)*2/3).toFixed(2)+'mm');const tds=all(cards[0],'td');assert.equal(tds[0].colSpan,2);assert.equal(tds[0].style.verticalAlign,'middle');assert.equal(tds[0].style.fontSize,'14px');const image=all(cards[0],'img')[0];assert.equal(image.src,'/api/barcode/BAR%2F%26%20');assert.equal(image.style.width,'25mm');assert.equal(image.style.height,'7mm');}
function fallback(){assert.equal(root.style['--label-width'],'90mm');assert.equal(root.style['--label-height'],'50mm');assert(ids.sizeInfo.textContent.includes('90'));assert.equal(ids.labelsContainer.children.length,2);}
function feedback(id){assert(ids[id]&&ids[id].textContent.trim(),'visible feedback '+id);assert(!ids[id].textContent.includes('Cannot read'));}
(async()=>{
 await settle();assert.equal(printed,0);assert.equal(opened.length,0);
 if(p.action==='token'){assert.equal(calls.length,0,'anonymous signed print page must skip login-only template APIs');fallback();assert.equal(ids.labelsContainer.getAttribute('data-wms-print-state'),'ready');assert(ids.labelsContainer.textContent.includes('<img src=x onerror=fixture()>fixture material'));fire('load');tick(400);assert.equal(printed,1);tick(800);assert.equal(printed,2);tick(800);tick(800);assert.equal(closed,1);ctx.downloadExcelLabels();assert.equal(opened.length,0,'anonymous Excel download must require login');return;}
 if(p.action==='auto'){
  await finish(excel,{status:'success',templates:[]});await finish(list,{status:'success',templates:[{id:'A',name:'A',width:40,height:20},{id:'B',name:'B',width:70,height:30}]});
  if(p.scenario==='loading'){assert(ids.labelsContainer.children.length>0,'loading spinner is an actual child for legacy readiness');fire('load');for(let i=0;i<3;i++)tick();assert.equal(printed,0,'spinner children are not printable labels');await finish(detail('A'),{status:'success',template:template('A')});drainUntilPrint();}
  else if(p.scenario==='timeout'){fire('load');for(let i=0;i<55;i++){const timer=timers.find(t=>!t.done);if(!timer)break;tick();}assert.equal(printed,0,'loading timeout must not print spinner children');assert(document.getElementById('wmsAutoprintStatus').textContent.includes('超时'),'timeout is visible');}
  else if(p.scenario==='error'){await finish(detail('A'),{status:'error',msg:'bad'},'business');fire('load');for(let i=0;i<55;i++){const timer=timers.find(t=>!t.done);if(!timer)break;tick();}assert.equal(printed,0,'errors and polling timeout must never auto-print');}
  else if(p.scenario==='switch_delay'){await finish(detail('A'),{status:'success',template:template('A')});fire('load');select('B');tick(400);assert.equal(printed,0,'400ms delayed print must recheck current template');await finish(detail('B'),{status:'success',template:template('B')});drainUntilPrint();rendered('B',70);}
  else if(p.scenario==='legacy'){await finish(detail('A'),{status:'success',template:template('A')});ids.labelsContainer.removeAttribute('data-wms-print-state');fire('load');tick(400);assert.equal(printed,1);tick(800);assert.equal(printed,2);tick(800);assert.equal(closed,0);tick(800);assert.equal(closed,1);}
  assert.equal(opened.length,0);return;
 }
 if(p.action==='excel_failure'){await finish(excel,{status:'success',templates:[{id:'E',name:'bad'}]},p.scenario);assert(!ids.excelTemplateSelect.children.some(c=>c.value==='E'),'HTTP failure must not populate Excel templates from a success envelope');feedback('excelTemplateStatus');return;}
 await finish(excel,{status:'success',templates:[{id:'E/& 中',name:'Excel',is_default:true}]});
 if(p.action==='download'){await finish(list,{status:'success',templates:[]});ids.excelTemplateSelect.value='E/& 中';ctx.downloadExcelLabels();assert.equal(opened.length,1);const url=new URL(opened[0].url,'http://fixture');assert.equal(url.pathname,'/label/batch_print_excel');assert.equal(url.searchParams.get('ids'),'7,8','material IDs are authoritative even if query contains inbound-item IDs');assert(opened[0].url.includes('ids=7%2C8'));assert.equal(url.searchParams.get('template_id'),'E/& 中');assert.equal(opened[0].target,'_blank');return;}
 if(p.action==='list_failure'){await finish(list,{status:'success',templates:[{id:'A',name:'bad',width:40,height:20}]},p.scenario);assert(!calls.some(c=>c.url===detail('A')),'failed list must not select a success-envelope template');feedback('templateStatus');fallback();return;}
 if(['empty','literal'].includes(p.action)){await finish(list,{status:'success',templates:[]});fallback();if(p.action==='literal'){assert(ids.labelsContainer.textContent.includes('<img src=x onerror=fixture()>fixture material'),'fallback must preserve the literal material name');assert(ids.labelsContainer.textContent.includes('<b>spec</b>'));assert.equal(all(ids.labelsContainer,'img').length,0);}return;}
 if(p.action==='preference'){let templates=[{id:'A',name:'first',width:40,height:20},{id:'B',name:'default',width:70,height:30,is_default:p.scenario!=='first'},{id:'C',name:'90x50',width:p.scenario==='size'?90:60,height:50}];await finish(list,{status:'success',templates});const chosen={size:'C',default:'B',first:'A'}[p.scenario];assert.equal(ids.templateSelect.value,chosen);const data=template(chosen,chosen==='C'?90:chosen==='B'?70:40);if(chosen==='C')data.height=50;await finish(detail(chosen),{status:'success',template:data});rendered(chosen,data.width);return;}
 await finish(list,{status:'success',templates:[{id:'A',name:'A',width:40,height:20},{id:'B',name:'B',width:70,height:30}]});
 if(p.action==='manual'){const button=nodes.find(n=>n.attrs.onclick&&n.attrs.onclick.includes('printLabels('));assert(button,'manual print uses guarded production entry');vm.runInContext(button.attrs.onclick,ctx);assert.equal(printed,0);await finish(detail('A'),{status:'success',template:template('A')});vm.runInContext(button.attrs.onclick,ctx);assert.equal(printed,1);return;}
 if(p.action==='detail_failure'){await finish(detail('A'),{status:'success',template:template('A')},p.scenario);assert(!ids.labelsContainer.textContent.includes('template-A'),'HTTP failure must not render a success-envelope template');feedback('templateStatus');assert(!ids.sizeInfo.textContent.includes('40'));return;}
 if(p.action==='cache'){await finish(detail('A'),{status:'success',template:template('A')});rendered('A',40);select('B');await finish(detail('B'),{status:'success',template:template('B')});rendered('B',70);const count=calls.length;select('A');rendered('A',40);assert.equal(calls.length,count,'cached template must not refetch');return;}
 if(p.scenario==='clear'){select('');fallback();await finish(detail('A'),{status:'success',template:template('A')});fallback();}
 else if(p.scenario==='cached_new'){
  select('B');await finish(detail('B'),{status:'success',template:template('B')});rendered('B',70);select('A');select('B');rendered('B',70);await finish(detail('A'),{status:'success',template:template('A')});rendered('B',70);
 }else{select('B');if(p.scenario==='new_error'){await finish(detail('B'),{status:'error',msg:'fixture refusal'},'business');feedback('templateStatus');const visible=ids.labelsContainer.textContent,status=ids.templateStatus.textContent;await finish(detail('A'),{status:'success',template:template('A')});assert.equal(ids.labelsContainer.textContent,visible);assert.equal(ids.templateStatus.textContent,status);}else{await finish(detail('B'),{status:'success',template:template('B')});rendered('B',70);await finish(detail('A'),{status:'success',template:template('A')},p.scenario==='old_error'?'network':'success');rendered('B',70);}}
 assert.equal(printed,0);assert.equal(opened.length,0);for(const call of calls){assert.equal(call.options.method,'GET');assert.equal(call.options.headers['X-Requested-With'],'XMLHttpRequest');assert.equal(call.options.credentials,'same-origin');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(action,scenario='success',search='',script_override=None,page_override=None,auto_override=None):
    env=Environment(loader=FileSystemLoader(ROOT/'app/templates'),autoescape=True)
    materials=[dict(id=7,name='<img src=x onerror=fixture()>fixture material',code='C/&',barcode='BAR/& ',spec='<b>spec</b>',unit_name='件',stock=3),dict(id=8,name='fixture second',code='C8',unit_name='件')]
    context=dict(materials=materials,materials_data=materials,request=NS(args=({'autoprint':'1','copies':2,'ptoken':'fixture-not-a-real-token'} if action=='token' else {'autoprint':'1','copies':2 if scenario=='legacy' else 1} if action=='auto' else {})),current_user=NS(is_authenticated=action!='token'),config={},url_for=lambda *args,**kwargs:'/fixture')
    html=(env.from_string(page_override) if page_override is not None else env.get_template('print_batch_labels.html')).render(**context)
    scripts=[text for attrs,text in re.findall(r'<script([^>]*)>(.*?)</script>',html,re.S) if 'src=' not in attrs]
    if script_override is not None:scripts=[script_override]
    if auto_override is not None:
        rendered_auto=env.from_string(auto_override).render(**context)
        scripts[-1]=re.search(r'<script>(.*?)</script>',rendered_auto,re.S).group(1)
    payload=dict(action=action,scenario=scenario,search=search,nodes=Nodes(html).nodes,scripts=scripts,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
    node=shutil.which('node');assert node,'Node required for real label rendering'
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('scenario',['size','default','first'])
def test_actual_render_preserves_preference_layout_barcode_and_dimensions(scenario):
    run('preference',scenario)


@pytest.mark.parametrize('scenario',['old_success','old_error','new_error','cached_new','clear'])
def test_late_template_response_never_replaces_current_selection_or_clear(scenario):
    run('race',scenario)


def test_cached_template_reuses_real_render_without_another_request():
    run('cache')


@pytest.mark.parametrize('scenario',['http_success','null','html200'])
def test_label_list_failure_is_visible_and_uses_safe_default(scenario):
    run('list_failure',scenario)


@pytest.mark.parametrize('scenario',['http_success','null','html','business','network'])
def test_detail_failure_never_leaves_old_labels_or_false_success(scenario):
    run('detail_failure',scenario)


@pytest.mark.parametrize('scenario',['http_success','null','network'])
def test_excel_template_failure_is_visible_and_does_not_accept_invalid_list(scenario):
    run('excel_failure',scenario)


@pytest.mark.parametrize('search',['','?ids=1001%2C1002'])
def test_explicit_excel_download_preserves_encoded_ids_and_template_id(search):
    run('download',search=search)


def test_empty_template_list_preserves_default_90_by_50_labels():
    run('empty')


def test_fallback_material_fields_render_as_literal_text():
    run('literal')


@pytest.mark.parametrize('scenario',['loading','error','timeout','switch_delay','legacy'])
def test_autoprint_waits_for_actual_ready_labels_and_preserves_unmarked_legacy_flow(scenario):
    run('auto',scenario)


def test_manual_print_waits_for_current_template_ready():
    run('manual')


def test_anonymous_signed_print_page_keeps_default_labels_without_login_only_requests():
    run('token')
