"""Run the real global dropdown refresh with native/hidden DOM fields and real API."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('kind', ['category', 'unit', 'supplier'])
@pytest.mark.parametrize('action', ['success', 'empty', 'network', 'http', 'business', 'shape',
                                  'bad_row', 'order', 'latest_error', 'stale_error', 'selection',
                                  'disabled', 'disable_pending', 'detached', 'hidden', 'text',
                                  'multiple', 'only_hidden', 'independent', 'headers'])
def test_global_dropdowns_preserve_values_and_ignore_failed_or_obsolete_refreshes(kind, action):
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    start = app.index('window.WmsRefreshDropdowns = function(')
    end = app.index('\n};', start) + len('\n};')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const pending=[],calls=[],unhandled=[];
process.on('unhandledRejection',err=>unhandled.push(err));
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const decode=s=>s.replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&');
class Select {
 constructor(value='1'){this.tagName='SELECT';this.disabled=false;this.isConnected=true;this.events=[];this.options=[{value:'',textContent:'请选择'},{value:'1',textContent:'OLD A'},{value:'2',textContent:'OLD B'}];this._value=value;}
 get value(){return this._value;}set value(v){this._value=this.options.some(o=>o.value===String(v))?String(v):'';}
 get firstChild(){return this.options[0]||null;}
 removeChild(o){this.options.splice(this.options.indexOf(o),1);if(!this.options.some(x=>x.value===this._value))this._value=this.options[0]?.value||'';}
 appendChild(o){o.value=String(o.value);this.options.push(o);if(this.options.length===1)this._value=o.value;}
 get innerHTML(){return this.options.map(o=>'<option value="'+escape(o.value)+'">'+escape(o.textContent)+'</option>').join('');}
 set innerHTML(html){this.options=[...html.matchAll(/<option value="([^"]*)"([^>]*)>([\s\S]*?)<\/option>/g)].map(m=>({value:decode(m[1]),textContent:decode(m[3]),selected:m[2].includes('selected')}));this._value=(this.options.find(o=>o.selected)||this.options[0]||{value:''}).value;}
 dispatchEvent(event){this.events.push(event);}
}
class Hidden {constructor(){this.tagName='INPUT';this.value='42';this.children=[];}get firstChild(){return this.children[0]||null;}removeChild(c){this.children.splice(this.children.indexOf(c),1);}appendChild(c){this.children.push(c);}}
const groups={};for(const type of ['category','unit','supplier'])groups[type]={selects:p.action==='only_hidden'?[]:[new Select()],hidden:new Hidden()};
if(p.action==='multiple')groups[p.kind].selects.push(new Select('2'));
const current=groups[p.kind].selects[0];
if(p.action==='disabled')current.disabled=true;
const before=current?.innerHTML;
const document={querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null,
 querySelectorAll:s=>{const name=(s.match(/name=["']([^"']+)["']/)||[])[1];const group=groups[String(name).replace(/_id$/,'')];if(!group)return[];return s.startsWith('select')?group.selects:[...group.selects,group.hidden];},createElement:()=>({value:'',textContent:''})};
const ctx={document,FormData:class{},Event:class{constructor(type,o){this.type=type;this.bubbles=!!o?.bubbles;}},fetch:(url,options={})=>{const request={url,options};calls.push(request);return new Promise((resolve,reject)=>pending.push({...request,resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.escape,ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.refresh,ctx);
const run=()=>{const start=pending.length;ctx.WmsRefreshDropdowns();return pending.slice(start);};
const usual=[{id:1,name:'NEW A'},{id:2,name:'NEW B'}];
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(setImmediate);};
async function finish(batch,data=usual,error=null){for(const request of batch){const selected=request.url===({category:'/api/categories',unit:'/api/units',supplier:'/api/suppliers'})[p.kind];if(selected&&error==='network'){request.reject(Error('offline'));continue;}const body=selected?data:usual;request.resolve({ok:!(selected&&error==='http'),status:selected&&error==='http'?503:200,json:()=>Promise.resolve(body)});}await settle();}
(async()=>{
 const first=run();
 if(p.action==='only_hidden'){await finish(first);assert.equal(calls.length,0,'hidden fields are not dropdowns');for(const g of Object.values(groups))assert.equal(g.hidden.children.length,0);return;}
 if(['order','latest_error','stale_error'].includes(p.action)){
  const second=run();await finish(second,usual,p.action==='latest_error'?'network':null);await finish(first,[{id:3,name:'STALE'}],p.action==='stale_error'?'network':null);
  assert.equal(current.innerHTML,p.action==='latest_error'?before:new NewSelectHTML(usual,'1').html,'older results must not override the newest request');
 }else{
  if(p.action==='selection')current.value='2';
  if(p.action==='disable_pending')current.disabled=true;
  if(p.action==='detached')current.isConnected=false;
  let data=usual;
  if(p.action==='empty')data=[];
  if(p.action==='business')data={status:'error',msg:'拒绝刷新'};
  if(p.action==='shape')data={items:usual};
  if(p.action==='bad_row')data=[{id:1}];
  if(p.action==='text')data=[{id:1,name:'名"<img src=x onerror=attack()>&'},usual[1]];
  await finish(first,data,p.action==='independent'?'network':p.action);
  if(['network','http','business','shape','bad_row','disabled','disable_pending','detached','independent'].includes(p.action))assert.equal(current.innerHTML,before,'failed or inactive dropdown must keep its options and selected value');
  else if(p.action==='empty'){assert.equal(current.value,'');assert.equal(current.events.length,1);assert(current.events[0].bubbles);}
  else {assert.equal(current.value,p.action==='selection'?'2':'1');assert.equal(current.events.length,0);assert(current.options.some(o=>o.textContent===data[0].name));}
  if(p.action==='text')assert(!current.innerHTML.includes('<img'),'labels are literal text');
  if(p.action==='multiple'){assert.equal(groups[p.kind].selects[1].value,'2');assert(groups[p.kind].selects[1].options.some(o=>o.textContent==='NEW B'));}
  if(p.action==='independent')for(const [type,g]of Object.entries(groups))if(type!==p.kind)assert(g.selects[0].options.some(o=>o.textContent==='NEW A'),'one endpoint failure must not prevent other dropdowns refreshing');
 }
 if(p.action==='hidden')for(const g of Object.values(groups)){assert.equal(g.hidden.value,'42');assert.equal(g.hidden.children.length,0,'do not append options to hidden ID inputs');}
 if(p.action==='headers')assert(calls.every(c=>c.options.headers['X-Requested-With']==='XMLHttpRequest'&&c.options.credentials==='same-origin'));
 assert.equal(unhandled.length,0,'automatic refresh must not leak rejected promises');
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
function NewSelectHTML(items,value){const s=new Select(value);s.options=[{value:'',textContent:'请选择'},...items.map(x=>({value:String(x.id),textContent:x.name}))];this.html=s.innerHTML;}
'''
    node = shutil.which('node')
    assert node, 'Node.js required for global dropdown runtime tests'
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(kind=kind, action=action,
        refresh=app[start:end], escape=function(app, 'escapeHtml'),
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        helper=(ROOT / 'app/static/js/select-refresh.js').read_text(encoding='utf-8'))),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == 'ok', 'The async runtime must finish every assertion'
