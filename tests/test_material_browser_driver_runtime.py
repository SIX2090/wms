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


@pytest.mark.parametrize('mode', ['success', 'response_first', 'click_first'])
def test_browser_wait_and_click_failures_are_both_observed(mode):
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),mode=JSON.parse(process.argv[2]);
let orphaned=[],clicks=0;process.on('unhandledRejection',error=>orphaned.push(error.message));
const good={url:()=> 'http://127.0.0.1:31000/in_order/add?embedded=1',request:()=>({method:()=> 'POST'})};
const page={waitForResponse(predicate){
 assert.equal(predicate(good),true);
 assert.equal(predicate({...good,request:()=>({method:()=> 'GET'})}),false);
 assert.equal(predicate({...good,url:()=> 'http://127.0.0.1:31000/out_order/add'}),false);
 if(mode==='success')return Promise.resolve(good);
 return new Promise((resolve,reject)=>setTimeout(()=>reject(Error('response timeout')),mode==='click_first'?30:0));
}};
function trigger(){clicks++;if(mode==='click_first')return Promise.reject(Error('click failed'));
 return new Promise(resolve=>setTimeout(resolve,mode==='response_first'?50:0));}
const ctx={Promise,URL};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 let result,error;try{result=await ctx.submitAndObserve(page,'/in_order/add',trigger);}catch(e){error=e;}
 if(mode==='success')assert.equal(result,good);
 else assert.equal(error.message,mode==='click_first'?'click failed':'response timeout');
 await new Promise(resolve=>setTimeout(resolve,70));assert.deepEqual(orphaned,[]);assert.equal(clicks,1);
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
