"""BUG-2026-10-22-013: real subcontract stock-list scripts and shared HTTP client."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['issue', 'receive']


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('action', ['materials', 'add', 'complete', 'revert', 'delete', 'import'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'html', 'unauthorized', 'expired', 'network', 'null'])
def test_stock_list_runtime(page, action, scenario):
    run(page, action, scenario)


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('action', ['complete', 'revert', 'delete'])
def test_manual_cancel_sends_no_request(page, action):
    run(page, action, 'cancel')


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('action', ['add', 'import'])
def test_empty_input_sends_no_request(page, action):
    run(page, action, 'empty')


@pytest.mark.parametrize('page', PAGES)
def test_material_cache_shape_and_explicit_server_cap(page):
    run(page, 'materials', 'shape')
    source = (ROOT / f'app/templates/subcontract_{page}.html').read_text(encoding='utf-8')
    assert '前1000' in source and 'data-ks' in source


@pytest.mark.parametrize('page', PAGES)
def test_no_legacy_post_transport(page):
    source = (ROOT / f'app/templates/subcontract_{page}.html').read_text(encoding='utf-8')
    assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(|\$\.(?:ajax|post)\s*\(', source)


@pytest.mark.parametrize('page', PAGES)
def test_bulk_delete_uses_existing_global_toolbar_not_dead_local_binding(page):
    from html.parser import HTMLParser
    class Ids(HTMLParser):
        def __init__(self):
            super().__init__()
            self.ids = []
        def handle_starttag(self, tag, attrs):
            self.ids.extend(value for key, value in attrs if key == 'id')
    source = (ROOT / f'app/templates/subcontract_{page}.html').read_text(encoding='utf-8')
    parser = Ids()
    parser.feed(source)
    assert 'batchDeleteBtn' not in parser.ids
    assert 'batchDeleteBtn' not in source, 'Do not retain an unreachable local delete binding'
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    module = shared.split(f'subcontract_{page}: {{', 1)[1].split('\n    },', 1)[0]
    path = re.search(r"deleteUrl: '([^']+)'", module).group(1)
    assert path == f'/subcontract_{page}/batch_delete'
    routes = (ROOT / 'app/routes/subcontract.py').read_text(encoding='utf-8')
    assert f"@app.route('{path}', methods=['POST'])" in routes
    assert 'postJsonForAction(module.deleteUrl, { ids: ids })' in shared


def run(page, action, scenario):
    source = (ROOT / f'app/templates/subcontract_{page}.html').read_text(encoding='utf-8')
    source = '\n'.join(re.findall(r'<script\b[^>]*>([\s\S]*?)</script>', source))
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let requests=[],messages=[],alerts=[],reloads=0,timers=[],handlers={},scenario=p.scenario;
const file={files:scenario==='empty'?[]:[{name:'fixture.xlsx'}],value:'fixture.xlsx'};
const form={id:'addForm',action:'/subcontract/'+p.page+'/import',addEventListener(){},querySelectorAll:()=>[]};
const addModal={id:'addModal',addEventListener(){}},saveButton={disabled:false},warehouse={value:scenario==='empty'?'':'2'};

const dataRows=[['warehouse_id','2'],['subcontract_order_id','9'],['material_id','3'],['material_id','4'],['material_code','M3'],['material_code','M4'],['quantity','2'],['quantity','3'],['unit_id','1'],['unit_id','1'],['item_remark','甲&乙'],['item_remark','中文']];
if(p.page==='receive')dataRows.push(['scrap_quantity','0'],['scrap_quantity','1'],['price','2'],['price','3']);
class FormData{constructor(f){this.form=f;this.rows=dataRows.slice();}get(k){return this.rows.find(x=>x[0]===k)?.[1]??null;}getAll(k){return this.rows.filter(x=>x[0]===k).map(x=>x[1]);}entries(){return this.rows[Symbol.iterator]();}delete(k){this.rows=this.rows.filter(x=>x[0]!==k);}append(k,v){this.rows.push([k,String(v)]);}}
function wrapper(arg){return{0:arg==='#addForm'?form:arg,length:1,
 click(f){handlers[arg]=f;},on(){return this;},find(){return this;},trigger(){return this;},each(){},
 prop(k,v){if(typeof arg==='object'){if(v===undefined)return arg[k];arg[k]=v;}return this;},
 val(){return typeof arg==='object'?arg.value:scenario==='empty'?'':'2';},html(){return this;},modal(){},append(){},remove(){},data(){return '2';}};}
const document={querySelector:s=>s.includes('csrf-token')?{content:'fixture-csrf'}:null,querySelectorAll:()=>[],
 getElementById:id=>id==='file'?file:['form','addForm'].includes(id)?form:id==='addModal'?addModal:id==='submitAdd'?saveButton:id.endsWith('Warehouse')?warehouse:{id}};
const ctx={document,$:wrapper,FormData,Headers,Promise,URL,registerDetailRowActions(){},
 showToast:(m,t)=>messages.push({m,t}),alert(m){assert.equal(reloads,0);alerts.push(m);},
 confirm:()=>scenario!=='cancel',showConfirm:()=>Promise.resolve(scenario!=='cancel'),
 location:{href:'original',reload(){reloads++;}},setTimeout:(f,ms)=>{timers.push({f,ms});return 1;},
 fetch:(url,options)=>{
  requests.push({url,options});
  if(url==='/api/material/all'&&p.action!=='materials')return response('success',true);
  return response(scenario,url==='/api/material/all');
 }};
function resolveResponse(kind,resolve){const status=kind==='http'?409:kind==='html'?502:kind==='unauthorized'?401:kind==='expired'?419:200;
resolve({status,ok:status===200,json:()=>kind==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve(kind==='null'?null:kind==='shape'?{status:'success',data:{items:[]}}:['business','http'].includes(kind)?{status:'error',msg:'fixture reason'}:{status:'success',msg:'fixture ok',data:[{id:3,code:'M3',unit:{id:1}}]})});}
function response(kind,material){if(kind==='network')return Promise.reject(Error('offline'));return new Promise(resolve=>resolveResponse(kind,resolve));}
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.actionHelper,ctx);vm.runInContext(p.selectionHelper,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
async function invoke(){
 if(p.action==='materials')return ctx.loadMaterials();
 if(p.action==='add')return handlers['#submitAdd'].call({});
 if(p.action==='import')return ctx.submitDocumentImport('form','file');
 const name=p.action+(p.page==='issue'?'Issue':'Receive');return ctx[name](7);
}
function verifyRequest(request){const headers=new Headers(request.options.headers);assert.equal(request.options.method,'POST');assert.equal(request.options.credentials,'same-origin');assert.equal(headers.get('X-CSRFToken'),'fixture-csrf');assert.equal(headers.get('X-Requested-With'),'XMLHttpRequest');
 if(['add','import'].includes(p.action)){assert(request.options.body instanceof FormData);assert.equal(request.options.body.form,form);assert(!headers.has('Content-Type'));assert.deepEqual(request.options.body.getAll('quantity'),['2','3']);assert.deepEqual(request.options.body.getAll('material_id'),['3','4']);assert.equal(request.options.body.get('warehouse_id'),'2');if(p.page==='receive')assert.deepEqual(request.options.body.getAll('scrap_quantity'),['0','1']);}
 else if(p.action==='complete')assert.deepEqual(JSON.parse(request.options.body),{});else assert.equal(request.options.body,undefined);
}
(async()=>{
 await flush();await flush();
 if(p.action==='materials'){
  assert.equal(requests.length,1);assert.equal(requests[0].url,'/api/material/all');verifyRequest(requests[0]);
  if(scenario==='success'){assert.equal(ctx.materialsCache.length,1);assert.equal(ctx.materialsCache[0].unit.id,1);}
  else{assert.deepEqual(Array.from(ctx.materialsCache),[]);assert(messages.some(x=>x.t==='danger'));scenario='success';await invoke();assert.equal(ctx.materialsCache.length,1);}
  return;
 }
 requests=[];messages=[];
 await invoke();await flush();await flush();
 if(['cancel','empty'].includes(scenario)){assert.equal(requests.length,0);assert.equal(reloads,0);return;}
 assert.equal(requests.length,1);requests.forEach(verifyRequest);
 const endpoint='/subcontract/'+p.page;
 const expected=p.action==='add'?endpoint+'/add':p.action==='import'?endpoint+'/import':p.action==='delete'?endpoint+'/delete/7':endpoint+'/7/'+p.action;
 assert.equal(requests[0].url,expected);
 if(p.action==='import')assert.equal(file.value,'');
 if(scenario==='success'){
  if(p.action==='import'){assert.equal(timers.length,1);assert.equal(timers[0].ms,900);timers[0].f();}
  assert.equal(reloads,1);
 }else{
  assert.equal(reloads,0);assert.equal(alerts.length,0);assert(messages.some(x=>x.t==='danger'));
  if(['business','http'].includes(scenario))assert(messages.some(x=>x.m.includes('fixture reason')));
  if(scenario==='html')assert(messages.some(x=>x.m.includes('502')));
  if(['unauthorized','expired'].includes(scenario))assert.equal(ctx.location.href,'/login');
  scenario='success';await invoke();await flush();await flush();timers.forEach(t=>t.f());assert.equal(reloads,1,'failure remains retryable');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for real page/runtime verification'
    env = dict(os.environ, NODE_OPTIONS='--max-old-space-size=64')
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(page=page, action=action, scenario=scenario, script=source, selectionHelper=(ROOT / 'app/static/js/subcontract-material-selection.js').read_text(encoding='utf-8'), api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'), actionHelper=(ROOT / 'app/static/js/document-action.js').read_text(encoding='utf-8'))), capture_output=True, encoding='utf-8', env=env, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
