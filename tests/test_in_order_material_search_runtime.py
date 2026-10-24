"""Run the real inbound search, picker, cache refresh and API with delayed HTTP."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.index('function ' + name + '(')
    opening = source.index(') {', start) + 2
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


@pytest.mark.parametrize('action', [
    'exact', 'single_request', 'typing', 'clear', 'row', 'escape', 'outside', 'blur', 'detach',
    'order', 'stale_failure', 'selected', 'debounce', 'clear_before_timer', 'lowercase', 'fallback', 'fallback_edit', 'fallback_order',
    'fallback_detach', 'refresh', 'refresh_order', 'refresh_busy',
])
def test_real_inbound_material_async_lifecycle(action):
    run(action)


@pytest.mark.parametrize('action', ['search_error', 'fallback_error', 'refresh_error'])
@pytest.mark.parametrize('error', ['http', 'business', 'shape', 'network'])
def test_errors_do_not_apply_false_success_data(action, error):
    run(action, error)



@pytest.mark.parametrize('action', ['single_request', 'typing', 'clear', 'row', 'escape', 'outside', 'blur',
                                  'detach', 'order', 'stale_failure', 'selected', 'debounce', 'clear_before_timer',
                                  'fallback', 'fallback_edit', 'fallback_order', 'fallback_detach'])
def test_purchase_request_uses_the_same_safe_lifecycle(action):
    run(action, page='pr')


@pytest.mark.parametrize('action', ['search_error', 'fallback_error'])
@pytest.mark.parametrize('error', ['http', 'business', 'shape', 'network'])
def test_purchase_request_error_results_are_not_applied(action, error):
    run(action, error, page='pr')


def run(action, error=None, page="in"):
    source = (ROOT / ('app/templates/in_order_add.html' if page == 'in' else 'app/templates/purchase_request_add.html')).read_text(encoding='utf-8')
    if page == 'in':
        core = source[source.index('function formatStock('):source.index('function handleKeydown(')]
        key = function(source, 'handleKeydown')
        refresh = source[source.index('function fetchMaterialsPage('):source.index('function refreshSuppliers(')]
    else:
        names = ['normalizeSearchValue', 'materialSearchText', 'findMaterialQuickMatch', 'getMaterialMatches',
                 'bindMaterialInput', 'renderMaterialDropdown', 'showDropdown', 'highlightMaterialDropdownItem',
                 'selectMaterialByDropdownItem', 'getMaterialUnitName', 'getMaterialUnitId', 'selectMaterial']
        if 'function cancelMaterialSearch(' in source:
            names.append('cancelMaterialSearch')
        core = "const MATERIAL_SEARCH_LIMIT_HINT=100;const materialSearchState={seq:0,timer:null};\n" + '\n'.join(function(source, name) for name in names)
        key = refresh = ''
    click = re.search(r"document.addEventListener\('click', function\(e\) \{.*?\n\s*\}\);", source, re.S).group(0)
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const timers=new Map(),pending=[],calls=[],messages=[],fills=[];let nextTimer=0;
const field=value=>({value,dataset:{},handlers:{},addEventListener(name,fn){this.handlers[name]=fn;},style:{display:'none'},innerHTML:'',focused:0,focus(){this.focused++;document.activeElement=this;},select(){},querySelectorAll(){return [];},querySelector(){return null;},classList:{contains:c=>c==='material-code'}});
function row(code){const fields={};for(const name of ['code','brand','name','spec','unit','stock','price','qty','batch-no','expiry'])fields['.material-'+name]=field(name==='code'?code:name==='price'?'7':'');fields['.material-dropdown']=field('');for(const [a,b] of Object.entries({'.quantity':'.material-qty','.spec':'.material-spec','.unit-name':'.material-unit','.estimated-price':'.material-price'}))fields[a]=fields[b];return {fields,isConnected:true,querySelector:s=>fields[s]||null};}
const rows=[row(''),row('')],button={disabled:false,innerHTML:'刷新物料'},purpose=field('');
const document={activeElement:rows[0].fields['.material-code'],querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:s.startsWith('button[')?button:s==='[name="purpose"]'?purpose:null,querySelectorAll:s=>s==='#materialTableBody tr'?rows:[],addEventListener:(name,fn)=>{document[name]=fn;}};
const material=(code,name='料'+code)=>({id:code==='M350'?350:1,code,name,brand:'品牌',spec:'规格',unit:{name:'个'},stock:4,price:12,purpose:'用途'});
const initial=[material('LOCAL')];
const ctx={document,URLSearchParams,FormData:class{},showToast:(message,type)=>messages.push({message,type}),
 setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),
 fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},
 updateRowAmount(){},calcAmount:r=>fills.push(r.fields['.material-code'].value),focusNextEditable(){},WMS:{positionDropdown(){}}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.escape,ctx);vm.runInContext(p.api,ctx);
vm.runInContext('const materials='+JSON.stringify(initial)+';let activeDropdown=null,activeIndex=-1,activeMaterialDropdown=null,activeMaterialIndex=-1;',ctx);
vm.runInContext(p.notify,ctx);vm.runInContext(p.core,ctx);vm.runInContext(p.key,ctx);vm.runInContext(p.click,ctx);vm.runInContext(p.refresh,ctx);if(p.page==='pr')rows.forEach(r=>ctx.bindMaterialInput(r));
const evaluate=s=>vm.runInContext(s,ctx),codes=()=>Array.from(evaluate('materials'),m=>m.code);
const tick=delay=>{for(const [id,t] of [...timers])if(t.delay===delay){timers.delete(id);t.fn();}};
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
const choose=(r,code)=>p.page==='pr'?ctx.selectMaterialByDropdownItem(r,{dataset:{code,materialId:code==='LOCAL'?'1':'350'}}):ctx.selectMaterial(r,code);
function type(index,value){const r=rows[index];r.fields['.material-code'].value=value;document.activeElement=r.fields['.material-code'];if(p.page==='pr')r.fields['.material-code'].handlers.input.call(r.fields['.material-code']);else ctx.handleMaterialCodeInput(r);}
async function finish(i,data,kind='search',err=null){let body=kind==='refresh'?{status:'success',materials:data}:{status:'success',data,total:data.length};
 if(err==='network')pending[i].reject(Error('offline'));
 else {if(err==='business')body.status='error';if(err==='shape')body=kind==='refresh'?{status:'success',materials:{bad:true}}:{status:'success',data:null};pending[i].resolve({ok:err!=='http',status:err==='http'?503:200,json:()=>Promise.resolve(body)});}await settle();}
const html=i=>rows[i].fields['.material-dropdown'].innerHTML,visible=i=>rows[i].fields['.material-dropdown'].style.display!=='none';
const escape=()=>{const event={key:'Escape',target:rows[0].fields['.material-code'],preventDefault(){}};if(p.page==='pr')rows[0].fields['.material-code'].handlers.keydown(event);else ctx.handleKeydown(event,rows[0]);};
(async()=>{
 if(p.action.startsWith('refresh')){
  const a=ctx.refreshMaterials();assert(a&&typeof a.then==='function','refresh must return its completion Promise');
  if(p.action==='refresh_order'||p.action==='refresh_busy'){
   const b=ctx.refreshMaterials();
   if(p.action==='refresh_busy'){await finish(0,[material('OLD')],'refresh');assert(button.disabled,'old finally cannot unlock the newer refresh');await finish(1,[material('NEW')],'refresh');}
   else {await finish(1,[material('NEW')],'refresh');await finish(0,[material('OLD')],'refresh');}
   assert(codes().includes('NEW'));assert(!codes().includes('OLD'));
  }else if(p.action==='refresh_error'){
   await finish(0,[material('POISON')],'refresh',p.error);assert.deepEqual(codes(),['LOCAL']);assert(messages.some(m=>m.type==='danger'));
  }else{await finish(0,[material('NEW')],'refresh');assert(codes().includes('LOCAL'));assert(codes().includes('NEW'));}
  await a;assert(!button.disabled);return;
 }
 if(p.action.startsWith('fallback')){
  rows[0].fields['.material-code'].value='M';choose(rows[0],'M350');assert.equal(calls.length,1);
  assert(calls[0].url.includes('/material/api/by_codes?'),'picker recovery must resolve the exact canonical code, not the first fuzzy result');
  if(p.action==='fallback_edit')type(0,'OTHER');
  if(p.action==='fallback_detach')rows[0].isConnected=false;
  if(p.action==='fallback_order'){choose(rows[0],'LOCAL');await finish(0,[material('M350')]);assert.equal(rows[0].fields['.material-code'].value,'LOCAL');return;}
  await finish(0,[material('M350')],'search',p.action==='fallback_error'?p.error:null);
  if(p.action==='fallback_error'||p.action==='fallback_edit'||p.action==='fallback_detach'){assert.notEqual(rows[0].fields['.material-name'].value,'料M350');assert.equal(rows[0].fields['.material-qty'].focused,0);}
  else {assert.equal(rows[0].fields['.material-code'].value,'M350');assert.equal(rows[0].fields['.material-name'].value,'料M350');assert.equal(rows[0].fields['.material-qty'].focused,p.page==='in'?1:0);}return;
 }
 if(p.action==='debounce'){type(0,'OLD');type(0,'M350');tick(220);assert.equal(calls.length,1);assert(calls[0].url.includes('kw=M350'));await finish(0,[material('M350')]);assert(html(0).includes('M350'));return;}
 if(p.action==='clear_before_timer'){type(0,'M350');type(0,'');tick(220);tick(400);assert.equal(calls.length,0);return;}
 type(0,p.action==='lowercase'?'m350':'M350');tick(220);assert.equal(calls.length,1);
 if(p.action==='single_request'){tick(400);assert.equal(calls.length,1,'cache miss must not also reload the first 300 materials');await finish(0,[material('M350')]);return;}
 if(p.action==='typing')type(0,'NEW');
 if(p.action==='clear')type(0,'');
 if(p.action==='row')type(1,'');
 if(p.action==='escape')escape();
 if(p.action==='outside')document.click({target:{closest:()=>null}});
 if(p.action==='blur')document.activeElement=rows[0].fields['.material-qty'];
 if(p.action==='detach')rows[0].isConnected=false;
 if(p.action==='selected')choose(rows[0],'LOCAL');
 if(p.action==='order'||p.action==='stale_failure'){
  type(0,'NEW');tick(220);await finish(1,[material('NEW')]);const good=html(0);
  await finish(0,[material('M350')],'search',p.action==='stale_failure'?'network':null);assert.equal(html(0),good);assert(!codes().includes('M350'));return;
 }
 const beforeHtml=html(0),beforeVisible=visible(0);
 await finish(0,[material('M350')],'search',p.action==='search_error'?p.error:null);
 if(['typing','clear','row','escape','outside','detach','selected'].includes(p.action)){
  assert.equal(html(0),beforeHtml,'obsolete response must not replace current options');assert.equal(visible(0),beforeVisible,'obsolete response must not change visibility');assert(!codes().includes('M350'),'obsolete data must not enter cache');
  if(p.action==='selected')assert.equal(rows[0].fields['.material-code'].value,'LOCAL');return;
 }
 if(p.action==='search_error'){assert(!codes().includes('M350'));if(p.page==='in')assert(!visible(0));else assert(html(0).includes('无匹配物料'));return;}
 if(p.action==='blur'){assert(!visible(0));if(p.page==='in')assert.equal(rows[0].fields['.material-name'].value,'料M350');assert.equal(document.activeElement,rows[0].fields['.material-qty']);return;}
 assert.equal(rows[0].fields['.material-name'].value,'料M350','exact code outside the initial 300 must fill without a manual selection');
 assert.equal(rows[0].fields['.material-unit'].value,'个');assert.equal(rows[0].fields['.material-price'].value,'7','keep entered price');assert.equal(purpose.value,'用途');assert(visible(0));
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""
    app_js = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    binary = shutil.which('node')
    assert binary, 'Node.js required for frontend runtime verification'
    payload = dict(action=action, error=error, page=page, core=core, refresh=refresh, click=click,
                   key=key, notify=function((ROOT / 'app/templates/in_order_add.html').read_text(encoding='utf-8'), 'notifyMaterialRefresh'), escape=function(app_js, 'escapeHtml'),
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([binary, '--max-old-space-size=64', '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
