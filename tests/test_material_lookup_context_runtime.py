"""Exercise remaining material lookup consumers against delayed real HTTP responses."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]


def execute(program, payload):
    binary = shutil.which('node')
    assert binary, 'Node.js is required for material lookup runtime verification'
    payload['api'] = (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')
    payload['escape'] = function((ROOT / 'app/static/js/app.js').read_text(encoding='utf-8'), 'escapeHtml')
    result = subprocess.run([binary, '--max-old-space-size=64', '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('action', ['normal', 'typing', 'clear', 'row', 'close', 'close_timer', 'detach', 'order', 'selected', 'blur', 'direct'])
def test_detail_lookup_does_not_apply_to_a_previous_context(page, action):
    detail(page, action)


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('error', ['http', 'business', 'shape', 'network'])
def test_detail_lookup_rejects_error_payloads(page, error):
    detail(page, 'error', error)


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('action', ['normal', 'typing', 'close'])
def test_detail_modal_preserves_the_same_context_guard(page, action):
    detail(page, action, modal=True)


def detail(page, action, error=None, modal=False):
    source = (ROOT / f'app/templates/{page}_order_detail.html').read_text(encoding='utf-8')
    source = source.replace("{{ (order.warehouse or '')|tojson }}", json.dumps('fixture-warehouse'))
    names = ['getMaterialQuickDropdown', 'hideMaterialQuickDropdown', 'setMaterialQuickActive',
             'selectAddMaterial', 'renderMaterialQuickDropdown', 'lookupAddMaterial', 'scheduleAddMaterialLookup']
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const timers=new Map(),pending=[],fills=[];let next=0;
const dropdown=()=>({style:{display:'none'},innerHTML:'',querySelectorAll:()=>[]});
const rows=[0,1].map(id=>{const d=dropdown(),r={id,isConnected:true,querySelector:()=>null};const input={value:'',isConnected:true,closest:s=>s==='.material-quick-search'?{querySelector:()=>d}:p.modal?null:r};return {input,dropdown:d,row:r};});
const document={activeElement:rows[0].input,getElementById:id=>id==='code'?rows[0].input:rows[0].dropdown,querySelector:()=>({content:'token'})};
const ctx={document,FormData:class{},URLSearchParams,WMS:{positionDropdown(){}},getMaterialUnit:m=>m.unit||'',formatStock:n=>String(n),
 setTimeout:(fn,delay)=>{const id=++next;timers.set(id,{fn,delay});return id;},clearTimeout:id=>timers.delete(id),
 fetch:(url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject})),
 fillAddMaterialInfo:(m,r)=>fills.push({code:m.code,row:r?.id}),fillInlineMaterialInfo:(r,m)=>fills.push({code:m.code,row:r.id}),clearAddMaterialInfo(){},clearInlineMaterialInfo(){}};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.escape,ctx);vm.runInContext(p.api,ctx);
vm.runInContext('let materialLookupTimer=null,materialLookupToken=0,materialQuickResults=[],materialQuickActiveIndex=-1,activeMaterialInput=null;',ctx);vm.runInContext(p.script,ctx);
function type(index,value){ctx.input=rows[index].input;vm.runInContext('activeMaterialInput=input',ctx);ctx.input.value=value;document.activeElement=ctx.input;ctx.scheduleAddMaterialLookup();}
function tick(){for(const [id,t] of [...timers]){timers.delete(id);t.fn();}}
async function finish(i,code,err=null){if(err==='network')pending[i].reject(Error('offline'));else{let data={status:'success',data:[{code,name:'料'+code,stock:2,unit:'个'}]};if(err==='business')data.status='error';if(err==='shape')data.data=null;pending[i].resolve({ok:err!=='http',status:err==='http'?503:200,json:()=>Promise.resolve(data)});}for(let j=0;j<5;j++)await new Promise(r=>setImmediate(r));}
(async()=>{
 type(0,'A');
 if(p.action==='close_timer'){ctx.hideMaterialQuickDropdown();tick();assert.equal(pending.length,0);return;}
 if(p.action==='direct'){ctx.lookupAddMaterial();tick();assert.equal(pending.length,1,'direct focus lookup must cancel the pending timer');}else tick();assert.equal(pending.length,1);
 if(p.action==='typing')type(0,'B');if(p.action==='clear')type(0,'');if(p.action==='row')type(1,'B');
 if(p.action==='close')ctx.hideMaterialQuickDropdown();if(p.action==='detach')rows[0].input.isConnected=false;
 if(p.action==='selected')ctx.selectAddMaterial({code:'LOCAL'});
 if(p.action==='blur')document.activeElement={};
 if(p.action==='order'){type(1,'B');tick();await finish(1,'B');const good=fills.slice();await finish(0,'A');assert.deepEqual(fills,good);assert.equal(fills[0].row,1);return;}
 const before=fills.slice();await finish(0,'A',p.action==='error'?p.error:null);
 if(['typing','clear','row','close','detach','selected','error'].includes(p.action)){assert.deepEqual(fills,before,'obsolete/error result cannot fill the row');assert.equal(rows[0].dropdown.style.display,'none');return;}
 assert.deepEqual(fills,[{code:'A',row:p.modal?undefined:0}]);
 assert.equal(rows[0].dropdown.style.display,p.action==='blur'?'none':'block');
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""
    execute(program, dict(page=page, action=action, error=error, modal=modal, script='\n'.join(function(source, name) for name in names)))


@pytest.mark.parametrize('action', ['normal', 'typing', 'clear', 'order', 'row', 'row_timer', 'manual', 'detach', 'stale_failure', 'empty'])
def test_ai_confirmation_material_filter_uses_current_context(action):
    confirmation(action)


@pytest.mark.parametrize('error', ['http', 'business', 'shape', 'network'])
def test_ai_confirmation_filter_rejects_error_data(error):
    confirmation('error', error)


def confirmation(action, error=None):
    source = (ROOT / 'app/templates/ai_document_confirm.html').read_text(encoding='utf-8')
    script = source[source.index('    let filterTimer = null;'):source.index('    // Select all / deselect all')]
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const timers=new Map(),pending=[],updates=[];let next=0;
function el(){return {value:'',isConnected:true,focusCount:0,handlers:{},addEventListener:(function(name,fn){this.handlers[name]=fn;}),focus(){this.focusCount++;}};}
const filter=el(),selects=[el(),el()],boxes=[{},{}];selects.forEach((s,i)=>s.closest=()=>({querySelector:()=>boxes[i]}));
const rowFilters=selects.map((select,i)=>{const b=el();b.getAttribute=()=>i?'B':'A';b.closest=()=>({querySelector:()=>select});return b;});
const ctx={filter,selects,rowFilters,initialOptions:new Map([['local',{id:'local',code:'LOCAL'}]]),document:{querySelector:()=>({content:'token'})},FormData:class{},URLSearchParams,
 updateSelect:(select,items)=>updates.push({index:selects.indexOf(select),codes:Array.from(items,x=>x.code)}),
 setTimeout:(fn,delay)=>{const id=++next;timers.set(id,fn);return id;},clearTimeout:id=>timers.delete(id),fetch:(url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject}))};ctx.window=ctx;ctx.fetcher=ctx.fetch;
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
function type(value){filter.value=value;filter.handlers.input();}
function tick(){for(const [id,fn] of [...timers]){timers.delete(id);fn();}}
async function finish(i,code,err=null){if(err==='network')pending[i].reject(Error('offline'));else{let data={status:'success',data:[{id:1,code,name:'料'+code}]};if(err==='business')data.status='error';if(err==='shape')data.data=null;pending[i].resolve({ok:err!=='http',status:err==='http'?503:200,json:()=>Promise.resolve(data)});}for(let j=0;j<5;j++)await new Promise(r=>setImmediate(r));}
(async()=>{
 if(p.action==='empty'){type('');tick();assert.equal(pending.length,0);assert.deepEqual(updates,[{index:0,codes:['LOCAL']},{index:1,codes:['LOCAL']}]);return;}
 type('A');if(p.action==='row_timer'){rowFilters[1].handlers.click();tick();assert.equal(pending.length,1,'row filter must cancel the old global timer');await finish(0,'B');assert.deepEqual(updates,[{index:1,codes:['B']}]);return;}
 tick();assert.equal(pending.length,1);
 if(p.action==='typing')type('B');if(p.action==='clear')type('');
 if(p.action==='manual'){selects[0].value='manual';selects[0].handlers.change();assert.equal(boxes[0].checked,true);}
 if(p.action==='detach')filter.isConnected=false;
 if(['order','row','stale_failure'].includes(p.action)){
  if(p.action==='row')rowFilters[1].handlers.click();else{type('B');tick();}
  await finish(1,'B');const good=updates.slice();await finish(0,'A',p.action==='stale_failure'?'network':null);assert.deepEqual(updates,good);assert(updates.every(u=>u.codes[0]==='B'));if(p.action==='row')assert.deepEqual(updates,[{index:1,codes:['B']}]);return;
 }
 await finish(0,'A',p.action==='error'?p.error:null);
 if(['typing','clear','manual','detach'].includes(p.action)){assert.equal(updates.length,0,'old callbacks must not change options');return;}
 if(p.action==='error'){assert(updates.every(u=>u.codes.length===0));return;}
 assert.deepEqual(updates,[{index:0,codes:['A']},{index:1,codes:['A']}]);
})().then(()=>process.stdout.write('ok')).catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
"""
    execute(program, dict(action=action, error=error, script=script))
