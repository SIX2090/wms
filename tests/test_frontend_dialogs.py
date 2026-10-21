"""Execute the production dialog queue and rejection handler with real events."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _function(source, name):
    start = re.search(r'(?:async )?function ' + name + r'\(', source).start()
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError('unclosed function')


@pytest.mark.parametrize('case', ['confirm', 'prompt', 'empty', 'cancel', 'escape', 'tab', 'queue', 'enter', 'fallback', 'deferredfocus'])
def test_dialog_runtime(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8').split('// 嵌入参数处理：')[0]
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);
const nodes={},listeners={};let restores=0,native=0;const document={activeElement:{isConnected:true,focus(){restores++;document.activeElement=this;}},getElementById:id=>nodes[id]||null,addEventListener:(t,f)=>listeners[t]=f};
for(const id of ['cbConfirmOverlay','cbConfirmTitle','cbConfirmMessage','cbConfirmOk','cbConfirmCancel','cbPromptField','cbPromptInput'])nodes[id]={id,dataset:{},hidden:false,value:'',textContent:'',attrs:{},handlers:{},classList:{add(){},remove(){}},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];},focus(){document.activeElement=this;},select(){},addEventListener(k,f){this.handlers[k]=f;},querySelectorAll(){return [nodes.cbPromptInput,nodes.cbConfirmCancel,nodes.cbConfirmOk].filter(n=>!n.hidden&&!(n.id==='cbPromptInput'&&nodes.cbPromptField.hidden));}};
const ctx={document,Promise,console,setTimeout:fn=>fn(),WMS:{},confirm:()=>{native++;return true;},prompt:()=>{native++;return 'fallback';}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.source,ctx);assert.equal(typeof ctx.WMS.prompt,'function');ctx.initDialogEvents();
const key=(key,shiftKey=false)=>{let prevented=false;listeners.keydown({key,shiftKey,isComposing:false,preventDefault(){prevented=true;},stopImmediatePropagation(){}});return prevented;};
(async()=>{
 if(p.case==='deferredfocus'){const timers=[];ctx.setTimeout=fn=>timers.push(fn);const promise=ctx.WMS.prompt('reason');ctx.resolveConfirm(false);assert.equal(await promise,null);assert.equal(restores,0);timers.shift()();assert.equal(restores,1);return;}
 if(p.case==='fallback'){delete nodes.cbPromptInput;assert.equal(await ctx.WMS.prompt('reason'),'fallback');assert.equal(native,1);return;}
 if(p.case==='confirm'){const promise=ctx.WMS.confirm('literal <b>text</b>');assert.equal(nodes.cbConfirmMessage.textContent,'literal <b>text</b>');assert.equal(nodes.cbPromptField.hidden,true);assert.equal(document.activeElement,nodes.cbConfirmCancel);ctx.resolveConfirm(true);assert.equal(await promise,true);assert.equal(restores,1);return;}
 if(p.case==='tab'){const promise=ctx.WMS.confirm('check');nodes.cbConfirmOk.focus();assert(key('Tab'));assert.equal(document.activeElement,nodes.cbConfirmCancel);assert(key('Tab',true));assert.equal(document.activeElement,nodes.cbConfirmOk);ctx.resolveConfirm(false);assert.equal(await promise,false);return;}
 const first=ctx.WMS.prompt('reason',{defaultValue:'original'});assert.equal(document.activeElement,nodes.cbPromptInput);assert.equal(nodes.cbPromptInput.value,'original');
 if(p.case==='queue'){const second=ctx.WMS.confirm('next');nodes.cbPromptInput.value='one';ctx.resolveConfirm(true);assert.equal(await first,'one');assert.equal(nodes.cbConfirmMessage.textContent,'next');assert(nodes.cbPromptField.hidden);ctx.resolveConfirm(false);assert.equal(await second,false);return;}
 if(p.case==='cancel'){ctx.resolveConfirm(false);assert.equal(await first,null);return;}
 if(p.case==='escape'){assert(key('Escape'));assert.equal(await first,null);assert.equal(restores,1);return;}
 nodes.cbPromptInput.value=p.case==='empty'?'':'<img src=x onerror=alert(1)> & quoted';
 if(p.case==='enter')assert(key('Enter'));else ctx.resolveConfirm(true);
 assert.equal(await first,nodes.cbPromptInput.value);assert.equal(native,0);assert.equal(nodes.cbConfirmOverlay.attrs['aria-hidden'],'true');
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', script, json.dumps({'source': source, 'case': case})], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('scenario', ['success', 'failure', 'cancel', 'pending'])
def test_rejection_keeps_manual_boundary_and_request_lock(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    template = (ROOT / 'app/templates/purchase_request_detail.html').read_text(encoding='utf-8')
    handler = _function(template, 'rejectOrder')
    helper = (ROOT / 'app/static/js/document-action.js').read_text(encoding='utf-8')
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);let requests=[],prompts=0,toasts=[],reloads=0,release;
const button={disabled:false,attrs:{},getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}};
const ctx={document:{querySelector:()=>button,querySelectorAll:()=>[button]},Promise,showToast:m=>toasts.push(m),setTimeout:f=>f(),location:{reload(){reloads++;}},WMS:{prompt:(message,options)=>{prompts++;assert.equal(options.returnFocus,button);return Promise.resolve(p.scenario==='cancel'?null:'<literal> reason');},api:{postRaw:(url,data)=>{requests.push({url,data});return p.scenario==='pending'?new Promise(r=>release=r):p.scenario==='failure'?Promise.reject({message:'fixture error'}):Promise.resolve({status:'success'});}}}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.handler,ctx);
(async()=>{const a=ctx.rejectOrder(7),b=ctx.rejectOrder(7);assert.equal(a,b);await new Promise(r=>setImmediate(r));assert.equal(prompts,1);assert.equal(requests.length,p.scenario==='cancel'?0:1);
if(requests.length){assert.equal(requests[0].url,'/purchase_request/7/reject');assert.equal(requests[0].data.remark,'<literal> reason');}
if(p.scenario==='pending'){assert(button.disabled);assert.equal(button.attrs['aria-busy'],'true');release({status:'success'});}await a;assert.equal(button.disabled,false);assert.equal(reloads,['success','pending'].includes(p.scenario)?1:0);if(p.scenario==='failure')assert(toasts.some(x=>x.includes('fixture error')));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', script, json.dumps(dict(handler=handler, helper=helper, scenario=scenario))], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
