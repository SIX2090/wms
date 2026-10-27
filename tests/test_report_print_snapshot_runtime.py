"""BUG-2026-10-25-005: execute real report print binding and render functions."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORT_TYPES = ['inventory', 'inventory_analysis', 'in_detail', 'out_detail', 'summary',
                'check', 'ledger', 'warehouse_monthly', 'subcontract', 'requisition',
                'purchase_order_execution', 'supplier_purchase_summary',
                'material_purchase_summary', 'purchase_price_analysis']

SCRIPT = r'''
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const root=process.argv[1], scenario=process.argv[2], reportType=process.argv[3];
const src=fs.readFileSync(root+'/app/templates/report_view.html','utf8');
const shared=fs.readFileSync(root+'/app/static/js/app.js','utf8');
const start=src.indexOf('const MAX_PRINT_ROWS = 10000;');
const end=src.indexOf('\nfunction setLoading(',start);
assert(start>=0&&end>start);
const escapeStart=shared.indexOf('function escapeHtml('),escapeEnd=shared.indexOf('\nfunction openAdd(',escapeStart);
const formatStart=src.indexOf('const STATUS_LABELS = {'),formatEnd=src.indexOf('\nfunction renderSummary(',formatStart);
const fields={
 warehouse_id:{id:'warehouse_id',name:'warehouse_id',tagName:'SELECT',type:'select-one',value:'2',options:[{value:'1',textContent:'甲仓'},{value:'2',textContent:'乙仓'}]},
 start_date:{id:'start_date',name:'start_date',tagName:'INPUT',type:'hidden',value:'2026-10-01'},
 end_date:{id:'end_date',name:'end_date',tagName:'INPUT',type:'hidden',value:'2026-10-25'},
 material_code:{id:'material_code',name:'material_code',tagName:'INPUT',type:'text',value:'M-1'},
 hide_zero:{id:'hideZero',name:'hide_zero',tagName:'INPUT',type:'checkbox',value:'1',checked:true},
 csrf_token:{name:'csrf_token',tagName:'INPUT',type:'hidden',value:'SECRET-DO-NOT-PRINT'}
};
Object.defineProperty(fields.warehouse_id,'selectedIndex',{get(){return fields.warehouse_id.options.findIndex(o=>o.value===fields.warehouse_id.value)}});
const labels={warehouse_id:'仓库 *',start_date:'开始日期',end_date:'结束日期',material_code:'物料搜索',hideZero:'库存等于0不显示'};
if(reportType==='in_detail'){
 fields.contract_no={id:'contract_no',name:'contract_no',tagName:'INPUT',type:'text',value:'C-001'};
 fields.project_name={id:'project_name',name:'project_name',tagName:'INPUT',type:'text',value:'一号工程'};
 labels.contract_no='合同编号';labels.project_name='工程名称';
}
let handler,prints=0,load=[],requests=[],pending=[],renderSnapshots=[];
const area={innerHTML:''},error={textContent:'',classList:{remove(){},add(){}}};
const screenValues={count:'99',quantity:'100',amount:'999'};
let screenReads=0;
const form={elements:Object.values(fields),querySelector(selector){
 if(selector.startsWith('#'))return Object.values(fields).find(f=>f.id===selector.slice(1))||null;
 let m=selector.match(/^\[name="(.+)"\]$/);if(m)return fields[m[1]]||null;
 m=selector.match(/^label\[for="(.+)"\]$/);return m&&labels[m[1]]?{textContent:labels[m[1]]}:null;
}};
const summaryLabels={count:'记录数',quantity:'数量',amount:'金额'},summaryTypes={count:'number',quantity:'number',amount:'money'};
const context={console,URLSearchParams,Date,reportType,reportTitle:'实际报表',summaryLabels,summaryTypes,
 currentColumns:[{field:'quantity',title:'数量',type:'number'}],currentPage:3,pageSize:20,
 currentSortField:'quantity',currentSortOrder:'desc',filterForm:form,
 printBtn:{addEventListener(event,fn){assert.equal(event,'click');handler=fn}},
 document:{getElementById(id){if(id==='printArea')return area;if(id==='truncationAlert')return error;return fields[id]||null},
 querySelectorAll(selector){assert.equal(selector,'#summaryCards .summary-card');screenReads++;
 return ['count','quantity','amount'].map(key=>({querySelector(sel){return {textContent:sel==='.summary-label'?summaryLabels[key]:screenValues[key]}}}));}},
 FormData:class{constructor(f){assert.equal(f,form)} entries(){return Object.values(fields).filter(f=>f.type!=='checkbox'||f.checked).map(f=>[f.name,f.value])}},
 window:{print(){prints++;renderSnapshots.push(area.innerHTML)}},setLoading(value){load.push(value)},renderTruncation(){},
 fetch(url){requests.push(new URL(url,'http://isolated.test'));return new Promise((resolve,reject)=>pending.push({resolve,reject}))}};
vm.createContext(context);
vm.runInContext(shared.slice(escapeStart,escapeEnd)+'\n'+src.slice(formatStart,formatEnd)+'\n'+src.slice(start,end),context);
function reply(index,overrides={},httpOK=true){
 pending[index].resolve({ok:httpOK,json:async()=>({status:'success',columns:[{field:'quantity',title:'数量',type:'number'}],
 data:[{quantity:7}],summary:{count:1,quantity:7,amount:14},summary_labels:{count:'本次记录',quantity:'本次数量',amount:'本次金额'},
 summary_types:{count:'number',quantity:'number',amount:'money'},total:1,total_pages:1,...overrides})});
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function assertRequest(index,warehouse='2'){
 assert.equal(requests[index].pathname,'/report/api/'+reportType);
 assert.equal(requests[index].searchParams.get('warehouse_id'),warehouse);
 assert.equal(requests[index].searchParams.get('page_size'),'500');
 if(reportType==='in_detail'){
  assert.equal(requests[index].searchParams.get('contract_no'),'C-001');
  assert.equal(requests[index].searchParams.get('project_name'),'一号工程');
 }
 assert.equal(requests[index].searchParams.has('csrf_token'),false);
 assert.equal(requests[index].searchParams.get('sort_field'),'quantity');
 assert.equal(requests[index].searchParams.get('sort_order'),'desc');
}
function assertCurrentSummary(quantity=7){
 assert.match(area.innerHTML,/本次记录 1/);assert.ok(area.innerHTML.includes('本次数量 '+quantity));
 assert.ok(area.innerHTML.includes('本次金额 ¥'+(quantity*2).toFixed(2)));assert.equal(screenReads,0);
 assert.deepEqual(screenValues,{count:'99',quantity:'100',amount:'999'});
 assert.equal(area.innerHTML.includes('SECRET-DO-NOT-PRINT'),false);
}
(async()=>{
 if(scenario==='missing_warehouse'){
  fields.warehouse_id.value='';await handler();assert.equal(requests.length,0);assert.equal(prints,0);assert.match(error.textContent,/选择仓库/);return;
 }
 if(scenario==='warehouse_a')fields.warehouse_id.value='1';
 if(scenario==='date_changed')fields.start_date.value='2026-10-20';
 if(scenario==='escaped'){
  fields.material_code.value='<img src=x onerror=evil()>&"';labels.material_code='物料<搜索>';
  fields.warehouse_id.options[1].textContent='乙仓<script>evil()</script>';
 }
 const work=handler();assert.equal(requests.length,1);assertRequest(0,scenario==='warehouse_a'?'1':'2');
 if(scenario.startsWith('failure_')){
  const reason=scenario.slice(8);
  if(reason==='network')pending[0].reject(new Error('网络中断'));
  else if(reason==='parse')pending[0].resolve({ok:true,json:async()=>{throw new Error('不是JSON')}});
  else if(reason==='html')pending[0].resolve({ok:false,json:async()=>{throw new SyntaxError('Unexpected token <')}});
  else reply(0,{status:reason==='business'?'error':'success',msg:'本次拒绝'},reason!=='http');
  await work;assert.equal(prints,0);assert.match(error.textContent,/打印失败/);assert.deepEqual(load,[true,false]);return;
 }
 if(scenario==='late_context'||scenario==='two_pages'||scenario==='later_failure'){
  fields.warehouse_id.value='1';fields.start_date.value='2030-01-01';fields.material_code.value='NEW';
 }
 if(scenario==='warehouse_a')reply(0,{data:[{quantity:5}],summary:{count:1,quantity:5,amount:10}});
 else if(scenario==='no_auxiliary')reply(0,{summary_labels:undefined,summary_types:undefined});
 else if(scenario==='zero')reply(0,{data:[],summary:{count:0,quantity:0,amount:0},total:0});
 else if(scenario==='escaped')reply(0,{columns:[{field:'quantity',title:'<img src=x>',type:'text'}],data:[{quantity:'<script>evil()</script>'}],
      summary_labels:{quantity:'<b>本次数量</b>'}});
 else if(scenario==='money_type')reply(0,{summary_types:{count:'number',quantity:'money',amount:'number'}});
 else if(scenario==='two_pages'||scenario==='later_failure')reply(0,{data:[{quantity:3}],total_pages:2,summary:{count:2,quantity:7,amount:14}});
 else if(scenario==='cap')reply(0,{data:Array.from({length:500},()=>({quantity:1})),total_pages:25,summary:{count:12500,quantity:12500,amount:25000}});
 else reply(0);
 if(scenario==='two_pages'||scenario==='later_failure'){
  await tick();assert.equal(requests.length,2);assertRequest(1);assert.equal(requests[1].searchParams.get('start_date'),'2026-10-01');
  assert.equal(requests[1].searchParams.get('material_code'),'M-1');assert.equal(requests[1].searchParams.get('page'),'2');
  if(scenario==='later_failure')pending[1].reject(new Error('第二页失败'));
  else reply(1,{data:[{quantity:4}],summary:{count:900,quantity:900,amount:900}});
 }
 if(scenario==='cap'){
  for(let i=1;i<20;i++){await tick();assert.equal(requests.length,i+1);reply(i,{data:Array.from({length:500},()=>({quantity:1})),total_pages:25,summary:{count:12500,quantity:12500,amount:25000}});}
 }
 await work;assert.deepEqual(load,[true,false]);
 if(scenario==='later_failure'){assert.equal(prints,0);assert.match(error.textContent,/第二页失败/);return;}
 assert.equal(prints,1);
 if(scenario==='zero'){
  assert.match(area.innerHTML,/当前条件下没有数据/);assert.match(area.innerHTML,/本次数量 0/);assert.match(area.innerHTML,/本次金额 ¥0\.00/);assert.equal(screenReads,0);
 }else if(scenario==='no_auxiliary'){
  assert.match(area.innerHTML,/记录数 1/);assert.match(area.innerHTML,/数量 7/);assert.match(area.innerHTML,/金额 ¥14\.00/);assert.equal(screenReads,0);
 }else if(scenario==='money_type'){
  assert.match(area.innerHTML,/本次数量 ¥7\.00/);assert.match(area.innerHTML,/本次金额 14/);assert.equal(screenReads,0);
 }else if(scenario==='escaped'){
  assert.match(area.innerHTML,/物料&lt;搜索&gt;/);assert.match(area.innerHTML,/乙仓&lt;script&gt;/);
  assert.match(area.innerHTML,/&lt;img src=x/);assert.match(area.innerHTML,/&lt;script&gt;evil\(\)&lt;\/script&gt;/);
  assert.match(area.innerHTML,/&lt;b&gt;本次数量&lt;\/b&gt; 7/);assert.equal(area.innerHTML.includes('<script>'),false);assert.equal(screenReads,0);
 }else if(scenario==='two_pages'){
  assert.match(area.innerHTML,/本次记录 2/);assert.match(area.innerHTML,/本次数量 7/);assert.equal(area.innerHTML.includes('900'),false);
  assert.match(area.innerHTML,/<td>3<\/td>/);assert.match(area.innerHTML,/<td>4<\/td>/);assert.match(area.innerHTML,/乙仓/);assert.equal(screenReads,0);
 }else if(scenario==='cap'){
  assert.equal(requests.length,20);assert.equal((area.innerHTML.match(/<td>1<\/td>/g)||[]).length,10000);
  assert.match(area.innerHTML,/完整数据请导出 Excel/);assert.match(area.innerHTML,/本次数量 12,500/);assert.match(area.innerHTML,/含未打印行/);assert.equal(screenReads,0);
 }else{
  assertCurrentSummary(scenario==='warehouse_a'?5:7);assert.match(area.innerHTML,/仓库：/);assert.match(area.innerHTML,/库存等于0不显示/);
  if(scenario==='warehouse_a')assert.match(area.innerHTML,/甲仓/);
  else assert.match(area.innerHTML,/乙仓/);
  if(scenario==='date_changed')assert.match(area.innerHTML,/2026-10-20/);
  if(scenario==='late_context'){
    assert.equal(area.innerHTML.includes('甲仓'),false);assert.equal(area.innerHTML.includes('2030-01-01'),false);assert.equal(area.innerHTML.includes('NEW'),false);
    assert.match(area.innerHTML,/2026-10-01/);assert.match(area.innerHTML,/M-1/);
  }
 }
})().catch(error=>{console.error(error);process.exit(1)});
'''


def run_scenario(scenario, report_type='inventory'):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for real report print runtime checks')
    run = subprocess.run([node, '--max-old-space-size=64', '-e', SCRIPT, str(ROOT), scenario, report_type],
                         capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert run.returncode == 0, run.stderr


@pytest.mark.parametrize('report_type', REPORT_TYPES)
def test_all_report_prints_use_their_own_response_summary(report_type):
    run_scenario('normal', report_type)


@pytest.mark.parametrize('scenario', ['warehouse_a', 'date_changed', 'late_context', 'two_pages',
                                    'zero', 'escaped', 'no_auxiliary', 'money_type', 'cap'])
def test_print_snapshot_and_response_summary_boundaries(scenario):
    run_scenario(scenario)


@pytest.mark.parametrize('scenario', ['missing_warehouse', 'failure_http', 'failure_business',
                                    'failure_network', 'failure_parse', 'failure_html', 'later_failure'])
def test_print_failures_and_loading_recovery(scenario):
    run_scenario(scenario)
