"""Execute document guards: feedback, focus, and unchanged submission/bulk edits."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.index('function ' + name + '(')
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


def run(page, action, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    payload = dict(page=page, action=action, scenario=scenario, source=function(source, action))
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);
let focused='',messages=[],alerts=0,calls=[],removed=false,calcs=0;
function input(key,value){return {value,style:{},focus(){focused=key;},options:[]};}
const fields={};Object.entries({date:'2026-10-21',customer:'Acme',department_id:'3',warehouse_id:'2',location:'A',order_id:'',order_no:'TEST',business_type:'领料单',picker:'Tester',remark:'Note'}).forEach(([k,v])=>fields[k]=input(k,v));
const ids={sourceInOrderNo:input('source','IN-1'),sourceInOrderId:input('sourceId','7'),batchUpdateField:input('batchField','quantity'),batchUpdateValue:input('batchValue','5'),batchUpdateWarehouse:input('batchWarehouse','2'),batchUpdateModal:{remove(){removed=true;}}};
const line={};Object.entries({'.material-code':'M1','.material-qty':'2','.material-price':'1','.line-contract-no':'C1','.line-project-name':'P1','.material-remark':'R1','.line-source-in-item-id':'9','.material-batch-no':'old','.material-expiry':'2026-12-01'}).forEach(([k,v])=>line[k]=input(k,v));
const row={querySelector:s=>line[s]||null};let rows=[row];
let sale=false,purchase=false,other=false;
const expected={date:'date',customer:'customer',supplier:'customer',department:'department_id',source:'source',quantity:'.material-qty',empty:'.material-code',warehouse:'warehouse_id',location:'location',batchWarehouse:'batchWarehouse',batchField:'batchField',batchEmpty:'batchValue',batchNaN:'batchValue',batchQuantity:'batchValue',batchPrice:'batchValue',batchPrecision:'batchValue',batchLength:'batchValue',batchFormula:'batchValue',batchExpiry:'batchValue'};
switch(p.scenario){
case 'date':fields.date.value='';break;
case 'customer':sale=true;fields.customer.value='';break;
case 'supplier':purchase=true;fields.customer.value='';break;
case 'department':fields.department_id.value='';break;
case 'source':purchase=true;ids.sourceInOrderNo.value='';ids.sourceInOrderId.value='';break;
case 'quantity':line['.material-qty'].value='0';break;
case 'empty':line['.material-code'].value='';break;
case 'warehouse':fields.warehouse_id.value='';break;
case 'location':fields.location.value='';break;
case 'batchWarehouse':ids.batchUpdateField.value='warehouse';ids.batchUpdateWarehouse.value='';break;
case 'batchField':ids.batchUpdateField.value='unknown';break;
case 'batchEmpty':ids.batchUpdateValue.value='';break;
case 'batchNaN':ids.batchUpdateValue.value='abc';break;
case 'batchQuantity':ids.batchUpdateValue.value='0';break;
case 'batchPrice':ids.batchUpdateField.value='price';ids.batchUpdateValue.value='-1';break;
case 'batchPrecision':ids.batchUpdateValue.value='1.234';break;
case 'batchLength':ids.batchUpdateField.value='batch_no';ids.batchUpdateValue.value='x'.repeat(51);break;
case 'batchFormula':ids.batchUpdateField.value='batch_no';ids.batchUpdateValue.value='=1';break;
case 'batchExpiry':ids.batchUpdateField.value='expiry_date';ids.batchUpdateValue.value='bad';break;
case 'validWarehouse':ids.batchUpdateField.value='warehouse';break;
case 'validPrice':ids.batchUpdateField.value='price';ids.batchUpdateValue.value='0';break;
case 'validPurchase':purchase=true;break;
case 'validSale':sale=true;break;
case 'validOther':other=true;fields.department_id.value='';break;
case 'validNoLocation':delete fields.location;break;
}
// The purchase-return branch does not render a picker input.
if(purchase)delete fields.picker;
const initial=JSON.stringify(Object.fromEntries(Object.entries(line).map(([k,v])=>[k,v.value])));
const document={querySelector:s=>{const m=s.match(/name="([^"]+)"/);return m?fields[m[1]]||null:s==='#materialTableBody .material-code'?line['.material-code']:null;},querySelectorAll:s=>s==='#materialTableBody tr'?rows:[],getElementById:id=>ids[id]||null};
const ctx={document,isSaleOrder:sale,isPurchaseReturn:purchase,isOtherOut:other,purchaseReturnRequiresOrder:true,outOrderSubmitting:false,returnAddUrl:'/out_order/add',window:{location:{href:'original'}},showToast:(m,t)=>messages.push({m,t}),alert:()=>alerts++,confirm:()=>true,calcAmount:()=>calcs++,calcTotal:()=>calcs++,WMS:{api:{postRaw:(url,data)=>{calls.push({url,data});return Promise.resolve({status:'success',id:8});}}}};
vm.createContext(ctx);vm.runInContext(p.source,ctx);
(async()=>{await ctx[p.action]();await new Promise(r=>setImmediate(r));
assert.equal(alerts,0,'no blocking native alert');
if(expected[p.scenario]){
 assert.equal(calls.length,0,'invalid input must never submit');assert.equal(removed,false,'keep modal open');assert.equal(calcs,0,'invalid bulk edit must not recalculate');
 assert.equal(JSON.stringify(Object.fromEntries(Object.entries(line).map(([k,v])=>[k,v.value]))),initial,'invalid input must preserve line values');
 assert.equal(messages.length,1);assert.equal(messages[0].t,'danger');assert.equal(focused,expected[p.scenario]);
}else if(p.action==='applyBatchUpdate'){
 assert.equal(removed,true);assert.equal(calls.length,0);
 if(p.scenario==='validWarehouse')assert.equal(fields.warehouse_id.value,'2');
 else {assert.equal(line[p.scenario==='validPrice'?'.material-price':'.material-qty'].value,p.scenario==='validPrice'?'0.00':'5.00');assert.equal(calcs,2);}
}else {
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/out_order/add');const d=calls[0].data;
 assert.equal(d.warehouse_id,'2');assert.equal(d.date,'2026-10-21');assert.equal(d.customer,'Acme');assert.equal(d.items.length,1);assert.equal(d.items[0].quantity,2);assert.equal(d.items[0].price,1);assert.equal(d.items[0].contract_no,'C1');assert.equal(d.items[0].project_name,'P1');assert.equal(d.items[0].remark,'R1');
 if(purchase){assert.equal(d.picker,'');assert.equal(d.source_in_order_id,'7');assert.equal(d.items[0].source_in_order_item_id,'9');}
 else assert.equal(d.picker,'Tester');
 assert.equal(d.location,p.scenario==='validNoLocation'?'':'A');assert.equal(ctx.window.location.href,'/out_order/8');
}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('scenario', ['date', 'customer', 'supplier', 'department', 'source', 'quantity', 'empty', 'warehouse', 'location', 'valid', 'validPurchase', 'validSale', 'validOther', 'validNoLocation'])
def test_outbound_validation_and_original_payload(scenario):
    run('out', 'submitForm', scenario)


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('scenario', ['batchWarehouse', 'batchField', 'batchEmpty', 'batchNaN', 'batchQuantity', 'batchPrice', 'batchPrecision', 'valid', 'validPrice', 'validWarehouse'])
def test_bulk_validation_preserves_lines_and_focus(page, scenario):
    run(page, 'applyBatchUpdate', scenario)


@pytest.mark.parametrize('scenario', ['batchLength', 'batchFormula', 'batchExpiry'])
def test_inbound_extra_bulk_guards(scenario):
    run('in', 'applyBatchUpdate', scenario)


@pytest.mark.parametrize('page', ['in', 'out'])
def test_bulk_overlay_leaves_common_feedback_visible(page):
    source = (ROOT / f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    body = function(source, 'batchUpdateField')
    assert 'alert(' not in body
    overlay = int(re.search(r'z-index:(\d+)', body).group(1))
    from tests.frontend_page_source import page_style_source
    base = page_style_source(ROOT / 'app/templates/base.html')
    toast = int(re.search(r'\.cb-toast-stack\s*\{[^}]*z-index:\s*(\d+)', base).group(1))
    assert 1055 < overlay < toast
