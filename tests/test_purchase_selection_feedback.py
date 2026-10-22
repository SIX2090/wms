"""Run both purchase-selection handlers without changing source or quantity guards."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/templates/in_order_add.html'


def function(source, name):
    start = source.index('function ' + name + '(')
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(name)


@pytest.mark.parametrize('action', ['applyPurchaseOrderSelectionToForm', 'createInOrderFromPurchaseOrderSelection'])
@pytest.mark.parametrize('scenario', ['empty', 'zero', 'nan', 'over', 'valid'])
def test_selection_feedback_and_original_values(action, scenario):
    execute(action, scenario)


@pytest.mark.parametrize('scenario', ['mixed', 'failure', 'network'])
def test_cross_supplier_and_generation_errors(scenario):
    execute('applyPurchaseOrderSelectionToForm' if scenario == 'mixed' else 'createInOrderFromPurchaseOrderSelection', scenario)


def execute(action, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    payload = {'action': action, 'scenario': scenario, 'source': function(SOURCE.read_text(encoding='utf-8'), action)}
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);let messages=[],alerts=0,focused='',calls=[],removed=false,lines=[],header=null;
function input(id,value){return {value,focus(){focused=id;},getAttribute:()=> '5'};}
const qty=input('quantity',p.scenario==='zero'?'0':p.scenario==='nan'?'abc':p.scenario==='over'?'6':'2');
const selected={dataset:{itemId:'11'},focus(){focused='selection';},closest:()=>({querySelector:()=>qty})};
let checked=p.scenario==='empty'?[]:[selected];
const source={purchase_order_item_id:11,purchase_order_no:'PO-11',supplier_id:3,supplier_name:'Supplier',material_code:'M1',material_name:'Material',unit:'pc',price:4};
const map=new Map([['11',source]]);
if(p.scenario==='mixed'){map.set('12',{...source,supplier_id:4});checked.push({...selected,dataset:{itemId:'12'}});}
function addNewRow(){const values={};lines.push({dataset:{},querySelector:s=>values[s]||(values[s]=input(s,''))});}
const remark=input('remark','');const fields={warehouse_id:input('warehouse','2'),remark};
const body={querySelectorAll:()=>[]};
const document={querySelectorAll:()=>checked,querySelector:s=>s.includes('tr:last-child')?lines.at(-1):s.includes('.po-select-row')?selected:fields[s.match(/name="([^"]+)"/)?.[1]]||null,getElementById:id=>id==='materialTableBody'?body:id==='purchaseOrderSelectModal'?{remove(){removed=true;}}:null};
const ctx={document,purchaseOrderSelectableMap:map,showToast:(m,t)=>messages.push({m,t}),alert:()=>alerts++,findEmptyRow:()=>null,addNewRow,findMaterialByCode:()=>null,formatQtyTrim:String,formatPurchaseQty:n=>Number(n).toFixed(2),calcAmount(){},renumberRows(){},calcTotal(){},setHeaderSupplier:(id,name)=>header={id,name},location:{href:'original'},fetch:(url,opts)=>{calls.push({url,opts});return p.scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:true,json:()=>Promise.resolve(p.scenario==='failure'?{status:'error',msg:'fixture failure'}:{status:'success',id:9,redirect_url:'/in_order/9'})});}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.source,ctx);
(async()=>{ctx[p.action]();await new Promise(r=>setImmediate(r));assert.equal(alerts,0,'no blocking native alert');
const invalid=['empty','zero','nan','over','mixed'].includes(p.scenario);
if(invalid){assert.equal(calls.length,0);assert.equal(lines.length,0);assert.equal(header,null);assert.equal(removed,false);assert.equal(messages.length,1);assert.equal(messages[0].t,'danger');assert(focused,'focus input or selection');assert.equal(ctx.location.href,'original');}
else if(p.action==='applyPurchaseOrderSelectionToForm'){
 assert.equal(calls.length,0,'bringing lines in never saves automatically');assert.equal(lines.length,1);assert.equal(lines[0].querySelector('.material-qty').value,'2');assert.equal(lines[0].querySelector('.material-price').value,'4.00');assert.equal(lines[0].dataset.sourcePurchaseOrderItemId,11);assert.equal(lines[0].dataset.sourcePurchaseOrderNo,'PO-11');assert.deepEqual(header,{id:3,name:'Supplier'});assert.equal(removed,true);
}else {assert.equal(calls.length,1);assert.equal(calls[0].url,'/purchase_order/create_in_order_from_selection');const d=JSON.parse(calls[0].opts.body);assert.deepEqual(d,{warehouse_id:'2',remark:'',items:[{purchase_order_item_id:'11',quantity:2}]});
 if(p.scenario==='valid')assert.equal(ctx.location.href,'/in_order/9');else {assert.equal(ctx.location.href,'original');assert.equal(messages.length,1);assert.equal(messages[0].t,'danger');assert(messages[0].m.includes(p.scenario==='network'?'offline':'fixture failure'));}}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_purchase_modal_does_not_cover_common_feedback():
    body = function(SOURCE.read_text(encoding='utf-8'), 'showPurchaseOrderSelectModal')
    z = int(re.search(r'z-index:(\d+)', body).group(1))
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    toast = int(re.search(r'\.cb-toast-stack\s*\{[^}]*z-index:\s*(\d+)', base).group(1))
    assert 1055 < z < toast
