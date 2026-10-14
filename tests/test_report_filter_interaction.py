"""Execute actual report filtering functions, including out-of-order requests."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_js(body):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for report runtime checks')
    script = r'''
const fs=require('node:fs'), assert=require('node:assert/strict');
const source=fs.readFileSync(JSON.parse(process.argv[1]),'utf8');
function extract(name) {
 let start=source.indexOf('function '+name+'(');
 if(start<0) throw Error('Missing function '+name);
 if(source.slice(start-6,start)==='async ') start-=6;
 const open=source.indexOf('{',start); let depth=0;
 for(let i=open;i<source.length;i++){
  if(source[i]==='{') depth++;
  if(source[i]==='}' && --depth===0) return source.slice(start,i+1);
 }
 throw Error('Unclosed function '+name);
}
let currentPage=1,pageSize=20,currentSortField='',currentSortOrder='asc',reportRequestId=0;
const fields={
 warehouse_id:{id:'warehouse_id',name:'warehouse_id',type:'select-one',value:'2'},
 start_date:{id:'start_date',name:'start_date',type:'hidden',value:'2026-10-13'},
 end_date:{id:'end_date',name:'end_date',type:'hidden',value:'2026-10-14'},
 material_code:{id:'material_code',name:'material_code',type:'text',value:'101001'},
 hide_zero:{id:'hideZero',name:'hide_zero',type:'checkbox',value:'1',checked:false},
 csrf_token:{name:'csrf_token',type:'hidden',value:'SECRET-CSRF'}
};
const filterForm={elements:Object.values(fields),querySelector:s=>fields[s.slice(1)]||null,
 reset(){fields.warehouse_id.value='1'; fields.material_code.value=''; fields.hide_zero.checked=false;
 fields.start_date.value='2026-10-13'; fields.end_date.value='2026-10-14';}};
const pageSizeSelect={value:'20',options:[{value:'20'},{value:'50'},{value:'100'},{value:'200'}]};
const extra={dateRangeError:{hidden:true},activeFilterSummary:{textContent:''}};
const document={getElementById:id=>fields[id]||extra[id]||null};
const window={location:{search:'',href:'http://localhost/report/view/inventory?embedded=1'},
 history:{replaceState(a,b,url){window.location.href=url;}}};
class FormData {entries(){return Object.values(fields).filter(f=>f.name&&(f.type!=='checkbox'||f.checked)).map(f=>[f.name,f.value]);}}
'''
    result = subprocess.run([node, '-e', script + '\n' + body,
                             json.dumps(str(ROOT / 'app/templates/report_view.html'))],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_reset_clears_flatpickr_and_preserves_selected_warehouse():
    run_js(r'''
eval(extract('setReportDate')+'\n'+extract('resetReportFilters'));
let clearCount=0;
for(const id of ['start_date','end_date']) fields[id]._flatpickr={clear(){clearCount++;},setDate(){}};
resetReportFilters();
assert.equal(fields.warehouse_id.value,'2');
assert.equal(fields.start_date.value,''); assert.equal(fields.end_date.value,'');
assert.equal(clearCount,2); assert.equal(fields.material_code.value,'');
''')


def test_restore_url_filters_and_query_export_share_conditions():
    run_js(r'''
eval(['setReportDate','restoreReportFilters','buildParams','syncReportFilterUrl'].map(extract).join('\n'));
window.location.search='?warehouse_id=3&material_code=M8&hide_zero=1&start_date=2026-10-01&page=2&page_size=50&sort_field=stock&sort_order=desc';
restoreReportFilters();
assert.equal(fields.warehouse_id.value,'3'); assert.equal(fields.material_code.value,'M8');
assert.equal(fields.hide_zero.checked,true); assert.equal(fields.start_date.value,'2026-10-01');
assert.equal(currentPage,2); assert.equal(pageSize,50); assert.equal(currentSortOrder,'desc');
const query=buildParams(),exported=buildParams(true);
assert.equal(query.has('csrf_token'),false); assert.equal(exported.get('export'),'excel');
exported.delete('export'); assert.equal(query.toString(),exported.toString());
syncReportFilterUrl(); const url=new URL(window.location.href);
assert.equal(url.searchParams.get('warehouse_id'),'3'); assert.equal(url.searchParams.get('embedded'),'1');
assert.equal(url.searchParams.has('csrf_token'),false);
''')


def test_presets_use_local_dates_and_inclusive_30_days():
    run_js(r'''
eval(extract('reportDateRange'));
const now=new Date(2026,9,14,0,30);
assert.deepEqual(reportDateRange('today',now),['2026-10-14','2026-10-14']);
assert.deepEqual(reportDateRange('week',now),['2026-10-12','2026-10-14']);
assert.deepEqual(reportDateRange('month',now),['2026-10-01','2026-10-14']);
assert.deepEqual(reportDateRange('30days',now),['2026-09-15','2026-10-14']);
assert.deepEqual(reportDateRange('all',now),['','']);
assert.deepEqual(reportDateRange('week',new Date(2026,9,18)),['2026-10-12','2026-10-18']);
''')


def test_older_response_cannot_overwrite_newer_filter_results():
    run_js(r'''
const reportType='inventory',tableBody={innerHTML:''},tableHeaderRow={innerHTML:''},paginationNav={innerHTML:''},pageTotal={textContent:''};
let rendered=[],masks=[],pending=[];
function updateReportFilterSummary(){} function syncReportFilterUrl(){}
function buildParams(){return new URLSearchParams();}
function setLoading(v){masks.push(v);} function renderSummary(v){rendered.push(v.count);}
function renderTable(){} function renderPagination(){} function renderTruncation(){} function escapeHtml(s){return s;}
function fetch(){return new Promise(resolve=>pending.push(resolve));}
eval(extract('loadData'));
(async()=>{
 const older=loadData(),newer=loadData();
 pending[1]({ok:true,json:async()=>({status:'success',summary:{count:1}})}); await newer;
 pending[0]({ok:true,json:async()=>({status:'success',summary:{count:1268}})}); await older;
 assert.deepEqual(rendered,[1]); assert.deepEqual(masks,[true,true,false]);
 fields.start_date.value='2026-10-20'; fields.end_date.value='2026-10-01';
 await loadData(); assert.equal(extra.dateRangeError.hidden,false); assert.equal(pending.length,2);
 fields.start_date.value=''; fields.end_date.value=''; fields.warehouse_id.value='';
 await loadData(); assert.match(tableBody.innerHTML,/请先选择仓库/); assert.equal(pending.length,2);
})().catch(e=>{console.error(e);process.exit(1);});
''')
