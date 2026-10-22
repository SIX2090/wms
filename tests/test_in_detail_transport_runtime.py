"""Execute every inbound detail mutation callback with the real shared API."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'app/templates/in_order_detail.html'
ACTIONS = ['row_delete', 'inline_add', 'batch_delete', 'header', 'revert', 'copy', 'delete', 'convert', 'paste', 'modal_add', 'toolbar_delete', 'excel']
SCENARIOS = ['success', 'business', 'http', 'html', 'malformed', 'invalid_json', 'expired401', 'expired419', 'network']
CASES = [(a, s) for a in ACTIONS for s in SCENARIOS]
CASES += [(a, 'cancel') for a in ['row_delete', 'batch_delete', 'revert', 'copy', 'delete', 'convert', 'toolbar_delete']]
CASES += [('batch_delete', s) for s in ['mixed_business', 'mixed_network', 'mixed_malformed']]
CASES += [('copy', 'fallback'), ('delete', 'parent'), ('convert', 'parent'), ('convert', 'cross_origin')]
CASES += [(a, 'empty') for a in ['inline_add', 'batch_delete', 'header', 'paste', 'modal_add']]


def action_handler(action):
    source = PAGE.read_text(encoding='utf-8')
    names = dict(row_delete='deleteDetailMaterialRow', inline_add='saveInlineMaterialRow', header='saveHeader', revert='revertOrder', copy='copyOrder', delete='deleteOrder', convert='convertToOutOrder', paste='processBatchPaste', modal_add='addItem')
    if action in names:
        handler = callback('in_order_detail', 'function ' + names[action] + '(')
        if action == 'delete':
            handler += '\n' + callback('in_order_detail', 'function doDeleteIn(')
        return handler, names[action]
    marker = {'batch_delete': "document.getElementById('batchDeleteBtn')", 'toolbar_delete': "document.querySelectorAll('.toolbar-btn-danger[data-id]')", 'excel': 'onSave: function(itemId'}[action]
    offset = source.index(marker)
    return 'var probe = ' + callback('in_order_detail', 'function(', offset), 'probe'


@pytest.mark.parametrize('action,scenario', CASES)
def test_inbound_detail_actions_preserve_transport_business_and_retry(action, scenario):
    handler, name = action_handler(action)
    handler = handler.replace('/fixture/0/', '7')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let sent=[],messages=[],timers=[],reloads=0,tabs=[],confirms=0,cancelled=0,cellSuccess=0;let scenario=p.scenario;
class FormData{constructor(form){this.fields=new Map(form?Object.entries({date:p.scenario==='empty'?'':'2026-10-22',supplier_id:'3',warehouse:'A',location:'A-1',remark:'header & note',business_type:'purchase',source_order_no:'PO-7'}):[]);}append(k,v){this.fields.set(k,String(v));}entries(){return this.fields.entries();}}
const values={code:' M&+ 中 ',qty:'3',price:'2.5',batchPasteContent:' M&+ 中\t3\t2.5 ','.material-code-field':' M&+ 中 ','.material-qty-field':'3','.material-price-field':'2.5','.material-remark-field':' note&+中 '};
const row={dataset:{id:'9'},classList:{contains:()=>false},querySelector:s=>({value:p.scenario==='empty'&&s==='.material-code-field'?'':values[s]})};
const btn={dataset:{id:'9'},disabled:false,closest:()=>row};
const ctx={FormData,Headers,document:{querySelector:()=>({content:'fixture-csrf'}),querySelectorAll:()=>p.scenario==='empty'?[]:[{value:'9'},{value:'10'}],getElementById:id=>id==='editHeaderForm'?{id}:({value:p.scenario==='empty'&&['code','batchPasteContent'].includes(id)?'':values[id]})},
showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>false,showToast:(m,t)=>messages.push({m,t}),setTimeout:fn=>timers.push(fn),location:{href:'original',reload(){reloads++;}},
fetch:(u,o)=>{sent.push({u,o});let s=scenario;if(s.startsWith('mixed_'))s=sent.length%2===1?'success':s.replace('mixed_','');const status=s==='http'?400:s==='html'?503:s==='expired401'?401:s==='expired419'?419:200;
const body=s==='malformed'?null:{status:['business','http'].includes(s)?'error':'success',msg:s==='business'?'已完成单据禁止删除':'fixture explanation',id:17,redirect_url:s==='fallback'?undefined:'/in_order/17?copied=1',out_order_id:23,out_order_no:'OUT-23',page:1,total_pages:2};
return s==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(s)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});}};
ctx.window=ctx;ctx.parent=p.scenario==='parent'?{WmsTabs:{open:(u,t)=>tabs.push({u,t})}}:{};
if(p.scenario==='cross_origin')Object.defineProperty(ctx,'parent',{get(){throw Error('cross origin');}});
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.handler.replace(/\{\{.*?\}\}/g,'7'),ctx);
let excel;
if(p.action==='excel'){
vm.runInContext(p.excel,ctx);excel=Object.create(ctx.ExcelTable.prototype);excel.options={onSave:ctx.probe};excel.showSuccess=()=>cellSuccess++;excel.showError=m=>messages.push({m,t:'danger'});excel.cancelEdit=()=>cancelled++;excel.updateAmount=()=>{};excel.selectCell=()=>{};
}
const cell={closest:()=>({querySelector:s=>({dataset:{value:s.includes('price')?'2.5':s.includes('remark')?'note':'3'},textContent:'note'})}),dataset:{value:'2'},classList:{remove(){}},innerHTML:'2'};
async function invoke(){
if(p.action==='excel')excel.saveCell(cell,9,'quantity',3,'2','2');
else if(p.action==='inline_add')ctx[p.name](btn);
else if(p.action==='row_delete')ctx[p.name](row);
else ctx[p.name].call(btn,7);
await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();
if(['cancel','empty'].includes(p.scenario)){assert.equal(sent.length,0);assert.equal(reloads,0);assert.equal(btn.disabled,false);return;}
assert.equal(sent.length,p.action==='batch_delete'?2:1);
const suffix={row_delete:'/delete_item/9',inline_add:'/item/add',header:'/update',revert:'/revert',copy:'/copy',delete:'/delete',convert:'/convert_to_out_order',paste:'/batch_add_items',modal_add:'/item/add',toolbar_delete:'/delete_item/9'};
for(const [i,req] of sent.entries()){assert.equal(req.u,p.action==='excel'?'/in_order/item/update':'/in_order/7'+(p.action==='batch_delete'?'/delete_item/'+(9+i):suffix[p.action]));const h=new Headers(req.o.headers);assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
if(['inline_add','modal_add','excel'].includes(p.action)){assert(req.o.body instanceof FormData);assert(!h.has('Content-Type'));const body=Object.fromEntries(req.o.body.entries());if(p.action==='excel')assert.deepEqual(body,{id:'9',quantity:'3',price:'2.5',remark:'note'});else{assert.equal(body.material_code,'M&+ 中');assert.equal(body.quantity,'3');assert.equal(body.price,'2.5');if(p.action==='inline_add')assert.equal(body.remark,'note&+中');}}
else if(['header','copy','paste'].includes(p.action)){const b=JSON.parse(req.o.body);assert.equal(typeof b,'object');if(p.action==='header')assert.deepEqual(b,{date:'2026-10-22',supplier_id:'3',warehouse:'A',location:'A-1',remark:'header & note',business_type:'purchase',source_order_no:'PO-7'});else if(p.action==='copy')assert.deepEqual(b,{});else assert.deepEqual(b,{content:'M&+ 中\t3\t2.5'});}}
const success=['success','fallback','parent','cross_origin'].includes(p.scenario);
if(p.action==='batch_delete'){
 assert.equal(messages.length,1,'completed callback fires once even for malformed response');
 assert.equal(messages[0].t,success?'success':p.scenario.startsWith('mixed_')||['business','malformed'].includes(p.scenario)?'warning':'danger');
 timers.forEach(fn=>fn());assert.equal(reloads,1,'batch refreshes once to reflect possible partial success');return;}
if(success){assert(messages.some(m=>m.t==='success')||p.action==='excel');timers.forEach(fn=>fn());
 if(p.action==='excel'){assert.equal(cellSuccess,1);assert.equal(cell.dataset.value,3);assert.equal(cancelled,0);}
 else if(p.action==='copy')assert.equal(ctx.location.href,p.scenario==='fallback'?'/in_order/17':'/in_order/17?copied=1');
 else if(p.action==='delete'){if(p.scenario==='parent')assert.equal(tabs[0].u,'/in_order');else assert.equal(ctx.location.href,'/in_order');}
 else if(p.action==='convert'){if(p.scenario==='parent'){assert.equal(tabs[0].u,'/out_order/23');assert(tabs[0].t.includes('OUT-23'));}else assert.equal(ctx.location.href,'/out_order/23');}
 else assert.equal(reloads,1);
}else{assert(messages.some(m=>m.t==='danger'),'failure visible');assert.equal(reloads,0);assert.equal(ctx.location.href,'original');assert.equal(tabs.length,0);if(p.action==='inline_add')assert.equal(btn.disabled,false);if(p.action==='excel')assert.equal(cancelled,1);if(['business','http'].includes(p.scenario))assert(messages.some(m=>m.m.includes(p.scenario==='business'?'已完成单据禁止删除':'fixture explanation')));if(p.scenario==='html')assert(messages.some(m=>m.m.includes('503')));
scenario='success';await invoke();assert.equal(sent.length,2,'failure permits retry');assert(messages.some(m=>m.t==='success')||cellSuccess===1);}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node is required'
    payload = dict(action=action, scenario=scenario, handler=handler, name=name,
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
                   excel=(ROOT / 'app/static/js/excel-table.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
