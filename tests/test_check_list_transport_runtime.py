"""Execute all seven stocktake list mutations against the production HTTP client."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
CASES = [(action, scenario) for action in ['delete', 'revert', 'batch', 'copy', 'add', 'edit', 'import']
         for scenario in ['success', 'business', 'http', 'html', 'invalid_json', 'null', 'invalid_body', 'expired401', 'expired419', 'network']]
CASES += [(action, 'cancel') for action in ['delete', 'revert', 'batch', 'copy']]
CASES += [('batch', 'empty'), ('import', 'empty')]


def handler_for(action):
    source = (ROOT / 'app/templates/check.html').read_text(encoding='utf-8')
    if action in ['delete', 'revert', 'batch', 'copy']:
        marker = {'delete': 'const delBtns', 'revert': 'const revertBtns', 'batch': "batchDeleteBtn.addEventListener('click'", 'copy': 'const copyBtns'}[action]
        return callback('check', 'async function()', source.index(marker))
    if action in ['add', 'edit']:
        marker = action + "Form.addEventListener('submit'"
        return callback('check', 'function(e)', source.index(marker)).replace('/fixture/0/', '/check/add')
    return callback('check', 'function submitDocumentImport(')


@pytest.mark.parametrize('action,scenario', CASES)
def test_check_list_mutations_keep_payload_confirmation_failure_and_retry(action, scenario):
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let sent=[],messages=[],timers=[],reloads=0,hidden=0,confirmed=0;let scenario=p.scenario;
const fields={warehouse:'A',warehouse_id:'2',scope:'category',category_id:'4',remark:'新增备注 &+ 中',csrf_token:'form-csrf'};
class FormData{constructor(form){this.fields=new Map(form?Object.entries(fields):[]);this.owner=form?.id;}append(k,v){this.fields.set(k,String(v));}entries(){return this.fields.entries();}}
const file={files:p.scenario==='empty'?[]:[{name:'fixture.xlsx'}],value:'fixture.xlsx',disabled:false};const form={id:p.action==='add'?'addForm':'importForm',action:'/check/import'};
const elements={editId:{value:'7'},editRemark:{value:'修改 & + 中文 \n保留'},addModal:{},editModal:{},importForm:form,importFile:file};
const ctx={FormData,Headers,document:{querySelector:()=>({content:'fixture-csrf'}),querySelectorAll:()=>p.scenario==='empty'?[]:[{value:'7'},{value:'8'}],getElementById:id=>elements[id]},
showConfirm:()=>{confirmed++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>false,showToast:(m,t)=>messages.push({m,t}),setTimeout:fn=>timers.push(fn),location:{href:'original',reload(){reloads++;}},bootstrap:{Modal:{getInstance:()=>({hide(){hidden++;}})}},
fetch:(u,o)=>{sent.push({u,o});const status=scenario==='http'?400:scenario==='html'?503:scenario==='expired401'?401:scenario==='expired419'?419:200;
const body=scenario==='null'?null:scenario==='invalid_body'?'unexpected value':{status:['business','http'].includes(scenario)?'error':'success',msg:'fixture explanation',id:17,redirect_url:'/check/17'};
return scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(scenario)?Promise.reject(SyntaxError('not JSON')):Promise.resolve(body)});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var handler='+p.handler,ctx);
async function invoke(){if(p.action==='import')ctx.handler('importForm','importFile');else if(['add','edit'].includes(p.action))ctx.handler.call(form,{preventDefault(){}});else await ctx.handler.call({getAttribute:()=>7});await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();
if(['cancel','empty'].includes(p.scenario)){assert.equal(sent.length,0);assert.equal(hidden,0);assert.equal(reloads,0);if(p.action==='batch'&&p.scenario==='empty')assert(messages.some(m=>m.t==='warning'));return;}
assert.equal(sent.length,1);const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
assert.equal(req.u,p.action==='add'?'/check/add':p.action==='import'?'/check/import':p.action==='batch'?'/check/batch_delete':'/check/7/'+(p.action==='edit'?'update':p.action));
if(['add','edit','import'].includes(p.action)){assert(req.o.body instanceof FormData);assert(!h.has('Content-Type'));const sentFields=Object.fromEntries(req.o.body.entries());assert.deepEqual(sentFields,p.action==='edit'?{remark:elements.editRemark.value}:fields);}
if(p.action==='batch')assert.deepEqual(JSON.parse(req.o.body),{ids:['7','8']},'backend accepts root JSON ids; never double encode');
if(['delete','revert','batch','copy'].includes(p.action))assert.equal(confirmed,1);
if(p.action==='import'){assert.equal(file.value,'','finally clears file on every outcome');assert.equal(file.disabled,false);}
if(p.scenario==='success'){assert(messages.some(m=>m.t==='success'));assert.equal(hidden,['add','edit'].includes(p.action)?1:0);timers.forEach(fn=>fn());assert.equal(reloads,1);assert.equal(ctx.location.href,'original','copy retains list reload behavior');}
else {assert(messages.some(m=>m.t==='danger'),'failure visible');assert.equal(reloads,0);assert.equal(ctx.location.href,'original');assert.equal(hidden,0,'failed modal remains open');
if(['http','business'].includes(p.scenario))assert(messages.some(m=>m.m.includes('fixture explanation')));if(p.scenario==='html')assert(messages.some(m=>m.m.includes('503')));
scenario='success';if(p.action==='import')file.value='fixture.xlsx';await invoke();assert.equal(sent.length,2);assert.equal(messages.at(-1).t,'success');assert.equal(hidden,['add','edit'].includes(p.action)?1:0);}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for real transport verification'
    payload = dict(action=action, scenario=scenario, handler=handler_for(action), api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
