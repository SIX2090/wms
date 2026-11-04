"""Use the shipped handler/API with a genuinely pending response, then retry."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('action', ['material', 'unit'])
@pytest.mark.parametrize('phase', ['success', 'business', 'network', 'html'])
def test_pending_material_entry_rejects_second_submit_and_restores_retry(action, phase):
    source = (ROOT / 'app/static/js/pages/material-add.js').read_text(encoding='utf-8')
    form_id = 'addMaterialForm' if action == 'material' else 'addUnitForm'
    offset = source.index("getElementById('" + form_id + "').addEventListener('submit'")
    handler = callback('material_add', 'function(e)', offset)
    dependencies = callback('material_add', 'function withPendingForm(')
    dependencies += '\n' + callback('material_add', 'function resolveMaterialRelation(' if action == 'material' else 'function closeUnitModal(')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let requests=[],release,mode=p.phase,messages=[];
const button={disabled:false},attributes={},feedback={textContent:''};
const form={dataset:{},values:{name:'retained draft'},setAttribute(k,v){attributes[k]=v;},querySelectorAll(){return [button];},querySelector(){return feedback;}};
class FormData{constructor(value){this.values={...value.values};}get(k){return this.values[k]||'';}}
const c={Promise,FormData,Headers,location:{href:'original'},units:[],suppliers:[],unitSearch:{value:''},unitIdHidden:{value:''},supplierSearch:{value:''},supplierIdHidden:{value:''},
document:{querySelector(){return {content:'fixture-csrf'};},getElementById(){return {remove(){},focus(){}};}},showToast:(m,t)=>messages.push({m,t}),alert(){},
fetch:(url,options)=>{requests.push({url,options});return new Promise((resolve,reject)=>{release=()=>mode==='network'?reject(Error('offline')):resolve({ok:mode!=='html',status:mode==='html'?503:200,
json:()=>mode==='html'?Promise.reject(Error('HTML')):Promise.resolve({status:mode==='business'?'error':'success',msg:'server explanation',id:9,name:'箱'})});});}};
c.window=c;vm.createContext(c);vm.runInContext(p.api,c);vm.runInContext(p.dependencies,c);vm.runInContext('var handler='+p.handler,c);
async function settle(){for(let i=0;i<12;i++)await Promise.resolve();}
(async()=>{
 const a=c.handler.call(form,{preventDefault(){}}),b=c.handler.call(form,{preventDefault(){}});await settle();
 assert.equal(requests.length,1);assert.equal(button.disabled,true);assert.equal(attributes['aria-busy'],'true');assert.equal(form.dataset.wmsPending,'1');
 release();await Promise.all([a,b]);assert.equal(button.disabled,false);assert.equal(attributes['aria-busy'],'false');assert.equal(form.dataset.wmsPending,undefined);
 assert.equal(form.values.name,'retained draft');
 if(p.phase!=='success'){
  assert(messages.some(m=>m.t==='danger'));mode='success';const retry=c.handler.call(form,{preventDefault(){}});await settle();assert.equal(requests.length,2);release();await retry;assert.equal(button.disabled,false);
 }
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '--max-old-space-size=96', '-e', program,
                             json.dumps({'phase': phase, 'handler': handler, 'dependencies': dependencies,
                                         'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')})],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('mode', ['lost', 'user_moved', 'detached', 'already_disabled', 'no_focus', 'retained_input'])
def test_pending_form_restores_only_lost_usable_focus(mode):
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),mode=JSON.parse(process.argv[2]);
const body={},other={},document={body,activeElement:null};let disabled=mode==='already_disabled',focused=0,release;
const button={isConnected:true,focus(){focused++;document.activeElement=this;}};
Object.defineProperty(button,'disabled',{get(){return disabled;},set(value){disabled=value;if(value&&document.activeElement===button)document.activeElement=body;}});
document.activeElement=mode==='no_focus'?null:mode==='retained_input'?other:button;
const form={dataset:{},setAttribute(){},querySelectorAll(){return [button];},querySelector(){return null;}};
const ctx={Promise,document};vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 const pending=ctx.withPendingForm(form,()=>new Promise(resolve=>{release=resolve;}));await Promise.resolve();
 if(mode==='user_moved')document.activeElement=other;
 if(mode==='detached')button.isConnected=false;
 release();await pending;
 assert.equal(button.disabled,mode==='already_disabled');assert.equal(form.dataset.wmsPending,undefined);
 assert.equal(focused,mode==='lost'?1:0);
 assert.equal(document.activeElement,mode==='lost'?button:['user_moved','retained_input'].includes(mode)?other:mode==='no_focus'?null:body);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program,
                             callback('material_add', 'function withPendingForm('), json.dumps(mode)],
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
