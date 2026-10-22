"""Execute each page request expression with the production API, including failures."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / 'app/static/js/api.js'


def closing(source, start):
    depth = 0
    quote = None
    escaped = False
    for i in range(start, len(source)):
        c = source[i]
        if quote:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == quote:
                quote = None
            continue
        if c in "\"'`":
            quote = c
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                return i + 1
    raise AssertionError('unclosed request')


def requests():
    calls = []
    for page in ['material', 'mobile_scan']:
        source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
        for match in re.finditer(r'(?m)^\s*(?:return\s+)?((?:fetch|csrfFetch|WMS\.api\.(?:getRaw|postRaw))\s*\()', source):
            start = match.start(1)
            end = closing(source, source.index('(', start))
            expr = re.sub(r'{{.*?}}', '/fixture-endpoint', source[start:end])
            calls.append(pytest.param(page, expr, id=page + '-' + str(source.count('\n', 0, start) + 1)))
    return calls


def node_run(program, payload):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('page,expression', requests())
@pytest.mark.parametrize('scenario', ['success', 'multiple', 'array', 'http', 'html', 'expired401', 'expired419', 'network'])
def test_every_migrated_request_preserves_raw_data_and_errors(page, expression, scenario):
    node_run(r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);let sent=[],expired=0;
class FormData{append(){}}
const formData=new FormData(),body=p.scenario==='array'?[{id:7}]:{status:p.scenario==='multiple'?'multiple':'success',msg:'literal failure',data:{id:7,matches:[{code:'M1'}]},page:2,total_pages:4,warnings:['warning']};
const controller=new AbortController();
const ctx={FormData,Headers,AbortController,controller,document:{querySelector:()=>({content:'fixture-csrf'})},location:{href:'original'},confirm:()=>{expired++;return true;},setTimeout(){},
 status:'inactive',id:7,currentTemplateId:7,templateId:7,type:'unit',quickSelectApiByType:{unit:'/fixture/units'},lookupUrl:'/fixture/lookup?warehouse=A',undo:{checkId:7},mode:'in',lines:[{material_code:'M1',quantity:2}],warehouseInput:{value:'A'},remarkInput:{value:'note'},selectedMaterial:{id:7},wh:'A',cid:7,url:'/fixture/list?page=1',qs:'&warehouse=A',formData,dbData:formData,payload:{code:'M1',quantity:2},candidate:{image_url:'/fixture/image.jpg'},
 csrfHeaders:x=>x||{},tokenHeader:()=>({}),
 fetch:(url,options={})=>{sent.push({url,options});return p.scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:!['http','html','expired401','expired419'].includes(p.scenario),status:p.scenario==='http'?400:p.scenario==='html'?503:p.scenario==='expired401'?401:p.scenario==='expired419'?419:200,json:()=>p.scenario==='html'?Promise.reject(SyntaxError('HTML response')):Promise.resolve(body)});}};
ctx.window=ctx;ctx.csrfFetch=(u,o)=>ctx.fetch(u,o);vm.createContext(ctx);vm.runInContext(p.api,ctx);
(async()=>{let result,error;try{result=await vm.runInContext('(function(){return '+p.expression+';}).call({action:"/fixture/import"})',ctx);}catch(e){error=e;}
assert.equal(sent.length,1);const req=sent[0],headers=new Headers(req.options.headers);assert.equal(req.options.credentials,'same-origin');assert.equal(headers.get('X-CSRFToken'),'fixture-csrf');assert.equal(headers.get('X-Requested-With'),'XMLHttpRequest');
const post=/postRaw|csrfFetch|method:\s*['"]POST/.test(p.expression);assert.equal(req.options.method,post?'POST':'GET');
if(post&&/formData|dbData/.test(p.expression)){assert.equal(req.options.body,formData);assert.equal(headers.has('Content-Type'),false,'browser owns multipart boundary');}
else if(post&&req.options.body!==undefined){assert.equal(typeof JSON.parse(req.options.body),'object','never double stringify JSON');assert.equal(headers.get('Content-Type'),'application/json');}
if(p.expression.includes('controller.signal'))assert.equal(req.options.signal,controller.signal,'preserve recognition timeout');
if(['success','multiple','array'].includes(p.scenario)){assert.equal(error,undefined);assert.deepEqual(result,body,'preserve root envelope and pagination');}
else {assert(error,'errors must reject');if(p.scenario==='network')assert.equal(error.message,'offline');else if(p.scenario==='http'){assert.equal(error.status,400);assert.equal(error.message,'literal failure');assert.deepEqual(error.data,body);}else if(p.scenario==='html'){assert.equal(error.status,503);assert.equal(error.code,'HTTP_ERROR');assert(!error.message.includes('HTML response'));}else{assert.equal(error.code,'SESSION_EXPIRED');assert.equal(expired,1);assert.equal(ctx.location.href,'/login');}}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
''', dict(expression=expression, scenario=scenario, api=API.read_text(encoding='utf-8')))


def test_api_preserves_abort_controller_and_multipart_body():
    node_run(r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);class FormData{}
let request;const ctx={FormData,document:{querySelector:()=>({content:'csrf'})},fetch:(u,o)=>{request=o;return new Promise((resolve,reject)=>o.signal?.addEventListener('abort',()=>reject(Object.assign(Error('timeout'),{name:'AbortError'}))));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);
(async()=>{const c=new AbortController(),data=new FormData();const pending=ctx.WMS.api.postRaw('/recognize',data,{signal:c.signal});assert.equal(request.signal,c.signal);assert.equal(request.body,data);assert(!new Headers(request.headers).has('Content-Type'));c.abort();await assert.rejects(pending,e=>e.name==='AbortError');})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
''', {'api': API.read_text(encoding='utf-8')})


@pytest.mark.parametrize('page', ['material', 'mobile_scan'])
def test_pages_use_shared_transport_for_all_legacy_requests(page):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    scripts = '\n'.join(re.findall(r'<script[^>]*>(.*?)</script>', source, re.S))
    scripts = re.sub(r'//[^\n]*|/\*.*?\*/', '', scripts, flags=re.S)
    assert not re.search(r'(?<![\w.])(?:fetch|csrfFetch)\s*\(', scripts)


@pytest.mark.parametrize('form_id', ['addForm', 'editForm'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'html', 'expired', 'network'])
def test_material_forms_keep_multipart_and_failure_feedback(form_id, scenario):
    source = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    marker = source.index(form_id + ".addEventListener('submit'")
    end = closing(source, source.index('(', marker))
    callback = source[source.index('function(e)', marker):end - 1]
    callback = re.sub(r'{{.*?}}', '/material/add', callback)
    node_run(r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);let sent=[],messages=[],timers=[],hidden=0;
class FormData{constructor(form){this.owner=form.id;}}
const fields={edit_id:{value:'7'},edit_code:{value:'M1',getAttribute:()=> 'M1'},edit_name:{value:'Fixture',getAttribute:()=> 'Fixture'}};
const ctx={document:{getElementById:id=>fields[id]||null,querySelector:()=>({content:'fixture-csrf'})},FormData,Headers,commitQuickSelects(){},showToast:(m,t)=>messages.push({m,t}),setTimeout:fn=>timers.push(fn),confirm:()=>true,location:{href:'original'},bootstrap:{Modal:{getInstance:()=>({hide(){hidden++;}})}},
fetch:(u,o)=>{sent.push({u,o});return p.scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:!['http','html','expired'].includes(p.scenario),status:p.scenario==='http'?400:p.scenario==='html'?503:p.scenario==='expired'?401:200,json:()=>p.scenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({status:['http','business'].includes(p.scenario)?'error':'success',msg:['http','business'].includes(p.scenario)?'fixture failure':'saved'})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var handler='+p.callback+';',ctx);
(async()=>{ctx.handler.call({id:p.form},{preventDefault(){}});await new Promise(r=>setImmediate(r));assert.equal(sent.length,1);assert.equal(sent[0].u,p.form==='addForm'?'/material/add':'/material/edit/7');assert(sent[0].o.body instanceof FormData);assert.equal(sent[0].o.body.owner,p.form);const h=new Headers(sent[0].o.headers);assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert(!h.has('Content-Type'));
if(p.scenario==='success'){assert(timers.length>0);assert(!messages.some(x=>x.t==='danger'));}
else {assert.equal(timers.length,0,'failure must not refresh and discard input');assert.equal(hidden,0,'failure keeps edit modal open');assert(messages.some(x=>x.t==='danger'));const text=messages.map(x=>x.m).join(' ');if(['http','business'].includes(p.scenario))assert(text.includes('fixture failure'));else if(p.scenario==='network')assert(text.includes('offline'));else if(p.scenario==='html')assert(text.includes('503')&&!text.includes('HTML'));else assert(text.includes('登录已过期'));}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
''', dict(callback=callback, form=form_id, scenario=scenario, api=API.read_text(encoding='utf-8')))


@pytest.mark.parametrize('scenario', ['http', 'html', 'network'])
def test_material_image_errors_are_visible_literal_text(scenario):
    source = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    start = source.index('window.loadEditMaterialImages = function(id)')
    callback = source[source.index('function(id)', start):source.index('\n    };', start) + 6]
    node_run(r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);const grid={innerHTML:'',textContent:''},literal='<img src=x onerror=alert(1)> A&B';
const ctx={FormData:class{},document:{getElementById:()=>grid,querySelector:()=>null},fetch:()=>p.scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:false,status:p.scenario==='html'?503:400,json:()=>p.scenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({msg:literal})})};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var handler='+p.callback+';',ctx);
(async()=>{ctx.handler(7);await new Promise(r=>setImmediate(r));assert(grid.textContent.startsWith('图片加载失败：'));assert.equal(grid.innerHTML,'','untrusted error text must never enter innerHTML');assert(grid.textContent.includes(p.scenario==='http'?literal:p.scenario==='html'?'503':'offline'));})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
''', dict(callback=callback, scenario=scenario, api=API.read_text(encoding='utf-8')))


@pytest.mark.parametrize('kind', ['in', 'out'])
def test_pending_pages_keep_warehouse_and_pagination_envelope(kind):
    source = (ROOT / 'app/templates/mobile_scan.html').read_text(encoding='utf-8')
    start = source.index('    function fetchPendingPage(')
    function = source[start:source.index('\n    }', start) + 6]
    node_run(r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);let url;const body={status:'success',data:{items:[{id:7}],page:3,total_pages:5,total:81}};
const ctx={FormData:class{},document:{querySelector:()=>null},confirmWarehouseSelect:{value:'Warehouse A&B'},fetch:u=>{url=u;return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(body)});}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
(async()=>{const result=await ctx.fetchPendingPage(p.kind,3);const parsed=new URL(url,'http://fixture');assert.equal(parsed.pathname,'/api/mobile/'+p.kind+'_order/list');assert.equal(parsed.searchParams.get('status'),'pending');assert.equal(parsed.searchParams.get('page'),'3');assert.equal(parsed.searchParams.get('warehouse'),'Warehouse A&B');assert.deepEqual(result,body);})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
''', dict(source=function, kind=kind, api=API.read_text(encoding='utf-8')))
