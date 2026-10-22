"""Run template-center and approval actions against the production HTTP client."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_frontend_remaining_page_transport import callback

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=[('print_template_center','setDefault'),('print_template_center','removeTemplate'),('approval','approveItem'),('approval','rejectItem')]
CASES=[(p,n,s) for p,n in ACTIONS for s in ['success','business','http','html','invalid_json','null','primitive','expired401','expired419','network']]
CASES += [(p,n,'cancel') for p,n in ACTIONS if n!='setDefault']
CASES += [('approval','rejectItem','empty_reason'),('approval','rejectItem','whitespace_reason')]
CASES += [('print_template_center',n,'missing_message') for n in ['setDefault','removeTemplate']]


def handler_for(page,name):
    return callback(page,('async ' if page=='print_template_center' else '')+'function '+name+'(')


@pytest.mark.parametrize('page,name,scenario',CASES)
def test_print_center_and_approval_feedback_and_retry(page,name,scenario):
    node=shutil.which('node')
    assert node,'Node required for the real template/approval callback regression'
    program=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let requests=[],messages=[],reloads=0,confirms=0,prompts=0,expired=0,responseScenario=p.scenario;
class FormData{}
const ctx={FormData,Promise,console,document:{querySelector:()=>({content:'fixture-token',value:'fixture-token'})},location:{href:'original',reload(){reloads++;}},setTimeout(){},
confirm:message=>{if(message.includes('登录已过期')){expired++;return false;}confirms++;return p.scenario!=='cancel';},prompt:()=>{prompts++;return p.scenario==='cancel'?null:p.scenario==='empty_reason'?'':p.scenario==='whitespace_reason'?'   ':' <b>原因&A</b> ';},showToast:(m,t)=>messages.push({m,t}),
fetch:(url,options)=>{requests.push({url,options});const s=responseScenario,status=s==='http'?409:s==='html'?503:s==='expired401'?401:s==='expired419'?419:200;if(s==='network')return Promise.reject(Error('offline'));return Promise.resolve({status,ok:status===200,json:()=>['html','invalid_json'].includes(s)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(s==='null'?null:s==='primitive'?'unexpected':{status:['business','http','missing_message'].includes(s)?'error':'success',msg:s==='missing_message'?undefined:'服务端拒绝原因',data:{status:'error',msg:'must not unwrap'}})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var action='+p.handler,ctx);
async function invoke(){await ctx.action(7);await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();if(['cancel','empty_reason'].includes(p.scenario)){assert.equal(requests.length,0);assert.equal(reloads,0);if(p.name==='rejectItem')assert.equal(prompts,1);else assert.equal(confirms,1);return;}
assert.equal(requests.length,1);const {url,options}=requests[0];assert.equal(url,p.page==='print_template_center'?'/print_templates/7/'+(p.name==='setDefault'?'set_default':'delete'):'/approval/7/'+(p.name==='approveItem'?'approve':'reject'));
assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'fixture-token');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');
if(p.name==='rejectItem'){assert.equal(prompts,1);assert.deepEqual(JSON.parse(options.body),{remark:p.scenario==='whitespace_reason'?'   ':' <b>原因&A</b> '});assert.equal(options.headers['Content-Type'],'application/json');}else{assert.equal(options.body,undefined);assert.equal(confirms,p.name==='setDefault'?0:1);}
if(['success','whitespace_reason'].includes(p.scenario)){assert.equal(reloads,1);assert.equal(messages.length,0,'retain success reload behavior');}
else{assert.equal(reloads,0,'failed business/HTTP/malformed results must never reload');assert.equal(ctx.location.href,'original');assert.equal(messages.length,1);assert.equal(messages[0].t,'danger');assert(messages[0].m&&!messages[0].m.includes('undefined'));if(['business','http'].includes(p.scenario))assert(messages[0].m.includes('服务端拒绝原因'));if(p.scenario==='html')assert(messages[0].m.includes('503'));if(p.scenario.startsWith('expired'))assert.equal(expired,1);
responseScenario='success';await invoke();assert.equal(requests.length,2);assert.equal(reloads,1,'failure leaves action available for retry');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result=subprocess.run([node,'--max-old-space-size=64','-e',program],
        input=json.dumps(dict(page=page,name=name,scenario=scenario,handler=handler_for(page,name),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),
        capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('name',['setDefault','removeTemplate'])
def test_template_center_200_business_refusal_does_not_reload(name):
    # Independent lock for the original r.ok bug, without transport/header assertions masking it.
    node=shutil.which('node');assert node
    program=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));let reloads=0,messages=[];
const ctx={FormData:class{},Promise,document:{querySelector:()=>({content:'fixture',value:'fixture'})},confirm:()=>true,showToast:(m,t)=>messages.push({m,t}),location:{reload(){reloads++;}},fetch:()=>Promise.resolve({status:200,ok:true,json:()=>Promise.resolve({status:'error',msg:'业务已拒绝'})})};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var action='+p.handler,ctx);
(async()=>{await ctx.action(7);assert.equal(reloads,0,'HTTP200 business refusal must not trigger reload');assert.deepEqual(messages,[{m:'业务已拒绝',t:'danger'}]);})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result=subprocess.run([node,'--max-old-space-size=64','-e',program],input=json.dumps(dict(handler=handler_for('print_template_center',name),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_four_migrated_callbacks_have_real_dom_entries_and_no_legacy_transport():
    class Attributes(HTMLParser):
        def __init__(self):super().__init__();self.values=[]
        def handle_starttag(self,tag,attrs):self.values.extend(v or '' for k,v in attrs if k=='onclick')
    for page,names in [('print_template_center',['setDefault','removeTemplate']),('approval',['approveItem','rejectItem'])]:
        source=(ROOT/f'app/templates/{page}.html').read_text(encoding='utf-8')
        assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(',source)
        assert source.count('WMS.api.postRaw(')==2
        dom=Attributes();dom.feed(source)
        for name in names:assert any(name+'(' in value for value in dom.values)
