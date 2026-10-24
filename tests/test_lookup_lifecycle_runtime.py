"""BUG-2026-10-24-020: execute real lookup closures and API with delayed replies."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def lookup_source(page):
    if page == 'contract':
        text = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
        pos = text.index('// ==================== 合同编号 / 工程名称 快速匹配')
        return text[text.index('(function(global)', pos):text.index('})(window);', pos) + 11]
    filename, marker = ('in_order.html', 'projectNameFilterInput') if page == 'project' else ('out_order_add.html', 'pickerInput')
    text = (ROOT / 'app/templates' / filename).read_text(encoding='utf-8')
    pos = text.index("getElementById('" + marker + "')")
    start = text.rindex('(function()', 0, pos)
    end = text.index('})();', pos) + 5
    return text[start:end]


SCRIPT = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const pending=[],timers=new Map(),events={},toasts=[],body=[];let timerId=0;
const esc=s=>String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
function element(){const e={value:'',style:{display:'none'},dataset:{},attrs:{},handlers:{},children:[],isConnected:true,parts:{},
 addEventListener(n,f){this.handlers[n]=f;},setAttribute(n,v){this.attrs[n]=String(v);},getAttribute(n){return this.attrs[n];},
 getBoundingClientRect(){return {left:10,bottom:50,width:100};},getClientRects(){return [{}];},scrollIntoView(){},
 appendChild(x){this.children.push(x);x.parent=this;},remove(){this.isConnected=false;const i=body.indexOf(this);if(i>=0)body.splice(i,1);},
 contains(x){return x===this||this.children.includes(x);},closest(selector){return selector==='tr'?this.row:null;},
 querySelectorAll(){return this.children;},querySelector(s){if(s.includes('active'))return this.children.find(x=>x.classList.contains('active'))||null;return this.parts[s]??={textContent:''};}};
 e.classList={values:new Set(),add(x){this.values.add(x)},remove(x){this.values.delete(x)},contains(x){return this.values.has(x)},toggle(x,on){on?this.add(x):this.remove(x)}};
 Object.defineProperty(e,'innerHTML',{get(){return this.html||''},set(v){this.html=v;this.children=[];
  for(const m of v.matchAll(/data-(pn|index)="([^"]*)"/g)){const item=element();item.attrs['data-'+m[1]]=m[2];item.dataset[m[1]]=m[2];if(m[1]==='pn'&&this.children.length===0)item.classList.add('active');this.appendChild(item);}}});return e;}
const input=element(),other=element(),projectMate=element(),dropdown=element(),button=element();input.value='OLD';other.value='OTHER';
input.row={querySelector:s=>s==='.line-contract-no'?input:projectMate};other.row={querySelector:s=>s==='.line-contract-no'?other:element()};
const fields={projectNameFilterInput:input,projectNameDropdown:dropdown,pickerInput:input,pickerDropdown:dropdown,pickerSearchBtn:button};
const doc={activeElement:input,getElementById:id=>id==='wms-contract-autocomplete-style'?{}:fields[id],
 querySelector:s=>s==='meta[name="csrf-token"]'?{content:'test-token'}:null,createElement:element,
 body:{appendChild(x){body.push(x)}},addEventListener(n,f){events[n]=f;}};
const ctx={document:doc,FormData,URLSearchParams,console,scrollY:0,escapeHtml:esc,showToast:(m)=>toasts.push(m),confirm:()=>false,location:{href:'original'},
 setTimeout(f){const id=++timerId;timers.set(id,f);return id;},clearTimeout:id=>timers.delete(id),
 fetch:(url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject}))};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.code,ctx);
if(p.page==='contract'){ctx.WMS.ContractAutocomplete.bind(input);ctx.WMS.ContractAutocomplete.bind(other);}
const tick=()=>new Promise(r=>setImmediate(r));
function fire(node,name,extra={}){node.handlers[name]?.call(node,{key:'',target:node,preventDefault(){this.prevented=true},stopPropagation(){},...extra});}
function flush(){const work=[...timers.values()];timers.clear();work.forEach(f=>f());}
function menu(){return p.page==='contract'?body.at(-1):dropdown;}
function visible(){const m=menu();return !!m&&(p.page==='contract'||m.style.display==='block');}
function contains(name){const m=menu();return visible()&&(p.page==='contract'?m.children.some(x=>x.attrs['data-contract-no']===name):m.innerHTML.includes(name));}
function reply(index,name,kind='ok'){
 const req=pending[index];assert(req,'request '+index+' exists');if(kind==='network'){req.reject(Error('offline'));return;}
 let data=p.page==='picker'?[{name,department:'D',phone:'P'}]:{contracts:[{contract_no:name,project_name:'P-'+name}]};
 if(kind==='shape')data=p.page==='picker'?{}:{contracts:{bad:true}};
 if(kind==='bad-item')data=p.page==='picker'?[null]:{contracts:[null]};
 if(kind==='empty')data=p.page==='picker'?[]:{contracts:[]};
 const result=kind==='null'?null:kind==='business'?{status:'error',msg:'拒绝'}:{status:'success',data};
 req.resolve({ok:!['http','html'].includes(kind),status:['http','html'].includes(kind)?500:200,json:()=>kind==='html'?Promise.reject(SyntaxError('html')):Promise.resolve(result)});
}
function choose(){const item=menu().children[0];assert(item);let prevented=false;fire(item,'mousedown',{preventDefault(){prevented=true}});if(p.page==='picker')fire(item,'click');return prevented;}
(async()=>{
 fire(input,'focus');assert.equal(pending.length,1);
 if(p.mode==='success'){reply(0,'MATCH');await tick();assert(contains('MATCH'));assert.equal(pending[0].options.credentials,'same-origin');assert.equal(pending[0].options.headers['X-Requested-With'],'XMLHttpRequest');return;}
 if(['http','html','business','shape','bad-item','network','null'].includes(p.mode)){
  reply(0,'BAD',p.mode);await tick();assert(!contains('BAD'));assert(toasts.length||menu()?.innerHTML.includes('失败'),'current failure must be visible');
  fire(input,'focus');assert.equal(pending.length,2,'failed keyword must retry');reply(1,'RECOVER');await tick();assert(contains('RECOVER'));return;
 }
 if(p.mode==='empty'){reply(0,'EMPTY','empty');await tick();assert(!contains('EMPTY'));assert.equal(toasts.length,0);return;}
 if(['late-success','late-error','late-http','late-shape'].includes(p.mode)){
  input.value='NEW';fire(input,'focus');reply(1,'NEW');await tick();reply(0,'OLD',{'late-error':'network','late-http':'http','late-shape':'shape'}[p.mode]||'ok');await tick();assert(contains('NEW'));assert(!contains('OLD'));assert.equal(toasts.length,0);return;
 }
 if(p.mode==='debounce'){
  input.value='NEW';fire(input,'input');reply(0,'OLD');await tick();assert(!contains('OLD'));flush();assert.equal(pending.length,2);reply(1,'NEW');await tick();assert(contains('NEW'));return;
 }
 if(p.mode==='cancel-timer'){
  input.value='NEW';fire(input,'input');input.value='';fire(input,'input');flush();assert.equal(pending.length,1);reply(0,'OLD');await tick();assert(!visible());return;
 }
 if(['clear','escape','blur','outside','detach','silent-change'].includes(p.mode)){
  if(p.mode==='clear'){input.value='';fire(input,'input');}
  if(p.mode==='escape')fire(input,'keydown',{key:'Escape'});
  if(p.mode==='blur'){doc.activeElement=null;fire(input,'blur');}
  if(p.mode==='outside')events.click?.({target:element()});
  if(p.mode==='detach')input.isConnected=false;
  if(p.mode==='silent-change')input.value='CHANGED';
  reply(0,'OLD');await tick();assert(!contains('OLD'));if(['clear','escape','blur','outside'].includes(p.mode))assert(!visible());return;
 }
 if(p.mode==='mousedown'){
  reply(0,'MATCH');await tick();assert(choose(),'mousedown must prevent losing input focus');assert(!visible());
  assert.equal(input.value,p.page==='project'?'P-MATCH':'MATCH');if(p.page==='contract')assert.equal(projectMate.value,'P-MATCH');return;
 }
 if(p.mode==='keyboard'){
  reply(0,'MATCH');await tick();fire(input,'keydown',{key:'ArrowDown'});fire(input,'keydown',{key:'Enter'});assert.equal(input.value,p.page==='project'?'P-MATCH':'MATCH');assert(!visible());return;
 }
 if(p.mode==='choose-late'){
  fire(input,'focus');reply(1,'MATCH');await tick();choose();reply(0,'OLD');await tick();assert(!visible());assert.equal(input.value,p.page==='project'?'P-MATCH':'MATCH');return;
 }
 if(p.mode==='cache-stale'){
  reply(0,'CACHED');await tick();input.value='PENDING';fire(input,'focus');input.value='OLD';fire(input,'input');assert(contains('CACHED'));reply(1,'PENDING');await tick();assert(contains('CACHED'));return;
 }
 if(p.mode==='cross-row'||p.mode==='old-blur-timer'){
  if(p.mode==='old-blur-timer')fire(input,'blur');doc.activeElement=other;fire(other,'focus');reply(1,'OTHER');await tick();reply(0,'OLD');await tick();flush();assert(contains('OTHER'));choose();assert.equal(other.value,'OTHER');assert.equal(input.value,'OLD');return;
 }
 if(p.mode==='empty-button'){
  input.value='';fire(input,'input');fire(button,'click');assert(pending[1].url.endsWith('q='));reply(1,'ALL');await tick();assert(contains('ALL'));reply(0,'OLD');await tick();assert(contains('ALL'));return;
 }
 throw Error('unknown mode '+p.mode);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1});
'''

CASES = [(page, mode) for page in ['contract', 'project', 'picker'] for mode in [
    'success', 'http', 'html', 'business', 'shape', 'bad-item', 'network', 'null', 'empty',
    'late-success', 'late-error', 'late-http', 'late-shape', 'debounce', 'cancel-timer', 'clear', 'escape',
    'blur', 'outside', 'detach', 'silent-change', 'mousedown', 'keyboard', 'choose-late',
]] + [('contract', 'cache-stale'), ('project', 'cache-stale'),
      ('contract', 'cross-row'), ('contract', 'old-blur-timer'), ('picker', 'empty-button')]


@pytest.mark.parametrize('page,mode', CASES)
def test_lookup_lifecycle(page, mode):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for actual lookup lifecycle')
    payload = {'page': page, 'mode': mode, 'code': lookup_source(page),
               'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')}
    result = subprocess.run([node, '--max-old-space-size=64', '-e', SCRIPT], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
