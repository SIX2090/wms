import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('page',['in','out'])
@pytest.mark.parametrize('case',['focus','pointer','first','blank_previous','no_selection','deleted','zero_price'])
def test_copy_previous_fills_selected_row_without_insertion(page,case):
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    source=(ROOT/f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    helpers='function copyValuesToRow'+source.split('function copyValuesToRow',1)[1].split('function insertRowBefore',1)[0]
    tracker=source[source.index('let currentMaterialRow = null;'):source.index('function copyValuesToRow')] if 'let currentMaterialRow = null;' in source else ''
    script=r'''
const assert=require('node:assert/strict');let focused=null,toasts=[];const events={};
function makeRow(){const fields={};return {dataset:{},querySelector(s){return fields[s] ||= {value:'',checked:false,focus(){focused=this;},select(){}};}};}
const rows=[makeRow(),makeRow(),makeRow(),makeRow()];
rows.forEach((r,i)=>Object.defineProperty(r,'previousElementSibling',{get(){return rows[i-1]||null;}}));
const src=rows[0],dst=rows[1],unrelated=rows[3];
const fields=['material-code','material-brand','material-name','material-spec','material-unit','material-stock',
 'material-qty','material-price','line-contract-no','line-project-name','material-remark',
 ...(PAGE==='in'?['material-batch-no','material-expiry']:['line-source-in-item-id'])];
fields.forEach((f,i)=>{src.querySelector('.'+f).value=String(i);dst.querySelector('.'+f).value='old';});
src.querySelector('.material-code').value='PREVIOUS';src.querySelector('.material-price').value=CASE==='zero_price'?'0.00':'6.50';
src.querySelector('.line-customer-supplied').checked=true;
src.dataset={sourcePurchaseOrderItemId:'9',sourcePurchaseOrderNo:'PO9'};
unrelated.querySelector('.material-code').value='LAST-FILLED';
const document={getElementById(){return {contains(row){return rows.includes(row);}};},
 addEventListener(name,fn){events[name]=fn;},querySelectorAll(){return rows;},querySelector(){return rows.at(-1);}};
function showToast(message){toasts.push(message);}
function calcAmount(){}
function findMaterialByCode(){return {price:12};}
function fillMaterialFields(r){r.querySelector('.material-price').value='12.00';}
function addNewRow(){throw new Error('Must not insert a row');}
function insertRowBefore(){throw new Error('Must not insert a row');}
function findEmptyRow(){return rows[2];}
''' .replace('PAGE',json.dumps(page)).replace('CASE',json.dumps(case))+tracker+helpers+r'''
const before=fields.map(f=>dst.querySelector('.'+f).value);
if(CASE!=='no_selection'){
 const chosen=CASE==='first'?src:dst;
 const select=events[CASE==='pointer'?'pointerdown':'focusin'];
 if(select)select({target:{closest(){return chosen;}}});
}
if(CASE==='blank_previous')src.querySelector('.material-code').value='';
if(CASE==='deleted')rows.splice(1,1);
// Clicking toolbar changes focus, but must retain the last selected detail row.
if(events.focusin)events.focusin({target:{closest(){return null;}}});
const count=rows.length;
copyPreviousRow();assert.equal(rows.length,count);assert.equal(unrelated.querySelector('.material-code').value,'LAST-FILLED');
if(['focus','pointer','zero_price'].includes(CASE)){
 fields.forEach(f=>assert.equal(dst.querySelector('.'+f).value,src.querySelector('.'+f).value,f));
 if(PAGE==='in'){assert.deepEqual(dst.dataset,src.dataset);assert.equal(dst.querySelector('.line-customer-supplied').checked,true);}
 assert.equal(focused,dst.querySelector('.material-qty'));assert.equal(toasts.length,0);
}else{
 assert.deepEqual(fields.map(f=>dst.querySelector('.'+f).value),before);assert.equal(toasts.length,1);
}
'''.replace('PAGE',json.dumps(page)).replace('CASE',json.dumps(case))
    subprocess.run([node,'-e',script],text=True,encoding='utf-8',capture_output=True,check=True)
