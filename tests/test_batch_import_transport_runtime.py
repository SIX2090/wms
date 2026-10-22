"""Execute batch-import callbacks with the production HTTP client and deferred responses."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function_at(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError('Unclosed function')


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let ctx,calls=[],pending=[],sessions=0,failureHtml='';
class Node {
 constructor(){this.disabled=false;this._html='';this.textContent='';this.buttons=[];this.classes=new Set(['d-none']);this.classList={add:x=>this.classes.add(x),remove:x=>this.classes.delete(x),contains:x=>this.classes.has(x)};}
 set innerHTML(value){this._html=value;this.buttons=[];for(const match of value.matchAll(/<button\b[^>]*onclick="(\w+)\(\)"[^>]*>/g)){const button=new Node();button.click=()=>{if(!button.disabled)ctx[match[1]]();};this.buttons.push(button);}}
 get innerHTML(){return this._html;}
 querySelectorAll(selector){assert.equal(selector,'button');return this.buttons;}
}
const result=new Node(),preview=new Node(),pre=new Node(),submit=new Node(),cancel=new Node();submit.innerHTML='Original submit';
const fileA={name:'same.xlsx',size:10,lastModified:1},fileB={name:'same.xlsx',size:10,lastModified:1};
const input={type:'file',files:[fileA],disabled:false,closest:s=>s==='#openingStockImportForm'?form:null};
const form={id:p.action==='import'?'materialImportForm':'openingStockImportForm',dataset:{url:p.action==='import'?'/material/import':'/opening_stock/import'},handlers:{},parentElement:{querySelector:()=>result},querySelector:s=>s.includes('file')?input:submit,addEventListener:(name,fn)=>form.handlers[name]=fn,requestSubmit:()=>{if(!input.files.length)return;form.handlers.submit({preventDefault(){}});},dispatchEvent:()=>form.handlers.submit({preventDefault(){}})};
class FD {constructor(f){this.map=new Map([['csrf_token','form-token']]);if(f&&!input.disabled&&input.files[0])this.map.set('file',input.files[0]);}set(k,v){this.map.set(k,v);}get(k){return this.map.get(k);}}
const nodes={openingStockImportForm:form,openingStockPreview:preview,openingStockPrecheckBtn:pre,openingStockConfirmBtn:submit,openingStockCancelBtn:cancel};
const events={};
const document={querySelectorAll:s=>{assert.equal(s,'.import-form');return [form];},getElementById:id=>nodes[id],querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null,addEventListener:(name,fn)=>events[name]=fn};
function success(file=fileA){return {status:'success',msg:'导入完成',rows:[{action:'import',material_code:file===fileA?'A':'B',quantity:1,price:2}],imported:1,skipped:0,fresh_count:1,total_rows:1,detail_url:'/opening_stock/7',doc_no:'DOC-7',warnings:'提示',errors:['逐行提示']};}
const evil='<img src=x onerror="alert(1)"> & 错误';
function response(scenario='success',body=success()) {const status={http:400,html:502,unauthorized:401,expired:419}[scenario]||200;return {ok:status===200,status,json:()=>['html','malformed'].includes(scenario)?Promise.reject(new SyntaxError('Invalid JSON')):Promise.resolve(scenario==='null'?null:scenario==='business'||scenario==='http'?{status:'error',msg:evil}:body)};}
function fetch(url,options){calls.push({url,options});if(p.deferred)return new Promise((resolve,reject)=>pending.push({resolve,reject}));if(p.scenario==='network')return Promise.reject(new Error(evil));return Promise.resolve(response(p.scenario));}
ctx={document,FormData:FD,fetch,Promise,URL,Headers,Number,Event:class{},location:{origin:'http://fixture.test',href:'http://fixture.test/batch_import'},setTimeout:()=>0,confirm:()=>{sessions++;return false;}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
const change=()=>events.change({target:input});
const resolve=async(index,scenario='success',body=success())=>{if(scenario==='network')pending[index].reject(new Error(evil));else pending[index].resolve(response(scenario,body));await settle();};
const expectPayload=(index,dry,file=fileA)=>{const call=calls[index];assert.equal(call.options.method,'POST');assert.equal(call.options.headers['X-CSRFToken'],'fixture-token');assert.equal(call.options.headers['X-Requested-With'],'XMLHttpRequest');assert(!('Content-Type' in call.options.headers));assert(call.options.body instanceof FD);assert.equal(call.options.body.get('file'),file);assert.equal(call.options.body.get('dry_run'),dry?'true':undefined);assert.equal(call.options.body.get('csrf_token'),'form-token');};
(async()=>{
 if(p.action==='import'||p.action==='precheck'){
  if(p.scenario==='empty')input.files=[];
  if(p.action==='import')form.requestSubmit();else ctx.precheckOpeningStock();await settle();
  if(p.scenario==='empty'){assert.equal(calls.length,0);return;}
  assert.equal(calls.length,1);expectPayload(0,p.action==='precheck');assert.equal(submit.disabled,false);assert.equal(pre.disabled,false);
  if(p.scenario==='success'){if(p.action==='precheck'){assert.equal(ctx.openingStockPrechecked,true);assert.equal(preview.buttons.length,2);assert.equal(calls.length,1,'precheck never automatically imports');}else{assert(result.innerHTML.includes('DOC-7'));assert(result.innerHTML.includes('target="_blank"'));}}
  else {assert(result.innerHTML.includes('alert-danger'));assert.equal(preview.buttons.length,0);assert.equal(ctx.openingStockPrechecked,false);if(['unauthorized','expired'].includes(p.scenario))assert.equal(sessions,1);}
 } else if(p.action==='stale-change'){
  ctx.precheckOpeningStock();input.files=[fileB];change();assert.equal(ctx.openingStockPrechecked,false);assert.equal(pre.disabled,false);await resolve(0,p.scenario);assert.equal(preview.buttons.length,0);assert.equal(ctx.openingStockPrechecked,false);ctx.confirmOpeningStockImport();assert.equal(calls.length,1);ctx.precheckOpeningStock();await resolve(1,'success',success(fileB));assert(preview.innerHTML.includes('<code>B</code>'));preview.buttons[0].click();assert.equal(calls.length,3);expectPayload(2,false,fileB);await resolve(2);
 } else if(p.action==='stale-order'){
  ctx.precheckOpeningStock();input.files=[fileB];change();ctx.precheckOpeningStock();await resolve(1,'success',success(fileB));const html=preview.innerHTML;await resolve(0,p.scenario);assert.equal(preview.innerHTML,html);assert.equal(ctx.openingStockPrecheckedFile,fileB);assert.equal(ctx.openingStockPrechecked,true);
 } else if(p.action==='cancel'){
  ctx.precheckOpeningStock();ctx.cancelOpeningStockPrecheck();await resolve(0,p.scenario);assert.equal(preview.buttons.length,0);assert.equal(ctx.openingStockPrechecked,false);assert.equal(pre.disabled,false);assert(pre.innerHTML.includes('预检（不导入）'));ctx.confirmOpeningStockImport();assert.equal(calls.length,1);
 } else if(p.action==='identity'){
  ctx.precheckOpeningStock();await resolve(0);input.files=[fileB];ctx.confirmOpeningStockImport();assert.equal(calls.length,1,'same filename with another File must be prechecked again');assert.equal(ctx.openingStockPrechecked,false);
 } else if(p.action==='confirm'){
  ctx.precheckOpeningStock();await resolve(0);const button=preview.buttons[0];button.click();button.click();ctx.confirmOpeningStockImport();form.requestSubmit();ctx.precheckOpeningStock();ctx.cancelOpeningStockPrecheck();assert.equal(preview.buttons.length,2);assert.equal(calls.length,2);assert.equal(button.disabled,true);assert.equal(input.disabled,true);expectPayload(1,false);await resolve(1,p.scenario);assert.equal(input.disabled,false);assert.equal(submit.disabled,false);assert.equal(pre.disabled,false);assert.equal(form.dataset.importBusy,'');
  if(p.scenario==='success'){assert.equal(preview.buttons.length,0);assert.equal(ctx.openingStockPrechecked,false);assert(result.innerHTML.includes('DOC-7'));ctx.confirmOpeningStockImport();assert.equal(calls.length,2);}
  else {assert(result.innerHTML.includes('alert-danger'));failureHtml=result.innerHTML;assert.equal(ctx.openingStockPrechecked,true);assert.equal(button.disabled,false);button.click();assert.equal(calls.length,3);await resolve(2);assert.equal(ctx.openingStockPrechecked,false);}
 } else if(p.action==='truncated'){
  const body=success();body.rows=Array.from({length:500},()=>({action:p.scenario==='first500bad'?'skip':'import',reason:'坏行',quantity:1,price:2}));body.imported=p.scenario==='first500bad'?1:650;body.skipped=p.scenario==='first500bad'?500:0;body.total_rows=p.scenario==='first500bad'?501:650;body.truncated=true;ctx.precheckOpeningStock();await resolve(0,'success',body);assert.equal(preview.buttons.length,2);assert(preview.innerHTML.includes('确认导入这 '+body.imported+' 行'));assert(preview.innerHTML.includes('确认导入将处理整个文件'));assert.equal(ctx.openingStockPrechecked,true);preview.buttons[0].click();assert.equal(calls.length,2);expectPayload(1,false);await resolve(1);
 } else throw new Error('Unknown action '+p.action);
 process.stdout.write(JSON.stringify({html:failureHtml||result.innerHTML,preview:preview.innerHTML}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(action, scenario='success'):
    node = shutil.which('node')
    assert node, 'Node.js is required for actual callback regression coverage'
    template = (ROOT / 'app/templates/batch_import.html').read_text(encoding='utf-8')
    script = re.search(r'{% block extra_js %}\s*<script>(.*?)</script>', template, re.S)
    assert script
    payload = dict(action=action, scenario=scenario,
                   deferred=action not in ('import', 'precheck'), script=script.group(1),
                   helper=function_at((ROOT / 'app/static/js/app.js').read_text(encoding='utf-8'), 'function escapeHtml('),
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    completed = subprocess.run([node, '--max-old-space-size=64', '-e', PROGRAM], input=json.dumps(payload),
                               capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout) if completed.stdout else {}


SCENARIOS = ['success', 'business', 'http', 'html', 'malformed', 'null', 'unauthorized', 'expired', 'network']


@pytest.mark.parametrize('action', ['import', 'precheck', 'confirm'])
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_actual_callbacks_transport_feedback_payload_and_retry(action, scenario):
    result = run(action, scenario)
    if scenario in ('business', 'http', 'network'):
        parser = HTMLParser()
        tags = []
        parser.handle_starttag = lambda tag, attrs: tags.append(tag)
        parser.feed(result['html'])
        assert 'img' not in tags
        assert '&lt;img' in result['html']


@pytest.mark.parametrize('action', ['stale-change', 'stale-order', 'cancel'])
@pytest.mark.parametrize('scenario', ['success', 'http', 'network'])
def test_pending_precheck_never_revives_changed_or_cancelled_state(action, scenario):
    run(action, scenario)


def test_precheck_is_bound_to_file_identity_even_with_same_file_metadata():
    run('identity')


@pytest.mark.parametrize('scenario', ['first500bad', 'total650'])
def test_truncated_preview_uses_whole_file_import_count_for_manual_confirmation(scenario):
    run('truncated', scenario)


def test_no_file_precheck_does_not_request():
    run('precheck', 'empty')
