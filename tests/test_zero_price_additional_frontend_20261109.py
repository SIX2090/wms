"""Run further real consumers found by the WMS-wide zero-price search."""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALUES = [0, '0', '', None, '2']
CASES = [(kind, value, price) for kind in ('after_select', 'po_fill', 'receive_modal')
         for value in VALUES for price in (0, 5)]
CASES += [(kind, value, 5) for kind in ('after_fill', 'po_add') for value in VALUES]
assert len(CASES) == 40

PROGRAM = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
function node(value=''){let text=String(value);return{get value(){return text;},set value(v){text=String(v);},dataset:{},style:{},focus(){},select(){}};}
const price=node(p.initial==null?'':p.initial),qty=node('7'),fields={};
function field(selector){if(/price/i.test(selector))return price;if(/qty|quantity/i.test(selector))return qty;return fields[selector]??=node();}
const row={querySelector:field};
Object.defineProperty(row,'innerHTML',{set(html){const tag=html.match(/<input\b[^>]*class="[^"]*material-price[^>]*>/);assert(tag);price.value=tag[0].match(/\bvalue="([^"]*)"/)[1];}});
const material={id:1,code:'S-ZERO',name:'合成物料',price:p.material,stock:10,unit:{id:1,name:'件'}};
let appended=0,calcs=0;
const context={document:{getElementById:id=>id==='materialTableBody'?{appendChild(r){assert.equal(r,row);appended++;}}:field(id),createElement:()=>row},
 materials:[material],getMaterialUnit:()=> '件',escapeHtml:value=>String(value),
 bindRow(){},calcAmount(r){assert.equal(r,row);calcs++;},renumberRows(){},activeDropdown:null};
context.window=context;vm.createContext(context,{codeGeneration:{strings:false,wasm:false}});
vm.runInContext(p.source,context,{timeout:1000});
const missing=p.initial===null||p.initial==='';
let expected=missing?p.material:Number(p.initial);
if(p.kind==='after_select')context.selectMaterial(row,material.code);
else if(p.kind==='po_fill')context.fillMaterial(row,material);
else if(p.kind==='receive_modal')context.receiveProbe(material);
else if(p.kind==='after_fill'){context.fillRowData(row,{material_code:material.code,quantity:7,price:p.initial});expected=missing?'':Number(p.initial);}
else{const actual=context.addNewRow({material_id:1,material_code:material.code,quantity:7,price:p.initial});assert.equal(actual,row);assert.equal(appended,1);assert.equal(calcs,1);expected=missing?'':Number(p.initial);}
if(expected==='')assert.equal(price.value,'','Absent saved price stays absent');
else{assert.notEqual(price.value,'','An explicit zero must stay visible');assert.equal(Number(price.value),expected,'Real fill must preserve an explicit price');}
assert.equal(Number(qty.value),7,'Price actions cannot change quantity');
'''


@pytest.mark.parametrize('kind,initial,material', CASES)
def test_further_actual_consumers_keep_zero_and_missing_defaults(kind, initial, material):
    runpy.run_path(str(ROOT / 'scripts/verify_db_guard.py'))['require_owned_test_profile']()
    assert all(os.environ.get(key) == 'sqlite:///:memory:' for key in ('DATABASE_URL', 'WMS_DATABASE_URI'))
    if kind == 'receive_modal':
        text = (ROOT / 'app/templates/subcontract_detail.html').read_text(encoding='utf-8-sig')
        matches = re.findall(r"const receiveSearch = bindScMaterialInput\('receiveCode', 'receiveCodeDropdown', (function\(m\) \{[\s\S]*?\n    \})\);", text)
        assert len(matches) == 1
        source = 'var receiveProbe = ' + matches[0] + ';'
    else:
        page = 'after_sale_out_add' if kind.startswith('after_') else 'purchase_order_add'
        name = {'after_fill':'fillRowData','after_select':'selectMaterial','po_fill':'fillMaterial','po_add':'addNewRow'}[kind]
        text = (ROOT / ('app/templates/' + page + '.html')).read_text(encoding='utf-8-sig')
        matches = re.findall(r'^function ' + name + r'\b[\s\S]*?^}', text, re.M)
        assert len(matches) == 1
        source = matches[0]
    executable = shutil.which('node')
    assert executable, 'Real Node execution required'
    result = subprocess.run([executable, '--disable-proto=throw', '-e', PROGRAM],
        input=json.dumps(dict(kind=kind, initial=initial, material=material, source=source)),
        text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
