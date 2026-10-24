"""BUG-2026-10-24-013: real selector callbacks, API transport and late replies."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    return re.search(r'^function '+name+r'\([^\n]*\) \{[\s\S]*?^\}', source, re.M).group()


def payload(page, mode):
    filename = {'sales':'sales_outbound_selection.html', 'purchase':'in_order_add.html', 'return':'out_order_add.html'}[page]
    source = (ROOT/'app/templates'/filename).read_text(encoding='utf-8')
    if page == 'sales':
        code = source[source.index('let selectable ='):source.index('function toggleAll')]
        code += '\n'+function(source, 'updateSummary')
        code = re.sub(r'{{\s*url_for\("api_sales_order_selectable"\)\s*}}', '/api/sales_order/selectable', code)
    elif page == 'purchase':
        code = 'let purchaseOrderSearchSeq=0; const purchaseOrderSelectableMap=new Map(); const sourcePurchaseOrderId="";\n'
        code += '\n'.join(function(source, n) for n in ['formatPurchaseQty', 'loadPurchaseOrderSelectable', 'renderPurchaseOrderSelectableRows', 'updatePurchaseOrderSelectionSummary'])
    else:
        code = source[source.index('let sourceInOrderTimer ='):source.index('function refreshDepartments')]
    return {'page':page, 'mode':mode, 'code':code, 'api':(ROOT/'app/static/js/api.js').read_text(encoding='utf-8')}


SCRIPT = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const fields={},pending=[],timers=[],events={};
function element(id){return {id,value:'',innerHTML:'',textContent:'',style:{display:'none'},dataset:{},checked:false,
 offsetTop:0,offsetLeft:0,offsetHeight:20,getBoundingClientRect:()=>({width:100}),
 addEventListener(n,f){this[n]=f;},querySelectorAll:()=>[],classList:{add(){},remove(){},toggle(){}}};}
['customerFilter','warehouseFilter','salespersonFilter','searchFilter','itemsBody','selectAll','entryStatus','summary','footerCount','footerQty',
 'selectionValidationPanel','selectionValidationList','purchaseOrderSelectBody','purchaseOrderSelectHint','purchaseOrderSelectSearch',
 'purchaseOrderSelectSummary','sourceInOrderNo','sourceInOrderId','sourceInOrderDropdown','supplier'].forEach(id=>fields[id]=element(id));
const key=p.page==='sales'?'searchFilter':p.page==='purchase'?'purchaseOrderSelectSearch':'sourceInOrderNo';
const bodyKey=p.page==='sales'?'itemsBody':p.page==='purchase'?'purchaseOrderSelectBody':'sourceInOrderDropdown';
const body=fields[bodyKey],input=fields[key]; input.value='old';
const esc=v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const doc={getElementById:id=>fields[id],querySelector:s=>s==='meta[name="csrf-token"]'?{content:'fixture'}:s==='[name="customer"]'?fields.supplier:null,
 querySelectorAll:()=>[],createElement(){const e={};Object.defineProperty(e,'textContent',{set(v){e.innerHTML=esc(v);}});return e;},
 addEventListener:(n,f)=>events[n]=f};
const ctx={document:doc,URLSearchParams,FormData,Map,Set,Number,Array,JSON,Error,escapeHtml:esc,escapeAttr:esc,
 getCurrentSupplierId:()=>fields.supplier.value,showToast(){},confirm:()=>false,
 setTimeout:(f)=>{timers.push(f);return timers.length;},clearTimeout:id=>{if(id)timers[id-1]=null;},
 fetch:(url,options)=>new Promise((resolve,reject)=>pending.push({url,options,resolve,reject}))};
ctx.window=ctx;ctx.location={href:'original'};vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.code,ctx);
const run=()=>ctx[p.page==='sales'?'loadSelectable':p.page==='purchase'?'loadPurchaseOrderSelectable':'searchSourceInOrders']();
const tick=()=>new Promise(r=>setImmediate(r));
const item=name=>({id:1,order_no:name,sales_order_id:1,sales_order_item_id:1,sales_order_no:name,purchase_order_item_id:1,purchase_order_no:name,
 warehouse:name,material_code:name,material_name:name,customer_name:'customer',supplier_name:'supplier',remaining_quantity:2,quantity:2,price:0});
function reply(i,name,kind='ok'){
 if(kind==='network'){pending[i].reject(Error('offline'));return;}
 const status=kind==='http'?500:kind==='auth'?401:200;
 pending[i].resolve({ok:status===200,status,json:()=>kind==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve(
 kind==='null'?null:kind==='business'?{status:'error',msg:'拒绝'}:{status:'success',items:kind==='shape'?{}:[item(name)],orders:kind==='shape'?{}:[item(name)]})});
}
function rendered(name){return body.innerHTML.includes(name)&&(p.page!=='return'||body.style.display==='block');}
(async()=>{
 if(p.page==='return')ctx.setupSourceInOrderSearch();
 run();assert.equal(pending.length,1);
 if(p.mode==='success'){
  reply(0,'current');await tick();assert(rendered('current'));
  assert.equal(pending[0].options.credentials,'same-origin');assert.equal(pending[0].options.headers['X-Requested-With'],'XMLHttpRequest');return;
 }
 if(['http','business','html','null','shape','auth','network'].includes(p.mode)){
  reply(0,'bad-candidate',p.mode);await tick();assert(!rendered('bad-candidate'));
  if(p.page!=='return')assert(body.innerHTML.includes('失败'),'error must not become an empty-success result');return;
 }
 if(['late-success','late-error'].includes(p.mode)){
  input.value='new';run();reply(1,'new-candidate');await tick();assert(rendered('new-candidate'));
  reply(0,'old-candidate',p.mode==='late-error'?'network':'ok');await tick();assert(rendered('new-candidate'));assert(!rendered('old-candidate'));return;
 }
 if(['filter-race','changed-filter'].includes(p.mode)){
  const filter=p.page==='sales'?fields.warehouseFilter:fields.supplier;filter.value='warehouse-or-supplier-2';
  if(p.mode==='changed-filter'){reply(0,'old-scope');await tick();assert(!rendered('old-scope'));return;}
  run();if(p.page!=='return')assert(pending[1].url.includes(encodeURIComponent(filter.value)));
  reply(1,'scope-2');await tick();reply(0,'scope-1');await tick();assert(rendered('scope-2'));assert(!rendered('scope-1'));return;
 }
 if(p.mode==='changed-context'){
  input.value='typed-before-next-query';reply(0,'old-candidate');await tick();assert(!rendered('old-candidate'));return;
 }
 if(p.mode==='replaced-dom'){
  fields[bodyKey]=element(bodyKey);reply(0,'detached');await tick();assert(!fields[bodyKey].innerHTML.includes('detached'));assert(!rendered('detached'));return;
 }
 if(p.mode==='cleared-summary'){
  const summary=p.page==='sales'?fields.summary:fields.purchaseOrderSelectSummary;
  summary.textContent='已选 9 行';run();assert(summary.textContent.includes('已选 0 行'));return;
 }
 if(p.mode==='pick')ctx.pickSourceInOrder('9','chosen');
 if(p.mode==='escape')input.keydown({key:'Escape'});
 if(p.mode==='outside')events.click({target:{closest:()=>null}});
 if(p.mode==='input')input.input();
 reply(0,'late-open');await tick();assert.equal(body.style.display,'none','closed dropdown must stay closed');
 if(p.mode==='pick'){assert.equal(input.value,'chosen');assert.equal(fields.sourceInOrderId.value,'9');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


@pytest.mark.parametrize('page', ['sales','purchase','return'])
@pytest.mark.parametrize('mode', ['success','http','business','html','null','shape','auth','network','late-success','late-error','changed-context','replaced-dom','filter-race','changed-filter'])
def test_selector_query_lifecycle(page, mode):
    result = subprocess.run([shutil.which('node'), '-e', SCRIPT, json.dumps(payload(page, mode))], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('page,mode', [('sales','cleared-summary'),('purchase','cleared-summary'), *[('return',m) for m in ['pick','escape','outside','input']]])
def test_selector_loading_and_dismissal(page, mode):
    result = subprocess.run([shutil.which('node'), '-e', SCRIPT, json.dumps(payload(page, mode))], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
