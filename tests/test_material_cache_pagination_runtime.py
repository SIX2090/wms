"""Run real material refresh consumers with paginated and delayed HTTP replies."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['out_order_add', 'document_table_form', 'adjustment_add']


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('action', ['pages', 'empty', 'later_error', 'shape', 'changing', 'duplicates', 'order', 'latest_error', 'stale_error', 'busy', 'invalid_row', 'bad_array', 'http', 'business'])
def test_refresh_fetches_every_page_before_replacing_cache(page, action):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    asset = ROOT / 'app/static/js/material-cache.js'
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],messages=[],button={disabled:false,innerHTML:'刷新物料'};
const ctx={document:{querySelector:s=>s.startsWith('meta')?{content:'token'}:button},FormData:class{},URLSearchParams,
 fetch:(url,options)=>{calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve,reject}));},
 showToast:(message,type)=>messages.push({message,type}),notifyMaterialRefresh:(message,type,silent)=>{if(!silent)messages.push({message,type});}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('const materials=[{id:9999,code:"KEEP",name:"已选物料"}];',ctx);if(p.asset)vm.runInContext(p.asset,ctx);vm.runInContext(p.refresh,ctx);
const rows=(start,count)=>Array.from({length:count},(_,i)=>({id:start+i,code:'M'+(start+i),name:'料'+(start+i),unit:'个',stock:3}));
const codes=()=>Array.from(vm.runInContext('materials',ctx),x=>x.code);
async function finish(index,items,total=items.length,page=1,error=null){let data={status:'success',materials:items,total,page,per_page:2000,pages:Math.ceil(total/2000)};if(error==='business')data.status='error';pending[index].resolve({ok:error!=='http',status:error==='http'?503:200,json:()=>Promise.resolve(data)});for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));}
(async()=>{
 ctx.refreshMaterials();assert.equal(calls.length,1);
 if(['order','latest_error','stale_error','busy'].includes(p.action)){
  ctx.refreshMaterials();
  if(p.action==='busy'){await finish(0,rows(1,1));if(p.page==='out_order_add')assert(button.disabled,'old finally must not unlock an active newer refresh');assert.deepEqual(codes(),['KEEP']);await finish(1,rows(2005,1));}
  else {await finish(1,rows(2005,1),1,1,p.action==='latest_error'?'http':null);await finish(0,rows(1,1),1,1,p.action==='stale_error'?'http':null);}
  assert.deepEqual(codes(),p.action==='latest_error'?['KEEP']:['M2005']);assert.equal(messages.filter(x=>x.type==='success').length,p.action==='latest_error'?0:1);assert.equal(messages.filter(x=>x.type==='danger').length,p.action==='latest_error'?1:0);if(p.page==='out_order_add')assert(!button.disabled);return;
 }
 if(p.action==='empty'){await finish(0,[],0);assert.deepEqual(codes(),[]);return;}
 if(['invalid_row','bad_array'].includes(p.action)){await finish(0,p.action==='invalid_row'?[{id:1,code:'BROKEN'}]:{},1);assert.deepEqual(codes(),['KEEP']);assert(!messages.some(x=>x.type==='success'));return;}
 if(['http','business','shape'].includes(p.action)){
  await finish(0,rows(1,1),1,p.action==='shape'?2:1,p.action==='shape'?null:p.action);assert.deepEqual(codes(),['KEEP']);assert(!messages.some(x=>x.type==='success'));if(p.page==='out_order_add')assert(!button.disabled);return;
 }
 await finish(0,rows(1,2000),2005);
 assert.deepEqual(codes(),['KEEP'],'first page must not replace the complete old cache');assert.equal(calls.length,2,'material 2001+ must be loaded');
 for(let i=0;i<2;i++){const u=new URL(calls[i].url,'https://fixture');assert.equal(u.searchParams.get('page'),String(i+1));assert.equal(u.searchParams.get('per_page'),'2000');assert.equal(calls[i].options.headers['X-Requested-With'],'XMLHttpRequest');}
 await finish(1,rows(p.action==='duplicates'?1:2001,5),p.action==='changing'?2006:2005,2,p.action==='later_error'?'http':null);
 if(p.action==='pages'){assert.equal(codes().length,2005);assert.equal(codes().at(-1),'M2005');assert.equal(messages.filter(x=>x.type==='success').length,1);}
 else {assert.deepEqual(codes(),['KEEP'],'failed/inconsistent later pages must preserve all existing options');assert(!messages.some(x=>x.type==='success'));}
 if(p.page==='out_order_add')assert(!button.disabled);
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""
    binary = shutil.which('node')
    assert binary, 'Node.js is required for material cache runtime tests'
    result = subprocess.run([binary, '--max-old-space-size=64', '-e', program],
                            input=json.dumps(dict(page=page, action=action, refresh=function(source, 'refreshMaterials'),
                                                  api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
                                                  asset=asset.read_text(encoding='utf-8') if asset.exists() else '')),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('page', PAGES)
def test_asset_is_loaded_once_before_page_script_with_cache_version(page):
    from jinja2 import Environment
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    tag = re.findall(r'<script src="[^\n]+material-cache\.js[^\n]+</script>', source)
    assert len(tag) == 1
    rendered = Environment(autoescape=True).from_string(tag[0]).render(config={'STATIC_VERSION':'fixture-v1'}, url_for=lambda endpoint, **kw:'/static/'+kw['filename'])
    assert 'src="/static/js/material-cache.js?v=fixture-v1"' in rendered
    assert source.index('material-cache.js') < source.index('<script>', source.index('{% block extra_js %}'))
    assert not re.search(r'\b(async|defer)=?', rendered)


def test_cache_asset_supports_browser_cache_and_etag():
    import app as wms
    client = wms.app.test_client()
    response = client.get('/static/js/material-cache.js?v=fixture')
    assert response.status_code == 200
    assert response.data == (ROOT / 'app/static/js/material-cache.js').read_bytes()
    assert response.mimetype in {'text/javascript','application/javascript'}
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert client.get('/static/js/material-cache.js', headers={'If-None-Match':response.headers['ETag']}).status_code == 304


def test_real_material_endpoint_returns_both_pages_and_excludes_inactive(monkeypatch):
    import app as wms
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        assert str(wms.db.engine.url) == 'sqlite:///:memory:'
        wms.db.drop_all()
        wms.db.create_all()
        try:
            user = wms.User(username='cache-fixture', password_hash='fixture-only', role='warehouse', status='active')
            unit = wms.Unit(code='PCS', name='个')
            wms.db.session.add_all([user, unit])
            wms.db.session.flush()
            wms.db.session.bulk_insert_mappings(wms.Material, [dict(code=f'M{i:04}', name=f'物料{i}', unit_id=unit.id, stock=0, price=0, status='active') for i in range(1, 2006)])
            wms.db.session.add(wms.Material(code='OFF', name='停用物料', unit_id=unit.id, status='inactive'))
            wms.db.session.commit()
            client = wms.app.test_client()
            with client.session_transaction() as session:
                session.update(_user_id=str(user.id), _fresh=True)
            pages = [client.get('/material/api/all', query_string={'page':page, 'per_page':2000}).get_json() for page in [1, 2]]
            for page, response in enumerate(pages, 1):
                assert response['status'] == 'success'
                assert (response['total'], response['pages'], response['per_page'], response['page']) == (2005, 2, 2000, page)
            assert [len(page['materials']) for page in pages] == [2000, 5]
            rows = [row for page in pages for row in page['materials']]
            assert len({row['id'] for row in rows}) == 2005
            assert rows[-1]['code'] == 'M2005'
            assert all(row['code'] != 'OFF' for row in rows)
        finally:
            wms.db.session.remove()
            wms.db.drop_all()
