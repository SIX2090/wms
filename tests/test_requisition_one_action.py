"""采购入库单一提交入口：执行实际模板函数，核对保存→完成及失败边界。"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import shutil
import subprocess

from jinja2 import Template
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/templates/out_order_add.html'


def node_binary():
    found = shutil.which('node')
    if found:
        return found
    bundled = Path(os.environ.get('USERPROFILE', '')) / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if bundled.exists():
        return str(bundled)
    pytest.skip('Node.js required for runtime verification')


@pytest.mark.parametrize('existing', [False, True])
def test_work_order_single_button(existing):
    source=(ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    header=source.split('{% block content %}',1)[1].split('<div class="doc-body">',1)[0]
    declarations=source.split('{% block title %}',1)[0].split('\n',1)[1]
    rendered=Template(declarations+header).render(current_user=SimpleNamespace(role='production'),readonly=False,doc_type='requisition',can_save=True,can_complete=existing,complete_url='/complete/0')
    assert rendered.count('保存并完成领料') == 1
    assert 'submitForm(false)' not in rendered
    assert 'completeDocument()' not in rendered
    assert 'data-wms-save-complete="requisition"' in rendered


def test_normal_requisition_single_button():
    header=SOURCE.read_text(encoding='utf-8').split('{% block content %}',1)[1].split('<div class="card">',1)[0]
    rendered=Template(header).render(is_other_out=False,is_sale_order=False,is_purchase_return=False)
    assert '保存并完成领料' in rendered
    assert '保存并新增' not in rendered


@pytest.mark.parametrize('scenario', [
    'success', 'save_error', 'save_network', 'complete_error', 'warning',
    'complete_network', 'double_click', 'invalid',
])
def test_submit_form_one_action(scenario):
    source = SOURCE.read_text(encoding='utf-8')
    submit = 'function submitForm(' + source.split('function submitForm(', 1)[1].split("\ndocument.addEventListener('click'", 1)[0]
    harness = r'''
const assert = require('assert');
const scenario = SCENARIO;
const fields = {};
for (const [name,value] of Object.entries({date:'2026-10-20',department_id:'1',picker:'',warehouse_id:'2',
  business_type:'领料单',order_id:'',order_no:'IN-TEST',purpose:'',remark:''})) fields[name]={value};
if(scenario==='invalid') fields.warehouse_id.value='';
const row = {dataset:{},querySelector(s){
 const values={'.material-code':'M-TEST','.material-qty':'2','.material-price':'1'};
 return s in values ? {value:values[s],style:{}} : null;
}};
const buttons=[{disabled:false}];
const document = {
 querySelector(s){const m=s.match(/name="([^"]+)"/);return m ? fields[m[1]]||null : null;},
 getElementById(){return null;},
 querySelectorAll(s){return s==='#materialTableBody tr' ? [row] : buttons;}
};
const window={location:{href:'original'}};
const messages=[];const calls=[];let releaseSave;
const WMS={api:{postRaw(url,payload){
 calls.push({url,payload});
 if(url==='/out_order/add'){
   if(scenario==='save_network') return Promise.reject(Error('network'));
   if(scenario==='double_click')return new Promise(resolve=>{releaseSave=resolve;});
   return Promise.resolve({status:scenario==='save_error'?'error':'success',id:7,order_no:'IN-7',msg:'failed'});
 }
 if(scenario==='complete_network')return Promise.reject(Error('network'));
 return Promise.resolve({status:scenario==='warning'?'warning':scenario==='complete_error'?'error':'success',msg:'failed'});
}}};
function fetch(url,options){return WMS.api.postRaw(url,options).then(data=>({json:()=>Promise.resolve(data)}));}
const isSaleOrder=false,isOtherOut=false,isPurchaseReturn=false,purchaseReturnRequiresOrder=false;
const partyField='supplier_id',partyLabel='供应商',supplierRequired=true,returnAddUrl='/out_order/add';
let outOrderSubmitting=false;
function clearInOrderValidation(){}
function showInOrderValidation(errors){messages.push('validation');}
function markRowError(){}
function findMaterialByCode(){return true;}
function showToast(message){messages.push(message);}
function alert(message){messages.push(message);}
function confirm(){return true;}
function clearDraft(){}
SUBMIT
async function main(){
 const pending=submitForm(false,true);
 if(scenario==='double_click'){
   submitForm(false,true);
   assert.equal(calls.length,1,'duplicate click must not save twice');
   releaseSave({status:'success',id:7,order_no:'IN-7'});
 }
 await pending;
 await new Promise(resolve=>setImmediate(resolve));
 if(scenario==='invalid'){assert.equal(calls.length,0);return;}
 assert.equal(calls[0].url,'/out_order/add');
 if(['save_error','save_network'].includes(scenario)){
   assert.equal(calls.length,1);assert.equal(window.location.href,'original');
 } else {
   assert.equal(calls.length,2);
   assert.equal(calls[1].url,'/out_order/7/complete');
   assert.equal(fields.order_id.value,7);
   if(['success','double_click'].includes(scenario))assert.equal(window.location.href,'/out_order/7');
   else assert.equal(window.location.href,'/out_order/7','saved draft must remain reachable without duplicate save');
 }
 if(scenario==='save_error'||scenario==='save_network')assert.equal(outOrderSubmitting,false);
}
main().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''.replace('SCENARIO', json.dumps(scenario)).replace('SUBMIT', submit)
    result = subprocess.run([node_binary(), '-e', harness], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr




def test_work_order_blocks_duplicate_save_until_navigation():
    source=(ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    submit='function submitForm(completeAfterSave) {'+source.split('function submitForm(completeAfterSave) {',1)[1].split('\nfunction escapeHtmlText',1)[0]
    run='function runComplete(actionUrl, force, orderId) {'+source.split('function runComplete(actionUrl, force, orderId) {',1)[1].split('\nfunction showCompleteConfirm',1)[0]
    helpers=source[source.index('function beginDocumentAction()'):source.index('function submitForm(')]
    api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')
    script=r"""
const assert=require('assert');
const documentRoleAllowed=true;
class FormData {}
const readonly=false,saveUrl='/save',completeUrl='/complete/0',detailUrl='/detail',docType='requisition';
const document={querySelector(){return {value:'1'};},querySelectorAll(){return [];}};
const window={location:{href:'original'}};
function collectItems(){return {items:[{code:'M',quantity:1}],invalidRows:[]};}
function collectHeader(){return {};}
function showToast(){}
function setTimeout(){}
let calls=[],release;
function fetch(url){
 calls.push(url);
 if(url==='/save')return new Promise(resolve=>{release=()=>resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',id:7})});});
 return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success'})});
}
API
const WMS=window.WMS;
HELPERS
SUBMIT
RUN
async function check(){
 const pending=submitForm(true);submitForm(true);
 assert.deepEqual(calls,['/save']);release();await pending;
 assert.deepEqual(calls,['/save','/complete/7']);
 submitForm(true);assert.equal(calls.length,2,'navigation delay must not allow another save');
}
check().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
""".replace('API',api).replace('HELPERS',helpers).replace('SUBMIT',submit).replace('RUN',run)
    result=subprocess.run([node_binary(),'-e',script],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stderr
