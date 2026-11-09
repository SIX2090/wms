"""BUG-2026-11-01-031: execute real quantity listeners, including inserted rows."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tests.frontend_page_source import page_source
from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['in_order_add', 'out_order_add', 'document_table_form', 'adjustment_add']
CASES = [('0.015', '0.02'), ('0.005', '0.01'), ('1.005', '1.01'),
         ('2.675', '2.68'), ('0.0049', '0.00'), ('0.0149', '0.01'),
         ('1.999', '2.00'), ('2', '2.00'), ('0.25', '0.25'), ('0', '0.00')]


def listeners(page, event, kind):
    source = page_source(ROOT / f'app/templates/{page}.html')
    field = '.adjust-qty' if page == 'adjustment_add' else '.material-' + ('qty' if kind == 'quantity' else 'price')
    marker = (r"(?:row|newRow)\.querySelector\('" + re.escape(field) + r"'\)\.addEventListener\('" + event + "', "
              if page != 'document_table_form' else re.escape(f"input.addEventListener('{event}', "))
    offsets = [m.end() for m in re.finditer(marker, source)]
    assert offsets, (page, event)
    return [callback(page, 'function()', offset) for offset in offsets]


@pytest.mark.parametrize('page,kind', [(page, 'quantity') for page in PAGES] +
                         [(page, 'price') for page in PAGES if page != 'adjustment_add'])
@pytest.mark.parametrize('original,expected', CASES)
def test_real_input_and_blur_preserve_typing_then_round_with_feedback(page, kind, original, expected):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    helper = ROOT / 'app/static/js/decimal-input.js'
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    support = '\n'.join(callback(page, f'function {name}(')
                        for name in ('formatQty', 'trimDecimalInput') if f'function {name}(' in source)
    if page == 'in_order_add':
        support += '\n' + callback(page, 'function formatQtyTrim(')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
const fs=require('node:fs');
for(let i=0;i<p.inputs.length;i++) {
 const messages=[],row={dataset:{},closest(){return this;}},input={value:'',classList:{contains:n=>n===(p.kind==='price'?'line-price':'actual-stock')}};
 const ctx={row,newRow:row,calcAmount(){},calcRow(){},calcTotal(){},showToast:(...x)=>messages.push(x)};
 ctx.window=ctx;ctx.WMS={};vm.createContext(ctx);
 if(fs.existsSync(p.helper))vm.runInContext(fs.readFileSync(p.helper,'utf8'),ctx);
 vm.runInContext(p.support,ctx);
 const onInput=vm.runInContext('('+p.inputs[i]+')',ctx);
 const onBlur=vm.runInContext('('+p.blurs[i]+')',ctx);
 // Actual key-by-key input: no loss while the operator is still typing.
 for(const ch of p.original) {input.value+=ch;onInput.call(input);}
 assert.equal(input.value,p.original,'input event must preserve every typed digit');
 assert.equal(messages.length,0,'do not interrupt typing');
 onBlur.call(input);
 assert.equal(Number(input.value),Number(p.expected),'same decimal rounding as backend');
 if(p.page==='in_order_add'&&p.kind==='quantity')assert.equal(input.value,String(Number(p.expected)),'retain integer/no-padding UX');
 else assert.equal(input.value,p.expected);
 const changed=Number(p.original)!==Number(p.expected);
 assert.equal(messages.length,changed?1:0,'changed quantities need explicit feedback');
 if(changed){assert.ok(messages[0][0].includes(p.original));assert.ok(messages[0][0].includes(input.value));assert.ok(messages[0][0].includes(p.kind==='price'?'单价':'数量'));}
 onBlur.call(input);assert.equal(messages.length,changed?1:0,'blur twice must not warn twice');
}
'''
    result = subprocess.run([node, '-e', program, json.dumps(dict(
        page=page, kind=kind, original=original, expected=expected, helper=str(helper), support=support,
        inputs=listeners(page, 'input', kind), blurs=listeners(page, 'blur', kind)))],
        text=True, capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('original,expected', [('-0.005', '-0.01'), ('-1.005', '-1.01'),
                                            ('5e-3', '0.01'), ('', ''), ('bad', 'bad')])
def test_decimal_normalizer_boundaries_and_readonly_protection(original, expected):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    program = r'''
const assert=require('node:assert/strict');global.window=global;let messages=[];
global.showToast=(...x)=>messages.push(x);require(process.argv[1]);
const p=JSON.parse(process.argv[2]),input={value:p.original};
WMS.normalizeDecimalInput(input);assert.equal(input.value,p.expected);
for(const key of ['readOnly','disabled']) {
 const control={value:'0.015',[key]:true};WMS.normalizeDecimalInput(control);
 assert.equal(control.value,'0.015','never rewrite a readonly/disabled quantity');
}
'''
    result = subprocess.run([node, '-e', program, str(ROOT / 'app/static/js/decimal-input.js'),
                             json.dumps(dict(original=original, expected=expected))],
                            text=True, capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('kind', ['bom', 'transfer', 'requisition', 'check', 'adjustment'])
@pytest.mark.parametrize('original,expected', CASES[:3])
def test_collection_rounds_unblurred_quantity_before_serializing(kind, original, expected):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    page = 'adjustment_add' if kind == 'adjustment' else 'document_table_form'
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
const fields={};for(const name of ['material-code','unit-id','line-qty','actual-stock','system-stock',
 'line-price','line-area','line-reason','line-usage','line-remark','adjust-qty','adjust-location','adjust-reason']) {
 fields['.'+name]={value:['line-qty','actual-stock','adjust-qty'].includes(name)?p.original:
   name==='system-stock'?'123.4567':name==='material-code'?'M1':name==='unit-id'?'1':name==='line-price'?'0':'',style:{}};
}
if(p.kind==='check')delete fields['.line-qty'];else delete fields['.actual-stock'];
const row={dataset:{counted:'true'},querySelector:s=>fields[s]||null};let messages=[];
const ctx={docType:p.kind,checkLocationRequired:false,document:{querySelectorAll:()=>[row]},
 findMaterialByCode:()=>({id:1,code:'M1',price:7}),getMaterialUnitId:()=>1,
 showToast:(...m)=>messages.push(m)};ctx.window=ctx;vm.createContext(ctx);
vm.runInContext(p.helper+'\n'+p.collect,ctx);
const result=JSON.parse(JSON.stringify(ctx.collectItems()));
assert.deepEqual(result.invalidRows,[]);assert.equal(result.items.length,1);
assert.equal(result.items[0][p.kind==='check'?'actual_stock':'quantity'],Number(p.expected));
if(p.kind==='check')assert.equal(result.items[0].system_stock,123.4567,'do not round the system-stock baseline');
assert.equal(messages.length,1,'unblurred changed quantity must also warn on save');
'''
    result = subprocess.run([node, '-e', program, json.dumps(dict(kind=kind, original=original,
        expected=expected, helper=(ROOT / 'app/static/js/decimal-input.js').read_text(encoding='utf-8'),
        collect=callback(page, 'function collectItems()')))], text=True, capture_output=True, encoding='utf-8')
    assert result.returncode == 0, result.stdout + result.stderr
