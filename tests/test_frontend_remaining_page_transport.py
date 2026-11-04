"""Run actual form/list/designer callbacks with the shared API and failed responses."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def callback(page, marker, start_at=0):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    start = source.index(marker, start_at)
    brace = source.index('{', start)
    depth, quote, escaped = 0, None, False
    for i in range(brace, len(source)):
        c = source[i]
        if quote:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == quote:
                quote = None
        elif c in "\"'`":
            quote = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return re.sub(r'{{.*?}}', '/fixture/0/', source[start:i + 1])
    raise AssertionError('Unclosed callback')


@pytest.mark.parametrize('action', ['material', 'unit', 'label_add', 'label_delete', 'label_default', 'layout'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'html', 'expired401', 'expired419', 'network'])
def test_page_actions_preserve_payload_and_retry_after_failures(action, scenario):
    dependencies = ''
    if action in ('material', 'unit'):
        form = 'addMaterialForm' if action == 'material' else 'addUnitForm'
        source = (ROOT / 'app/templates/material_add.html').read_text(encoding='utf-8')
        offset = source.index(f"getElementById('{form}').addEventListener('submit'")
        # Select the real listener, excluding unrelated page initialization.
        handler = callback('material_add', 'function(e)', offset)
        if action == 'material':
            dependencies = callback('material_add', 'function resolveMaterialRelation(')
    elif action == 'label_add':
        handler = callback('label_template', 'function(e)')
    elif action in ('label_delete', 'label_default'):
        handler = callback('label_template', 'function deleteTemplate(id)' if action == 'label_delete' else 'function setDefault(id)')
    else:
        handler = callback('label_template_detail', 'async function saveLayout()')
    program = r'''
const vm=require('node:vm'), assert=require('node:assert/strict'), p=JSON.parse(process.argv[1]);
let requests=[],messages=[],reloads=0,removed=0,confirmed=0;let responseScenario=p.scenario;
class FormData {constructor(form){this.form=form;}get(k){return 'PCS';}}
const btn={disabled:false,innerHTML:'保存'}, fields={marginTop:{value:'3'},marginRight:{value:'4'},marginBottom:{value:'5'},marginLeft:{value:'6'}};
const ctx={FormData,Headers,document:{querySelector:s=>s.includes('csrf-token')?{content:'fixture-csrf'}:btn,getElementById:id=>fields[id]||{remove(){removed++;}}},
showToast:(m,t)=>messages.push({m,t}),alert:m=>messages.push({m,t:'manual'}),confirm:()=>{confirmed++;return true;},setTimeout(){},
location:{href:'original',reload(){reloads++;}},units:[],unitSearch:{value:''},unitIdHidden:{value:''},layoutData:{'0-0':{field:'code',label:'编号',style:{}}},_savingLayout:false,
fetch:(url,options)=>{requests.push({url,options});const status=responseScenario==='http'?400:responseScenario==='html'?503:responseScenario==='expired401'?401:responseScenario==='expired419'?419:200;
return responseScenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:status===200,status,json:()=>responseScenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({status:['business','http'].includes(responseScenario)?'error':'success',msg:'fixture explanation',id:7,name:'个'})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);
if(p.dependencies){
 ctx.suppliers=[];ctx.supplierSearch={value:''};ctx.supplierIdHidden={value:''};
 vm.runInContext(p.dependencies,ctx);
}
vm.runInContext('var handler='+p.handler+';',ctx);
async function invoke(){const result=ctx.handler.call({id:'fixture-form'},{preventDefault(){}});await result;await new Promise(r=>setImmediate(r));}
(async()=>{if(p.action==='label_delete'||p.action==='label_default'){ctx.run=()=>ctx.handler(7);await ctx.run();await new Promise(r=>setImmediate(r));}else await invoke();
assert.equal(requests.length,1);const first=requests[0],headers=new Headers(first.options.headers);assert.equal(first.options.method,'POST');assert.equal(first.options.credentials,'same-origin');assert.equal(headers.get('X-CSRFToken'),'fixture-csrf');
if(['material','unit','label_add'].includes(p.action)){assert(first.options.body instanceof FormData);assert(!headers.has('Content-Type'));}
if(p.action==='layout'){assert.deepEqual(JSON.parse(first.options.body),{layout:{'0-0':{field:'code',label:'编号',style:{}},marginTop:3,marginRight:4,marginBottom:5,marginLeft:6}});assert.equal(btn.disabled,false);assert.equal(btn.innerHTML,'保存');assert.equal(ctx._savingLayout,false);}
if(p.scenario==='success'){
 if(p.action==='material'){assert.equal(ctx.location.href,'/material');assert.equal(messages[0].t,'manual');}
 if(p.action==='unit'){assert.equal(ctx.units.length,1);assert.equal(ctx.unitIdHidden.value,7);assert.equal(removed,1);}
 if(p.action.startsWith('label_'))assert.equal(reloads,1);
 if(p.action==='layout')assert.equal(messages[0].t,'success');
}else{assert.equal(reloads,0);assert.equal(ctx.location.href,p.scenario.startsWith('expired')?'/login':'original');assert.equal(removed,0);assert(messages.some(m=>m.t==='danger'),'failure must be visible');
 if(['business','http'].includes(p.scenario))assert(messages.some(m=>m.m.includes('fixture explanation')),'retain server explanation');
 if(p.scenario==='html')assert(messages.some(m=>m.m.includes('503')),'non-JSON HTTP status remains readable');
 if(p.action==='layout'){responseScenario='success';await invoke();assert.equal(requests.length,2);assert.equal(messages.at(-1).t,'success','failed save permits retry');}}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node is required for runtime transport verification'
    result = subprocess.run([node, '-e', program, json.dumps(dict(action=action, scenario=scenario, handler=handler, dependencies=dependencies, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')))], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
