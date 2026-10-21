"""采购入库单一提交入口：执行实际模板函数，核对保存→完成及失败边界。"""
import json
import os
from pathlib import Path
import shutil
import subprocess

from jinja2 import Template
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/templates/in_order_add.html'


def node_binary():
    found = shutil.which('node')
    if found:
        return found
    bundled = Path(os.environ.get('USERPROFILE', '')) / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
    if bundled.exists():
        return str(bundled)
    pytest.skip('Node.js required for runtime verification')


def test_purchase_toolbar_single_action():
    source = SOURCE.read_text(encoding='utf-8')
    toolbar = source.split('{% block content %}', 1)[1].split('<div class="card">', 1)[0]
    rendered = Template(toolbar).render(is_other_in=False, business_type='采购入库')
    assert '保存并完成入库' in rendered
    assert 'onclick="submitForm(false, true)"' in rendered
    assert 'onclick="submitForm(false, false)"' not in rendered
    assert 'onclick="submitForm(true, false)"' not in rendered
    assert 'data-wms-save-complete="1"' in rendered
    assert 'wms-no-global-actionbar' not in source


@pytest.mark.parametrize('kind', ['产品入库', '销售退货入库'])
def test_other_receipts_keep_draft_actions(kind):
    toolbar = SOURCE.read_text(encoding='utf-8').split('{% block content %}', 1)[1].split('<div class="card">', 1)[0]
    rendered = Template(toolbar).render(is_other_in=False, business_type=kind)
    assert 'onclick="submitForm(false, false)"' in rendered
    assert 'onclick="submitForm(true, false)"' in rendered


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
for (const [name,value] of Object.entries({date:'2026-10-20',supplier_id:'1',warehouse_id:'2',
  business_type:'采购入库',order_id:'',order_no:'IN-TEST',purpose:'',remark:''})) fields[name]={value};
if(scenario==='invalid') fields.warehouse_id.value='';
const row = {dataset:{},querySelector(s){
 const values={'.material-code':'M-TEST','.material-qty':'2','.material-price':'1'};
 return s in values ? {value:values[s]} : null;
}};
const buttons=[{disabled:false}];
const document = {
 querySelector(s){const m=s.match(/name="([^"]+)"/);return m ? fields[m[1]]||null : null;},
 querySelectorAll(s){return s==='#materialTableBody tr' ? [row] : buttons;}
};
const window={location:{href:'original'}};
const messages=[];const calls=[];let releaseSave;
const WMS={api:{postRaw(url,payload){
 calls.push({url,payload});
 if(url==='/in_order/add'){
   if(scenario==='save_network') return Promise.reject(Error('network'));
   if(scenario==='double_click')return new Promise(resolve=>{releaseSave=resolve;});
   return Promise.resolve({status:scenario==='save_error'?'error':'success',id:7,order_no:'IN-7',msg:'failed'});
 }
 if(scenario==='complete_network')return Promise.reject(Error('network'));
 return Promise.resolve({status:scenario==='warning'?'warning':scenario==='complete_error'?'error':'success',msg:'failed'});
}}};
function fetch(url,options){return WMS.api.postRaw(url,options).then(data=>({json:()=>Promise.resolve(data)}));}
const partyField='supplier_id',partyLabel='供应商',supplierRequired=true,returnAddUrl='/in_order/add';
let inOrderSubmitting=false;
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
 assert.equal(calls[0].url,'/in_order/add');
 if(['save_error','save_network'].includes(scenario)){
   assert.equal(calls.length,1);assert.equal(window.location.href,'original');
 } else {
   assert.equal(calls.length,2);
   assert.equal(calls[1].url,'/in_order/7/complete');
   assert.equal(fields.order_id.value,7);
   if(['success','double_click'].includes(scenario))assert.equal(window.location.href,'/in_order/add');
   else assert.equal(window.location.href,'/in_order/7','saved draft must remain reachable without duplicate save');
 }
 if(scenario==='save_error'||scenario==='save_network')assert.equal(inOrderSubmitting,false);
}
main().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''.replace('SCENARIO', json.dumps(scenario)).replace('SUBMIT', submit)
    result = subprocess.run([node_binary(), '-e', harness], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('combined', [True, False])
@pytest.mark.parametrize('marker', ['1', 'requisition'])
def test_global_toolbar_keeps_tools_and_routes_save(combined, marker):
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    helper_start = source.index('function escapeHtml(')
    helper = source[helper_start:source.index('\n}\n', helper_start) + 2]
    function = 'function insertGlobalActionBar() {' + source.split('function insertGlobalActionBar() {', 1)[1].split('// DOM加载完成后初始化', 1)[0]
    script = r'''
const assert=require('assert');
const combined=COMBINED;
let clicked=0,saved=0,rendered;
const primary={getAttribute(){return MARKER;},click(){clicked++;}};
const module={printTemplateUrl:'/templates',deleteUrl:'/delete'};
const document={
 getElementById(){return null;},
 body:{classList:{contains(){return false;},add(){}}},
 querySelector(selector){
  if(selector==='.embedded-content')return {insertBefore(bar){rendered=bar;}};
  if(selector==='button[data-wms-save-complete]')return combined?primary:null;
  return null;
 },
 createElement(tag){return {tag,children:[],classList:{add(){}},setAttribute(k,v){this[k]=v;},
  appendChild(child){this.children.push(child);},addEventListener(type,fn){this[type]=fn;}};}
};
const window={location:{pathname:'/in_order/add'}};
function isWmsEmbeddedPage(){return true;}
function getWmsActionModule(){return module;}
function isWmsListPage(){return false;}
function isFormPage(){return true;}
function pageHasOwnButton(){return false;}
function trimWmsActionbarDividers(buttons){return buttons;}
function saveCurrentPage(){saved++;}
function createDocumentNavigationGroup(){return {navigation:true};}
FUNCTION
insertGlobalActionBar();
const buttons=rendered.children.filter(x=>x.tag==='button');
for(const title of ['新增','打印设置','打印','导入','导出','导入导出模板','智能分享'])
 assert(buttons.some(x=>x.title===title),title+' must remain');
assert(rendered.children.some(x=>x.navigation),'document navigation must remain');
const save=buttons.find(x=>x.title===(combined?(MARKER==='requisition'?'保存并完成领料':'保存并完成入库'):'保存'));
assert(save);save.click();
assert.equal(clicked,combined?1:0);assert.equal(saved,combined?0:1);
'''.replace('MARKER', json.dumps(marker)).replace('COMBINED', json.dumps(combined)).replace('FUNCTION', helper + '\n' + function)
    result = subprocess.run([node_binary(), '-e', script], capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
