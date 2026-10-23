"""One session-expiry prompt across the real base interceptor and shared API."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]

PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const prompts=[],timers=[],calls=[];let jsonReads=0;
const ctx={Headers,FormData,document:{querySelector:()=>({content:'session-token'})},location:{origin:'http://fixture',href:'/original'},confirm:message=>{prompts.push(message);return p.accept;},setTimeout:(fn,delay)=>timers.push({fn,delay}),wmsGlobalErrorToast:()=>assert.fail('session response must not be a server/network error'),fetch:(url,options)=>{calls.push({url,options});const status=Number(url.split('/').at(-1));return Promise.resolve({status,ok:false,json(){jsonReads++;return Promise.resolve({status:'error',msg:'expired'});}});}};ctx.window=ctx;
if(p.mode==='preset')ctx.__wmsSessionExpiredShown=true;
vm.createContext(ctx);
if(['combined','preset'].includes(p.mode))vm.runInContext(p.base,ctx);
vm.runInContext(p.api,ctx);
async function api(method,status){try{await ctx.WMS.api[method]('/session/'+status,{fixture:true});assert.fail('expired API must reject');}catch(error){assert.equal(error.code,'SESSION_EXPIRED');assert.equal(error.status,status);}}
async function group(){const other=p.status===401?419:401;const work=[api('postRaw',p.status),api('post',other),api('postResponse',p.status)];if(p.mode!=='standalone')work.push(ctx.fetch('/session/'+other).then(response=>assert.equal(response.status,other)));await Promise.all(work);await new Promise(r=>setImmediate(r));assert.equal(jsonReads,0,'session handlers must not consume JSON');}
(async()=>{
 if(p.mode==='latebase'){await api('postRaw',p.status);assert.equal(prompts.length,1);assert.equal(ctx.__wmsSessionExpiredShown,true);vm.runInContext(p.base,ctx);}
 await group();
 const expected=p.mode==='preset'?0:1;assert.equal(prompts.length,expected,'base and API must share one session prompt');assert.equal(timers.length,p.mode==='preset'||p.accept?0:1,'cancel schedules exactly one reset');assert.equal(ctx.__wmsSessionExpiredShown,true);assert.equal(ctx.location.href,p.accept?'/login':'/original');
 await group();assert.equal(prompts.length,expected,'same-tick mixed requests must remain suppressed');
 if(!p.accept&&p.mode!=='preset'){assert.equal(timers[0].delay,5000);timers[0].fn();assert.equal(ctx.__wmsSessionExpiredShown,false);await group();assert.equal(prompts.length,2,'cancel permits another prompt after five seconds');assert.equal(timers.length,2);assert.equal(ctx.__wmsSessionExpiredShown,true);}
 for(const call of calls){assert.equal(new Headers(call.options.headers).get('X-Requested-With'),'XMLHttpRequest');if(call.options.method==='POST')assert.equal(new Headers(call.options.headers).get('X-CSRFToken'),'session-token');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(mode,status,accept):
    node=shutil.which('node');assert node,'Node required for real session handlers'
    base=(ROOT/'app/templates/base.html').read_text(encoding='utf-8')
    start=base.index('    (function() {\n        var csrfToken =')
    end=base.index('    })();',start)+len('    })();')
    payload=dict(mode=mode,status=status,accept=accept,base=base[start:end],api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('mode',['combined','standalone'])
@pytest.mark.parametrize('status',[401,419])
@pytest.mark.parametrize('accept',[False,True])
def test_real_interceptor_and_api_share_expiry_prompt_and_cancel_reset(mode,status,accept):
    run(mode,status,accept)


@pytest.mark.parametrize('status',[401,419])
def test_api_first_then_base_preserves_existing_prompt_flag(status):
    run('latebase',status,False)


@pytest.mark.parametrize('status',[401,419])
def test_api_loading_does_not_reset_already_visible_base_prompt(status):
    run('preset',status,False)
