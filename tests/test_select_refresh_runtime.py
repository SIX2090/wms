"""Execute all real select-refresh consumers with deferred HTTP responses."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [('in_order_add', 'in'), ('out_order_add', 'out'), ('out_order_add', 'department'),
         ('document_table_form', 'transfer'), ('document_table_form', 'check'), ('document_table_form', 'requisition')]


def function(source, name):
    start = source.index('function ' + name + '(')
    depth = 0
    for end in range(source.index('{', start), len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


@pytest.mark.parametrize('page,kind', CASES)
@pytest.mark.parametrize('scenario', ['selection', 'order', 'stale_failure', 'new_failure', 'failure', 'business', 'malformed', 'removed', 'same', 'readonly', 'detached', 'text'])
def test_refresh_preserves_current_context_and_ignores_obsolete_results(page, kind, scenario):
    run(page, kind, scenario)


@pytest.mark.parametrize('page,kind', CASES[:3])
@pytest.mark.parametrize('scenario', ['same', 'failure'])
def test_automatic_refresh_keeps_silent_notification_policy(page, kind, scenario):
    run(page, kind, scenario, silent=True)


def run(page, kind, scenario, silent=False):
    source = (ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf-8')
    name = 'refreshDepartments' if kind == 'department' else 'refreshWarehouses'
    asset = ROOT / 'app/static/js/select-refresh.js'
    app_js = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8')),sent=[],pending=[],messages=[];
const byName=p.kind==='transfer',key=p.kind==='department'?'departments':'warehouses';
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;|&#x27;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
class Select {
 constructor(value){this.tagName='SELECT';this.disabled=false;this.isConnected=true;this.events=[];this.handlers={};this.options=[{value:'',label:'请选择'},{value:byName?'仓库A':'1',label:'仓库A'},{value:byName?'仓库B':'2',label:'仓库B'}];this._value=value;this.html='initial';}
 get value(){return this._value;}set value(v){this._value=this.options.some(o=>o.value===String(v))?String(v):'';}
 set innerHTML(html){this.html=html;this.options=[...html.matchAll(/<option value="([^"]*)"([^>]*)>([\s\S]*?)<\/option>/g)].map(m=>({value:decode(m[1]),label:decode(m[3]),selected:m[2].includes('selected')}));this._value=(this.options.find(o=>o.selected)||this.options[0]||{value:''}).value;}
 get innerHTML(){return this.html;}
 addEventListener(name,fn){this.handlers[name]=fn;}
 dispatchEvent(event){this.events.push(event);if(this.handlers[event.type])this.handlers[event.type](event);}
}
const first=new Select(byName?'仓库A':'1'),second=new Select('仓库B'),location={value:'原库位'};
const fields={warehouse_id:first,department_id:first,from_location:first,to_location:second,location};
const document={querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:fields[(s.match(/name="([^"]+)"/)||[])[1]]||null};
const ctx={document,FormData,Headers,WeakMap,Event:class{constructor(type,options){this.type=type;this.bubbles=!!options?.bubbles;}},readonly:false,docType:p.kind,
 notifyMaterialRefresh:(m,t,s)=>{if(!s)messages.push({m,t});},showToast:(m,t)=>messages.push({m,t}),
 fetch:(url,options={})=>{sent.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.escape,ctx);vm.runInContext(p.api,ctx);if(p.helper)vm.runInContext(p.helper,ctx);vm.runInContext(p.source,ctx);
if(p.bind){vm.runInContext(p.bind,ctx);ctx.bindRequisitionLocationWarehouse();}
const refresh=()=>ctx[p.name]({silent:p.silent});
const settle=async()=>{for(let i=0;i<7;i++)await new Promise(setImmediate);};
async function reply(index,list,status=200,business=false){pending[index].resolve({ok:status<400,status,json:()=>Promise.resolve(business?{status:'error',msg:'拒绝刷新',[key]:list}:list===null?{}:{[key]:list})});await settle();}
const usual=[{id:1,name:'仓库A'},{id:2,name:'仓库B'}],empty=[{id:3,name:'仓库C'}];
(async()=>{
 if(p.scenario==='readonly')first.disabled=true;
 refresh();
 if(p.scenario==='readonly'){if(pending.length)await reply(0,empty);assert.equal(first.value,byName?'仓库A':'1','disabled historical selections must remain intact');return;}
 assert.equal(sent.length,1);assert.equal(sent[0].url,key==='warehouses'?'/warehouse/api/list':'/department/api/list');
 if(p.scenario==='selection'){
  first.value=byName?'仓库B':'2';first.dispatchEvent(new ctx.Event('change'));location.value='新库位';const before=first.events.length;
  await reply(0,usual);assert.equal(first.value,byName?'仓库B':'2','pending refresh must not restore an old warehouse/department');assert.equal(first.events.length,before);assert.equal(location.value,'新库位');
 }else if(['order','stale_failure','new_failure'].includes(p.scenario)){
  refresh();assert.equal(sent.length,2);
  if(p.scenario==='new_failure'){await reply(1,empty,503);const before=first.innerHTML;await reply(0,empty);assert.equal(first.innerHTML,before,'older success must not overwrite a newer failed request');}
  else {await reply(1,usual);const before=first.innerHTML,count=messages.length;
   if(p.scenario==='stale_failure'){pending[0].reject(Error('obsolete failure'));await settle();assert.equal(messages.length,count,'obsolete errors must not notify');}
   else {await reply(0,empty);assert.equal(first.innerHTML,before,'older response must not replace newer list');}
  }
 }else if(p.scenario==='failure'||p.scenario==='business'||p.scenario==='malformed'){
  const before=first.innerHTML;await reply(0,p.scenario==='malformed'?null:empty,p.scenario==='failure'?503:200,p.scenario==='business');assert.equal(first.innerHTML,before,'failed payload must not mutate selectors');
  if(['in','out','department'].includes(p.kind)&&!p.silent)assert(messages.some(m=>m.t==='danger'),'invalid response must be visible');
 }else if(p.scenario==='removed'){
  await reply(0,empty);assert.equal(first.value,'');assert.equal(first.events.length,1,'lost selection must notify dependent controls exactly once');assert.equal(first.events[0].bubbles,true);
  if(p.kind==='requisition')assert.equal(location.value,'');
 }else if(p.scenario==='detached'){
  first.isConnected=false;const before=first.innerHTML;await reply(0,empty);assert.equal(first.innerHTML,before);
 }else if(p.scenario==='text'){
  const bad='仓库"<img src=x onerror=attack()>&';await reply(0,[{id:1,name:bad},{id:2,name:'仓库B'}]);assert(first.options.some(o=>o.label===bad));assert(!first.innerHTML.includes('<img'));
 }else {await reply(0,usual);assert.equal(first.value,byName?'仓库A':'1');assert.equal(first.events.length,0);if(byName)assert.equal(second.value,'仓库B','transfer destination keeps its independent name value');}
 if(p.silent)assert.equal(messages.length,0);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node.js required for deferred selection refresh behavior'
    payload = dict(kind=kind, scenario=scenario, silent=silent, name=name, source=function(source, name),
                   helper=asset.read_text(encoding='utf-8') if asset.exists() else '',
                   bind=function(source, 'bindRequisitionLocationWarehouse') if kind == 'requisition' else '',
                   escape=function(app_js, 'escapeHtml'), api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('role', ['viewer', 'warehouse', 'admin'])
def test_shared_helper_loads_once_after_its_dependencies(role):
    from tests.test_shell_navigation_asset import render_shell
    html = render_shell(role)
    asset = '/static/js/select-refresh.js?v=nav-test-v1'
    assert html.count(asset) == 1
    assert html.index('js/api.js') < html.index('js/app.js') < html.index(asset)
    tag = next(tag for tag in re.findall(r'<script[^>]+>', html) if asset in tag)
    assert not re.search(r'\b(async|defer|type)=?', tag)


def test_shared_helper_response_is_cacheable_and_matches_disk():
    import app as app_module
    client = app_module.app.test_client()
    response = client.get('/static/js/select-refresh.js?v=fixture')
    assert response.status_code == 200
    assert response.mimetype in {'text/javascript', 'application/javascript'}
    assert response.data == (ROOT / 'app/static/js/select-refresh.js').read_bytes()
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert client.get('/static/js/select-refresh.js', headers={'If-None-Match': response.headers['ETag']}).status_code == 304
