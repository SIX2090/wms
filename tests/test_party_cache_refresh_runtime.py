"""Exercise the actual array-cache consumers and HTTP client with delayed replies."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('in_order_add', 'refreshSuppliers', 'supplier_id', '/api/suppliers'),
    ('in_order_add', 'refreshSuppliers', 'customer_id', '/api/customers'),
    ('out_order_add', 'refreshCustomers', '', '/api/customers'),
    ('after_sale_out_add', 'refreshCustomers', '', '/api/customers'),
    ('material', 'refreshQuickSelectData', 'supplier', '/api/suppliers'),
    ('material', 'refreshQuickSelectData', 'category', '/api/categories'),
    ('material', 'refreshQuickSelectData', 'unit', '/api/units'),
]


@pytest.mark.parametrize('page,name,mode,url', CASES)
@pytest.mark.parametrize('action', ['success', 'empty', 'order', 'latest_error', 'stale_error',
                                      'http', 'business', 'shape', 'network', 'invalid_row', 'duplicate', 'silent'])
def test_real_cache_consumer_keeps_latest_complete_valid_list(page, name, mode, url, action):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    asset = ROOT / 'app/static/js/list-cache.js'
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const pending=[],calls=[],messages=[];
const ctx={document:{querySelector:()=>null},FormData:class{},
 fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},
 notifyMaterialRefresh:(msg,type,silent)=>{if(!silent)messages.push({msg,type});},showToast:(msg,type)=>messages.push({msg,type})};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.api,ctx);if(p.asset)vm.runInContext(p.asset,ctx);
vm.runInContext('const customers=[{id:9,name:"KEEP"}],suppliers=[{id:9,name:"KEEP"}];const partyField='+JSON.stringify(p.mode)+';const partyLabel="往来单位";const quickSelectData={supplier:[{id:9,name:"KEEP"}],category:[{id:9,name:"KEEP"}],unit:[{id:9,name:"KEEP"}]};const quickSelectApiByType={supplier:"/api/suppliers",category:"/api/categories",unit:"/api/units"};',ctx);
vm.runInContext(p.source,ctx);
const target=vm.runInContext(p.page==='material'?'quickSelectData['+JSON.stringify(p.mode)+']':p.page==='in_order_add'?'suppliers':'customers',ctx);
const names=()=>Array.from(target,x=>x.name);
const run=()=>ctx[p.name](p.page==='material'?[p.mode]:{silent:p.action==='silent'});
async function finish(i,body,error){if(error==='network')pending[i].reject(new Error('offline'));else pending[i].resolve({ok:error!=='http',status:error==='http'?503:200,json:()=>Promise.resolve(body)});for(let j=0;j<5;j++)await new Promise(r=>setImmediate(r));}
(async()=>{
 run();assert.equal(calls[0].url,p.url);
 const row=name=>[{id:1,name}];
 if(p.action==='independent'){
  const others=['supplier','category','unit'].filter(x=>x!==p.mode);
  for(const type of others)ctx.refreshQuickSelectData([type]);
  run();await finish(3,row('NEW'));await finish(0,row('OLD'));
  for(let i=0;i<others.length;i++)await finish(i+1,row(others[i]));
  assert.deepEqual(names(),['NEW']);
  for(const type of others)assert.deepEqual(Array.from(vm.runInContext('quickSelectData.'+type,ctx),x=>x.name),[type],'separate cache arrays must not invalidate each other');
  return;
 }
 if(['order','latest_error','stale_error'].includes(p.action)){
  run();await finish(1,row('NEW'),p.action==='latest_error'?'http':null);await finish(0,row('OLD'),p.action==='stale_error'?'network':null);
  assert.deepEqual(names(),p.action==='latest_error'?['KEEP']:['NEW'],'obsolete responses must never replace the newest cache');
 }else{
  let data=p.action==='empty'?[]:row('NEW');
  if(p.action==='business')data={status:'error',msg:'failed'};
  if(p.action==='shape')data={items:row('NEW')};
  if(p.action==='invalid_row')data=[{id:1}];
  if(p.action==='duplicate')data=[{id:1,name:'ONE'},{id:1,name:'TWO'}];
  await finish(0,data,p.action);
  assert.deepEqual(names(),p.action==='empty'?[]:['success','silent'].includes(p.action)?['NEW']:['KEEP']);
 }
 assert.strictEqual(target,vm.runInContext(p.page==='material'?'quickSelectData['+JSON.stringify(p.mode)+']':p.page==='in_order_add'?'suppliers':'customers',ctx),'search closures retain the same array');
 const notified=['in_order_add','out_order_add'].includes(p.page)&&p.action!=='silent';
 const good=['success','empty','order','stale_error'].includes(p.action);
 assert.equal(messages.filter(x=>x.type==='success').length,notified&&good?1:0);
 assert.equal(messages.filter(x=>x.type==='danger').length,notified&&!good?1:0);
 assert(calls.every(x=>x.options.headers['X-Requested-With']==='XMLHttpRequest'),'real consumers must use the HTTP client');
 if(p.page==='material')for(const type of ['supplier','category','unit'].filter(x=>x!==p.mode))assert.deepEqual(Array.from(vm.runInContext('quickSelectData.'+type,ctx),x=>x.name),['KEEP']);
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""
    node = shutil.which('node')
    assert node, 'Node.js required for delayed HTTP cache regression'
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(
        page=page, name=name, mode=mode, url=url, action=action, source=function(source, name),
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        asset=asset.read_text(encoding='utf-8') if asset.exists() else '')),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mode,url', [('supplier', '/api/suppliers'), ('category', '/api/categories'), ('unit', '/api/units')])
def test_each_quick_cache_refresh_is_independent(mode, url):
    test_real_cache_consumer_keeps_latest_complete_valid_list('material', 'refreshQuickSelectData', mode, url, 'independent')


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'viewer'])
def test_array_helper_loads_once_with_version_after_http_client(role):
    from tests.test_shell_navigation_asset import render_shell
    html = render_shell(role)
    asset = '/static/js/list-cache.js?v=nav-test-v1'
    assert html.count(asset) == 1
    assert html.index('js/api.js') < html.index(asset)
    tag = next(t for t in re.findall(r'<script[^>]+>', html) if asset in t)
    assert not re.search(r'\b(async|defer|type)=?', tag)


def test_array_helper_response_has_versioned_cache_and_etag():
    import app as wms
    client = wms.app.test_client()
    response = client.get('/static/js/list-cache.js?v=fixture')
    assert response.status_code == 200
    assert response.data == (ROOT / 'app/static/js/list-cache.js').read_bytes()
    assert response.mimetype in {'application/javascript', 'text/javascript'}
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert client.get('/static/js/list-cache.js', headers={'If-None-Match':response.headers['ETag']}).status_code == 304
