"""BUG-2026-10-23-002: execute actual remaining sales callbacks with production api.js."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = {'import':'sales_order.html','selection':'sales_outbound_selection.html'}


def payload(action, outcome, **extra):
    text = (ROOT/'app/templates'/PAGES[action]).read_text(encoding='utf-8')
    name = 'submitImportForm' if action == 'import' else 'createSelectedOutbound'
    function = re.search(r'^(?:async )?function '+name+r'\(\) \{[\s\S]*?^\}',text,re.M).group()
    function = re.sub(r'{{\s*url_for\("create_sales_outbound_from_selection"\)\s*}}','/sales/create_outbound_from_selection',function)
    if action == 'selection':
        function += '\n' + re.search(r'^window.submitForm = function\(\) \{[^\n]*\};',text,re.M).group()
        assert text.count('onclick="createSelectedOutbound()"') == 1
    else:
        assert 'onchange="submitImportForm()"' in text
    return dict(action=action,outcome=outcome,source=function,
                api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),**extra)


SCRIPT = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const calls=[],messages=[],validations=[],timers=[],confirms=[],resolvers=[];let jsonCalls=0;
const marker='服务器拒绝 <fixture> & 原因';
const file={name:'orders.xlsx'},input={files:p.outcome==='no-file'?[]:[file],disabled:false,value:'fixture.xlsx'};
const importButton={disabled:false},createButton={disabled:false};
const fields={importFile:input,importForm:{fixture:true},salesImportButton:importButton,createSelectedOutboundBtn:createButton,entryStatus:{textContent:''}};
const qty={value:p.quantity===undefined?'2':p.quantity,max:'20',focus(){this.focused=true;}};
const rows=p.outcome==='no-selection'?[]:[{dataset:{id:'19'}}];
class FormData {constructor(form){assert.equal(form,fields.importForm);assert.equal(input.disabled,false,'file must be captured before disabling');this.file=input.files[0];this.csrf='form-token';}}
function response(kind){
 let status=['http-json','http-success'].includes(kind)?400:kind==='http-html'?500:kind.startsWith('401')?401:kind.startsWith('419')?419:200;
 return {status,ok:status<400,json:()=>{jsonCalls++;if(kind==='http-html'||kind==='html')return Promise.reject(SyntaxError('Unexpected token < fixture-html'));
 if(kind==='null')return Promise.resolve(null);
 if(kind==='empty')return Promise.resolve({});
 if(kind==='business'||kind==='http-json')return Promise.resolve({status:'error',msg:marker});
 return Promise.resolve({status:'success',msg:'处理完成',redirect_url:kind==='missing-redirect'?null:'/out_order/7'});}};}
const doc={getElementById:id=>fields[id],querySelector:selector=>selector==='meta[name="csrf-token"]'?{content:'fixture-csrf'}:selector.startsWith('.qty-input')?qty:null,
 querySelectorAll:selector=>selector==='.select-row:checked'?rows:[]};
const ctx={document:doc,FormData,URLSearchParams,Error,JSON,Number,Array,setTimeout:(fn,ms)=>timers.push({fn,ms}),
 showToast:(message,type)=>messages.push({message,type}),showValidation:value=>validations.push(value),
 confirm:message=>{confirms.push(message);return p.outcome.endsWith('yes');},
 fetch:(url,options)=>{calls.push({url,options});
 if(p.outcome==='delayed')return new Promise(resolve=>resolvers.push(resolve));
 if(p.outcome==='network'||p.outcome==='retry'&&calls.length===1)return Promise.reject(Error(marker));
 return Promise.resolve(response(p.outcome==='retry'?'success':p.outcome));}};
// Keep legacy callbacks executable during the byte-backup rollback check.
ctx.csrfFetch=(url,options)=>ctx.fetch(url,options);
ctx.window=ctx;ctx.location={href:'original',reload:()=>ctx.reloaded=true};vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const name=p.action==='import'?'submitImportForm':'createSelectedOutbound';const button=p.action==='import'?importButton:createButton;
const tick=()=>new Promise(r=>setImmediate(r));
function checkTransport(){assert.equal(calls.length,1);const call=calls[0];assert.equal(call.options.method,'POST');assert.equal(call.options.credentials,'same-origin');
 assert.equal(call.options.headers['X-CSRFToken'],'fixture-csrf');assert.equal(call.options.headers['X-Requested-With'],'XMLHttpRequest');
 if(p.action==='import'){assert.equal(call.url,'/sales/import');assert.equal(call.options.body.file,file);assert.equal(call.options.body.csrf,'form-token');assert.equal(call.options.headers['Content-Type'],undefined);}
 else {assert.equal(call.url,'/sales/create_outbound_from_selection');assert.equal(call.options.headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(call.options.body),{items:[{sales_order_item_id:19,quantity:2}]});}}
(async()=>{
 let first=ctx[name]();
 if(p.outcome==='delayed'){
   assert.equal(button.disabled,true);if(p.action==='import')assert.equal(input.disabled,true);
   await ctx[name]();if(p.action==='selection')ctx.submitForm();assert.equal(calls.length,1);assert.equal(timers.length,0);assert.equal(ctx.location.href,'original');
   resolvers[0](response('success'));await first;await tick();
 }else {await first;await tick();}
 if(['no-file','no-selection','invalid'].includes(p.outcome)){
   assert.equal(calls.length,0);assert.equal(button.disabled,false);if(p.outcome!=='no-file')assert.equal(messages.at(-1).type,'warning');return;
 }
 checkTransport();
 if(p.outcome==='retry'){
   assert.equal(button.disabled,false);input.files=[file];input.value='same-file.xlsx';await ctx[name]();await tick();assert.equal(calls.length,2);assert.equal(button.disabled,true);return;
 }
 if(['success','delayed'].includes(p.outcome)){
   assert.equal(button.disabled,true,'lock must cover navigation delay');await ctx[name]();assert.equal(calls.length,1);
   if(p.action==='import'){assert.equal(input.value,'');assert.equal(input.disabled,true);assert.equal(timers.length,1);assert.equal(timers[0].ms,900);assert.equal(ctx.reloaded,undefined);timers[0].fn();assert.equal(ctx.reloaded,true);}
   else{assert.equal(ctx.location.href,'/out_order/7');ctx.submitForm();assert.equal(calls.length,1);assert.equal(timers.length,0);}
   return;
 }
 assert.equal(button.disabled,false);assert.deepEqual(timers.map(timer=>timer.ms),p.outcome.endsWith('-no')?[5000]:[]);assert.equal(ctx.reloaded,undefined);assert.equal(messages.at(-1).type,'danger');
 if(p.action==='import'){assert.equal(input.disabled,false);assert.equal(input.value,'');}
 else{assert.ok(validations.at(-1)[0].includes(messages.at(-1).message));assert.ok(fields.entryStatus.textContent.includes(messages.at(-1).message));}
 if(p.outcome.startsWith('401')||p.outcome.startsWith('419')){
   assert.equal(confirms.length,1);assert.equal(jsonCalls,0);assert.equal(ctx.location.href,p.outcome.endsWith('yes')?'/login':'original');
 }else {assert.equal(ctx.location.href,'original');assert.equal(confirms.length,0);}
 if(['business','network','http-json'].includes(p.outcome))assert.ok(messages.at(-1).message.includes(marker));
 if(p.outcome==='http-html')assert.ok(messages.at(-1).message.includes('500'));
})().catch(error=>{console.error(error);process.exitCode=1;});
'''


def execute(action,outcome,**extra):
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    result=subprocess.run([node,'--max-old-space-size=64','-e',SCRIPT,json.dumps(payload(action,outcome,**extra))],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('action',['import','selection'])
@pytest.mark.parametrize('outcome',['success','business','http-json','http-success','http-html','html','null','empty','network','401-yes','401-no','419-yes','419-no','delayed','retry'])
def test_actual_callback_and_api_protocol_feedback_and_lock(action,outcome):
    execute(action,outcome)


@pytest.mark.parametrize('quantity',['0','-1','NaN','21'])
def test_selection_quantity_guard_sends_no_request(quantity):
    execute('selection','invalid',quantity=quantity)


def test_empty_file_does_not_submit():
    execute('import','no-file')


def test_empty_selection_does_not_submit():
    execute('selection','no-selection')


def test_success_without_redirect_is_feedback_not_broken_navigation():
    execute('selection','missing-redirect')
