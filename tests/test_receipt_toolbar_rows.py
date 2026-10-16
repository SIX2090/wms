"""Execute receipt toolbar row helpers against DOM fixtures."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('price', ['0.00', '6.50'])
@pytest.mark.parametrize('cached', [True, False])
@pytest.mark.parametrize('page', ['in', 'out'])
def test_row_menu_copy_preserves_all_fields_and_inserts_next_to_source(price, cached, page):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    helpers = 'function copyValuesToRow' + source.split('function copyValuesToRow', 1)[1].split('function insertRowBefore', 1)[0]
    script = r'''
const assert=require('node:assert/strict');
let focused=null;
function makeRow() {
    const values={};
    return {values, dataset:{},querySelector(s) {
        return values[s] ||= {value:'',checked:false,focus(){focused=this;},select(){}};
    },querySelectorAll(){return Object.values(values);}};
}
let rows=[makeRow(),makeRow(),makeRow()];
Object.defineProperty(rows[0],'nextElementSibling',{get(){return rows[1];}});
const src=rows[0];
const fields=['material-code','material-brand','material-name','material-spec','material-unit','material-stock',
              'material-qty','material-price','line-contract-no','line-project-name','material-remark',
              ...(PAGE==='in' ? ['material-batch-no','material-expiry'] : ['line-source-in-item-id'])];
fields.forEach((f,i)=>src.querySelector('.'+f).value=String(i));
src.querySelector('.material-code').value='AUD001';
src.querySelector('.material-price').value=PRICE;
src.querySelector('.line-customer-supplied').checked=true;
src.dataset={sourcePurchaseOrderItemId:'9',sourcePurchaseOrderNo:'PO9'};
const document={querySelectorAll(){return rows;},querySelector(){return rows.at(-1);}};
function addNewRow(){const r=makeRow();rows.push(r);return r;}
function insertRowBefore(next){const r=makeRow();rows.splice(rows.indexOf(next),0,r);return r;}
function findEmptyRow(){return rows.find(r=>!r.querySelector('.material-code').value);}
function findMaterialByCode(){return CACHED ? {price:12} : null;}
function fillMaterialFields(r){r.querySelector('.material-price').value='12.00';}
function calcAmount(){}
''' .replace('PRICE', json.dumps(price)).replace('CACHED', json.dumps(cached)).replace('PAGE', json.dumps(page)) + helpers + r'''
copyRowAfter(src);
const dst=rows[1];
for(const f of fields) assert.equal(dst.querySelector('.'+f).value,src.querySelector('.'+f).value,f);
if (PAGE==='in') {
    assert.deepEqual(dst.dataset,src.dataset);
    assert.equal(dst.querySelector('.line-customer-supplied').checked,true);
}
assert.equal(focused,dst.querySelector('.material-qty'));
'''.replace('PAGE', json.dumps(page))
    subprocess.run([node, '-e', script], check=True, capture_output=True, text=True, encoding='utf-8')


@pytest.mark.parametrize('page', ['in', 'out'])
def test_add_button_focuses_available_row_without_unnecessary_append(page):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    assert 'onclick="addRowAfterCurrent()"' in source
    function = 'function addRowAfterCurrent' + source.split('function addRowAfterCurrent', 1)[1].split('function insertRowBefore', 1)[0]
    script = r'''
const assert=require('node:assert/strict'); let focused=false,appended=0;
const row={querySelector(){return {focus(){focused=true;},select(){}};}};
function findEmptyRow(){return row;}
function addNewRow(){appended++;return row;}
''' + function + 'addRowAfterCurrent();assert.equal(appended,0);assert.equal(focused,true);'
    subprocess.run([node, '-e', script], check=True, capture_output=True, text=True, encoding='utf-8')
