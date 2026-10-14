"""Actual shared-form functions must distinguish zero price from a blank value."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('doc_type', ['bom', 'transfer', 'requisition'])
def test_shared_form_collects_zero_price_without_material_price_fallback(doc_type):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(JSON.parse(process.argv[1]),'utf8'),docType=process.argv[2];
function extract(name){const start=source.indexOf('function '+name+'(');let depth=0;
for(let i=source.indexOf('{',start);i<source.length;i++){if(source[i]==='{')depth++;if(source[i]==='}'&&--depth===0)return source.slice(start,i+1);}}
const material={id:1,code:'M1',price:5,name:'测试',spec:'规格'};
const fields={'.material-code':{value:'M1',style:{}},'.unit-id':{value:'1'},
'.line-qty':{value:'3',style:{}},'.line-price':{value:'0'},
'.material-name':{value:''},'.material-spec':{value:''},'.material-unit':{value:''},'.line-usage':{value:''},'.line-remark':{value:''}};
const row={dataset:{},querySelector:s=>fields[s]||null};
const document={querySelectorAll:()=>[row]};
function findMaterialByCode(){return material;}
function getMaterialUnitId(){return 1;} function getMaterialUnit(){return '个';}
function formatQty(v){return Number(v||0).toFixed(2);} function calcRow(){}
eval(extract('collectItems')+'\n'+extract('fillMaterialFields'));
assert.equal(collectItems().items[0].price,0);
fillMaterialFields(row,material);assert.equal(fields['.line-price'].value,'0');
fields['.line-price'].value='';fillMaterialFields(row,material);
assert.equal(collectItems().items[0].price,5);
fields['.line-qty'].value='Infinity';assert.equal(collectItems().items.length,0);
'''
    result = subprocess.run([node, '-e', script,
                             json.dumps(str(ROOT / 'app/templates/document_table_form.html')), doc_type],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_bom_unit_picker_is_visible_only_for_editable_bom():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(JSON.parse(process.argv[1]),'utf8');
const start=source.indexOf('function rowCells('),end=source.indexOf('function createRow(',start);
let docType='bom',readonly=false;
function unitOptions(){return '<option value="2">箱</option>';}
eval(source.slice(start,end));
assert.match(rowCells({unit_id:2}),/class="unit-id " /);
assert.match(rowCells({unit_id:2}),/material-unit" style="display:none;"/);
readonly=true;assert.match(rowCells({unit_id:2}),/class="unit-id d-none" disabled/);
readonly=false;docType='transfer';assert.match(rowCells({unit_id:2}),/class="unit-id d-none"/);
'''
    result = subprocess.run([node,'-e',script,json.dumps(str(ROOT/'app/templates/document_table_form.html'))],
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stderr
