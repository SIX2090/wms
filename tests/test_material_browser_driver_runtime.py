"""CI browser driver must reject completion and contain concurrent wait failures."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def helper(name):
    source = (ROOT / 'tests/material_browser_check.cjs').read_text(encoding='utf-8')
    return re.search(r'async function ' + name + r'\([^\n]*\) \{.*?^\}', source, re.S | re.M).group()


def execute(program, name, payload):
    result = subprocess.run([shutil.which('node'), '-e', program, helper(name), json.dumps(payload)],
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mode', ['success', 'response_first', 'click_first', 'navigation_after_response', 'upstream_failure'])
def test_browser_wait_and_click_failures_are_both_observed(mode):
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),mode=JSON.parse(process.argv[2]);
let orphaned=[],clicks=0,navigated=false,reads=0,upstreamReads=0,forwarded=0,unroutes=0,handler,waitingResolve,waitingReject;process.on('unhandledRejection',error=>orphaned.push(error.message));
const good={url:()=> 'http://127.0.0.1:31000/in_order/add?embedded=1',request:()=>({method:()=> 'POST'}),status:()=>200,
 async text(){assert.equal(navigated,false,'Response body discarded after navigation');reads++;await new Promise(resolve=>setTimeout(resolve,5));return '{"status":"success","id":1}';}};
const upstream={status:()=>200,text:async()=>{upstreamReads++;return '{"status":"success","id":1}';},dispose:async()=>{}};
const page={url:()=> 'http://127.0.0.1:31000/form',isClosed:()=>false,
 async route(matches,fn){assert(matches(new URL('http://127.0.0.1:31000/in_order/add')));assert(!matches(new URL('http://other.invalid/in_order/add')));handler=fn;},
 async unroute(matches,fn){assert.equal(fn,handler);unroutes++;handler=null;},
 waitForResponse(predicate){
 assert.equal(predicate(good),true);
 assert.equal(predicate({...good,request:()=>({method:()=> 'GET'})}),false);
 assert.equal(predicate({...good,url:()=> 'http://127.0.0.1:31000/out_order/add'}),false);
 return new Promise((resolve,reject)=>{waitingResolve=resolve;waitingReject=reject;
  if(mode==='response_first'||mode==='click_first')setTimeout(()=>reject(Error('response timeout')),mode==='click_first'?30:0);
 });
}};
function trigger(){clicks++;if(mode==='click_first')return Promise.reject(Error('click failed'));
 return new Promise(resolve=>{
  if(mode!=='response_first'){
   if(handler)handler({request:()=>good.request(),fetch:async options=>{assert.deepEqual({...options},{maxRedirects:0,maxRetries:0});forwarded++;if(mode==='upstream_failure')throw Error('upstream failed');return upstream;},
    fulfill:async options=>{assert.equal(options.response,upstream);waitingResolve(good);},abort:async()=>waitingReject(Error('aborted'))});
   else waitingResolve(good);
  }
  setTimeout(()=>{if(mode==='navigation_after_response')navigated=true;resolve();},mode==='response_first'?50:mode==='navigation_after_response'?20:0);
 });}
const ctx={Promise,URL,check:assert};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 let result,error;try{result=await ctx.submitAndObserve(page,'/in_order/add',trigger);
  if(typeof result.text==='function')result={status:result.status(),text:await result.text()};
 }catch(e){error=e;}
 if(mode==='success'||mode==='navigation_after_response'){
  assert.equal(error,undefined);assert.deepEqual({...result},{status:200,text:'{"status":"success","id":1}'});
  assert.equal(upstreamReads+reads,1);if(upstreamReads)assert.equal(forwarded,1);
 }
 else assert.equal(error.message,mode==='click_first'?'click failed':mode==='upstream_failure'?'upstream failed':'response timeout');
 await new Promise(resolve=>setTimeout(resolve,70));assert.deepEqual(orphaned,[]);assert.equal(clicks,1);
 if(upstreamReads||mode==='upstream_failure')assert.equal(unroutes,1);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    execute(program, 'submitAndObserve', mode)


@pytest.mark.parametrize('mode', ['ordinary', 'complete', 'proxy', 'missing', 'ambiguous'])
def test_browser_selects_visible_save_and_refuses_completion(mode):
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),mode=JSON.parse(process.argv[2]);
const button={count:async()=>mode==='missing'?0:mode==='ambiguous'?2:1,
 getAttribute:async name=>(mode==='complete'&&name==='data-wms-save-complete')||
                         (mode==='proxy'&&name==='data-wms-save-complete-proxy')?'':null};
const page={getByRole(role,options){assert.equal(role,'button');assert(options.name.test(' 保存'));
 assert(!options.name.test('保存并新增'));assert(!options.name.test('保存草稿'));return button;}};
const ctx={check:assert};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 if(mode==='ordinary')assert.equal(await ctx.ordinarySaveControl(page),button);
 else await assert.rejects(ctx.ordinarySaveControl(page),mode==='complete'||mode==='proxy'?/save-and-complete/:/exactly one/);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    execute(program, 'ordinarySaveControl', mode)
