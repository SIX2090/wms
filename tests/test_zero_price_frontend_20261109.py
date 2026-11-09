"""Execute actual price-fill consumers, with all DOM and business I/O synthetic."""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    'opening': ('app/static/js/pages/opening-stock.js', 'selectMaterial'),
    'request': ('app/templates/purchase_request_add.html', 'fillRowData'),
    'in_add': ('app/templates/in_order_add.html', 'fillMaterialFields'),
    'out_add': ('app/templates/out_order_add.html', 'fillMaterialFields'),
    'in_detail': ('app/templates/in_order_detail.html', 'fillAddMaterialInfo'),
    'out_modal': ('app/templates/out_order_detail.html', 'fillAddMaterialInfo'),
    'out_inline': ('app/templates/out_order_detail.html', 'fillInlineMaterialInfo'),
    'receive': ('app/templates/subcontract_receive.html', 'bindMaterialInput'),
}
CASES = [(kind, value, 5, False) for kind in TARGETS for value in ('0', '', '2')]
CASES += [(kind, '', 0, False) for kind in TARGETS]
CASES += [(kind, value, 5, False) for kind in ('opening', 'request') for value in (0, None)]
CASES += [(kind, '0', 5, True) for kind in ('in_add', 'out_add')]
assert len(CASES) == 38

PROGRAM = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const price={value:p.initial==null?'':String(p.initial),dataset:{}};
const quantity={value:'7',dataset:{}},fields={};
function field(selector){
 if(selector.includes('price'))return price;
 if(selector.includes('quantity')||selector.includes('-qty'))return quantity;
 return fields[selector]??={value:'',dataset:{},style:{}};
}
const row={querySelector:field},material={id:1,code:'B-M',name:'合成物料',spec:'规格',unit:{id:1,name:'件'},stock:10,price:p.material};
let handler,calculations=0,renders=0,drafts=0;
const inputNode={value:'B-M'};
const jqRow={find(selector){const node=selector==='.material-input'?inputNode:field(selector);return{val(value){if(arguments.length){node.value=value;return this;}return node.value;}};}};
const jqInput={val:()=>inputNode.value,closest:()=>jqRow};
const jqRoot={find(selector){assert.equal(selector,'.material-input');return{on(event,callback){assert.equal(event,'input');handler=callback;}};}};
const context={document:{querySelector:field,getElementById:field},materialCache:new Map([[1,material]]),
 rows:[{line_id:7,material_id:1,quantity:7,price:p.initial,warehouse_id:3}],
 closeMaterialMenu(){},renderRows(){renders++;},scheduleDraftSave(){drafts++;},
 formatStock:value=>Number(value).toFixed(2),getMaterialUnit:()=> '件',fillPurposeFromMaterial(){},
 calcInlineRowAmount(){calculations++;},materialsCache:[material],
 WMS:{subcontractMaterialSelection:{choose:()=>material}},$node:null,
 $(node){assert.equal(node,inputNode);return jqInput;},
 fetch(){assert.fail('No HTTP is permitted in this DOM test');}};
context.window=context;vm.createContext(context,{codeGeneration:{strings:false,wasm:false}});
vm.runInContext(p.source,context,{timeout:1000});
if(p.kind==='opening')context.selectMaterial(0,1);
else if(p.kind==='request')context.fillRowData(row,{material_id:1,material_code:'B-M',quantity:7,estimated_price:p.initial,price:p.material});
else if(p.kind==='in_add'||p.kind==='out_add')context.fillMaterialFields(row,material,{forcePrice:p.force});
else if(p.kind==='in_detail')context.fillAddMaterialInfo(material,row);
else if(p.kind==='out_modal')context.fillAddMaterialInfo(material);
else if(p.kind==='out_inline')context.fillInlineMaterialInfo(row,material);
else{context.bindMaterialInput(jqRoot);assert.equal(typeof handler,'function');handler.call(inputNode);}
const missing=p.initial===null||p.initial===undefined||p.initial==='';
const expected=p.force||missing?p.material:Number(p.initial);
const actual=p.kind==='opening'?context.rows[0].price:price.value;
assert.notEqual(actual,'','A valid zero price must be displayed explicitly');
assert.equal(Number(actual),expected,'An explicit price cannot be replaced by a material default');
assert.equal(Number(quantity.value),7,'Price fill must not change the document quantity');
assert.equal(context.rows[0].quantity,7);
if(p.kind==='opening'){assert.equal(renders,1);assert.equal(drafts,1);assert.equal(context.rows[0].line_id,7);}
if(p.kind==='in_detail'||p.kind==='out_inline')assert.equal(calculations,1);
'''


@pytest.mark.parametrize('kind,initial,material,force', CASES)
def test_zero_price_survives_each_actual_consumer_and_blank_still_defaults(kind, initial, material, force):
    runpy.run_path(str(ROOT / 'scripts/verify_db_guard.py'))['require_owned_test_profile']()
    assert all(os.environ.get(key) == 'sqlite:///:memory:' for key in ('DATABASE_URL', 'WMS_DATABASE_URI'))
    relative, name = TARGETS[kind]
    text = (ROOT / relative).read_text(encoding='utf-8-sig')
    functions = re.findall(r'^function ' + re.escape(name) + r'\b[\s\S]*?^}', text, re.M)
    assert len(functions) == 1, (relative, name)
    payload = dict(kind=kind, initial=initial, material=material, force=force, source=functions[0])
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, '--disable-proto=throw', '-e', PROGRAM], input=json.dumps(payload),
                            text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('row_index', [0, 1])
def test_unselected_receive_rows_use_blank_price_so_defaults_remain_unambiguous(row_index):
    text = (ROOT / 'app/templates/subcontract_receive.html').read_text(encoding='utf-8-sig')
    tags = re.findall(r'<input\b[^>]*\bname="price"[^>]*>', text)
    assert len(tags) == 2
    assert 'value=""' in tags[row_index]
