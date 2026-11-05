"""Execute the production header listeners, including late-response races."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = r"""
const vm=require('node:vm'), assert=require('node:assert/strict');
const payload=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
class Field {
 constructor(value=''){this.value=value;this.dataset={};this.events={};this.isConnected=true;}
 addEventListener(name,fn){this.events[name]=fn;}
 dispatchEvent(event){this.events[event.type]?.(event);}
 emit(type){this.dispatchEvent({type});}
 closest(){return this.form;}
}
function setup(contract='',name=''){
 const input=new Field(contract),project=new Field(name),requests=[],toasts=[];
 const form={querySelector:()=>project};input.form=form;
 let timer,ready;
 const document={addEventListener:(name,fn)=>{if(name==='DOMContentLoaded')ready=fn;},querySelectorAll:()=>[input]};
 const window={WMS:{api:{getContracts:keyword=>new Promise((resolve,reject)=>requests.push({keyword,resolve,reject}))}},showToast:(...args)=>toasts.push(args)};
 vm.runInNewContext(payload.source,{window,document,Event:class{constructor(type){this.type=type;}},
  setTimeout:fn=>{timer=fn;return 1;},clearTimeout:()=>{timer=null;}});
 ready();
 return {input,project,requests,toasts,type(value){input.value=value;input.emit('input');if(timer){let fn=timer;timer=null;fn();}}};
}
const tick=async()=>{for(let i=0;i<6;i++)await Promise.resolve();};
const found=(no,name)=>({contracts:[{contract_no:no,project_name:name}]});
(async()=>{
 const s=setup(payload.case==='initial'?'HD1':'',payload.case==='existing'?'人工工程':'');
 switch(payload.case){
 case 'exact':
  s.type(' hd1 ');assert.equal(s.requests[0].keyword,'hd1');s.requests[0].resolve(found('HD1','工程一'));await tick();
  assert.equal(s.input.value,'HD1');assert.equal(s.project.value,'工程一');break;
 case 'blur':
  s.input.value='HD1';s.input.emit('blur');s.requests[0].resolve(found('HD1','工程一'));await tick();assert.equal(s.project.value,'工程一');break;
 case 'late':
  s.type('HD1');s.type('HD2');s.requests[1].resolve(found('HD2','工程二'));await tick();s.requests[0].resolve(found('HD1','旧工程'));await tick();assert.equal(s.project.value,'工程二');break;
 case 'manual':
  s.type('HD1');s.project.value='手工工程';s.project.emit('input');s.requests[0].resolve(found('HD1','工程一'));await tick();assert.equal(s.project.value,'手工工程');break;
 case 'existing':
  s.input.value='HD1';s.input.emit('blur');assert.equal(s.requests.length,0);assert.equal(s.project.value,'人工工程');break;
 case 'clear':
  s.type('HD1');s.requests[0].resolve(found('HD1','工程一'));await tick();s.type('');assert.equal(s.project.value,'');break;
 case 'unknown':
  s.type('HD1');s.project.value='手工工程';s.requests[0].resolve(found('HD2','不应带出'));await tick();assert.equal(s.project.value,'手工工程');break;
 case 'error':
  s.type('HD1');s.requests[0].reject(new Error('offline'));await tick();assert.equal(s.project.value,'');assert.equal(s.toasts.length,1);break;
 case 'initial':
  assert.equal(s.requests.length,1);s.requests[0].resolve(found('HD1','工程一'));await tick();assert.equal(s.project.value,'工程一');break;
 case 'stale_error':
  s.type('HD1');s.type('HD2');s.requests[0].reject(new Error('late'));s.requests[1].resolve(found('HD2','工程二'));await tick();assert.equal(s.toasts.length,0);assert.equal(s.project.value,'工程二');break;
 default:throw new Error('Unknown test');
 }
 process.stdout.write(JSON.stringify({ok:true,case:payload.case}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
"""


@pytest.mark.parametrize('case', ['exact', 'blur', 'late', 'manual', 'existing', 'clear',
                                 'unknown', 'error', 'initial', 'stale_error'])
def test_product_header_contract_runtime(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node is required for production listener execution')
    source = (ROOT/'app/static/js/product-receipt-contract.js').read_text(encoding='utf-8')
    result = subprocess.run([node, '-e', NODE], input=json.dumps({'source': source, 'case': case}),
                            text=True, encoding='utf-8', capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'ok': True, 'case': case}
