"""Actual collect/save/wrapper and DOM save entrypoints with production api.js."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(marker)


@pytest.mark.parametrize('action', ['add', 'new', 'edit'])
@pytest.mark.parametrize('scenario', ['success', 'warnings', 'business', 'http403', 'http_success', 'html', 'invalid_json', 'null', '401', '419', 'network', 'collect_error', 'validation'])
def test_sales_actual_save_entrypoints(action, scenario):
    page = 'sales_order_edit.html' if action == 'edit' else 'sales_order_add.html'
    source = (ROOT / 'app/templates' / page).read_text(encoding='utf-8')
    fields = re.search(r'var formFields = (\[[^;]+\]);', source)[1]
    original = block(source, 'async function save(')
    wrapper = block(source, 'save = async function(')
    script = ('var formFields = ' + fields + ';\nvar salesSaveBusy = false;\n'
              + block(source, 'function collect(') + '\n' + original + '\nvar originalSave = save;\n' + wrapper + ';\n')
    script += '\n'.join(re.findall(r"document\.getElementById\('save(?:New)?Btn'\)\.addEventListener\('click', function\(\) \{ save\([^;]*; \}\);", source))
    script += '\n' + re.search(r'window.submitForm = function\(\) \{ return save\([^;]*; \};', source)[0]
    script = script.replace('{{ url_for("sales_order_add") }}', '/sales/add').replace('{{ url_for("sales_order_add_page") }}', '/sales/add')
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario,resolveRequest,href='original',collectRound=0;const sent=[],timers=[],messages=[],handlers={},recent=[];
const fields={order_no:'SO-FIXTURE',date:'2026-10-23',customer_id:'2',delivery_date:'2026-11-01',warehouse_id:'3',salesperson_id:'4',project_no:'project fixture',currency:'CNY',settlement_method:'fixture settlement',remark:'fixture header'};
const lines={'.material-code':' MAT-1 ','.qty':'2.00','.price':'0','.tax-rate':'0','.batch-no':'batch fixture','.serial-no':'serial fixture','.line-contract-no':' contract fixture ','.line-project-name':' project line ','.line-remark':'line remark'};
const row={querySelector:s=>{if(s==='.material-code')collectRound++;if(mode==='collect_error'&&(p.action!=='add'||collectRound>1))throw Error('fixture collection failure');return {value:lines[s]};}};
const buttons={saveBtn:{disabled:false,addEventListener:(e,fn)=>handlers.saveBtn=fn},saveNewBtn:{disabled:p.action==='edit',addEventListener:(e,fn)=>handlers.saveNewBtn=fn}};
const status={textContent:''};const body={querySelectorAll:()=>[row]};
const ctx={Headers,FormData,body,editUrl:'/sales/7/edit',document:{getElementById:id=>id==='entryStatus'?status:buttons[id],querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:{value:mode==='validation'&&s.includes('customer_id')?'':fields[s.match(/name="([^"]+)"/)?.[1]]},querySelectorAll:()=>Object.values(buttons)},
 showValidation:m=>messages.push(...m),rememberRecent:code=>recent.push(code),showToast:(m,t)=>messages.push({m,t}),confirm:()=>false,
 location:{get href(){return href;},set href(value){href=value;}},setTimeout:(fn,delay)=>timers.push({fn,delay}),
 fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>resolveRequest=()=>{
  if(mode==='network'){reject(Error('fixture offline'));return;}
  const status=mode==='http403'?403:mode==='http_success'?500:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
  const body=mode==='null'?null:{status:['business','http403'].includes(mode)?'error':'success',msg:'specific permission or business explanation',id:9,...(mode==='warnings'?{warnings:['fixture stock warning']}: {})};
  resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});
 })}};
// Keep the former request helper executable during rollback validation.
ctx.csrfFetch=(url,options)=>ctx.fetch(url,Object.assign({credentials:'same-origin'},options));
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const click=()=>handlers[p.action==='new'?'saveNewBtn':'saveBtn'](),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 click();await flush();
 if(['validation','collect_error'].includes(mode)){
  assert.equal(sent.length,0);assert.equal(href,'original');assert(!buttons.saveBtn.disabled);
  assert(status.textContent.includes(mode==='collect_error'?'fixture collection failure':'请选择客户'));
  mode='success';click();await flush();assert.equal(sent.length,1);resolveRequest();await flush();return;
 }
 assert.equal(sent.length,1);assert(buttons.saveBtn.disabled);click();await ctx.submitForm();assert.equal(sent.length,1,'DOM and global toolbar share the lock');
 const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.u,p.action==='edit'?'/sales/7/edit':'/sales/add');assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('Content-Type'),'application/json');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
 assert.deepEqual(JSON.parse(req.o.body),{...fields,items:[{code:'MAT-1',quantity:'2.00',price:'0',tax_rate:'0',batch_no:'batch fixture',serial_no:'serial fixture',contract_no:'contract fixture',project_name:'project line',remark:'line remark'}]});
 resolveRequest();await flush();await flush();
 const target=p.action==='new'?'/sales/add':'/sales/9';
 if(['success','warnings'].includes(mode)){
  if(mode==='warnings'){assert.equal(href,'original');assert(status.textContent.includes('fixture stock warning'));assert.equal(timers.length,1);assert.equal(timers[0].delay,3000);assert(messages.some(m=>m.t==='warning'));}
  else assert.equal(href,target);
  click();await ctx.submitForm();assert.equal(sent.length,1,'warning/navigation window must remain locked');
  if(mode==='warnings'){timers[0].fn();assert.equal(href,target);}
 }else{
  assert.equal(href,'original');assert(!buttons.saveBtn.disabled);assert.equal(buttons.saveNewBtn.disabled,p.action==='edit');assert(!timers.some(t=>t.delay===3000));assert(status.textContent&&!status.textContent.includes('保存中'));
  if(['http403','business'].includes(mode))assert(status.textContent.includes('specific permission or business explanation'));
  if(mode==='html')assert(status.textContent.includes('503'));
  mode='success';click();await flush();assert.equal(sent.length,2);resolveRequest();await flush();await flush();assert.equal(href,target);
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'action': action, 'scenario': scenario,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
