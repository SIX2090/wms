"""Run real page clipboard handlers and ExcelTable methods without browser I/O."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WRITE_SCENARIOS = [
    'modern_success', 'modern_reject_true', 'modern_reject_false',
    'modern_reject_throw', 'modern_throw_true', 'modern_throw_false',
    'missing_true', 'missing_false', 'missing_throw', 'missing_truthy',
]
CASES = [(entry, scenario) for entry in ['contract', 'mobile', 'token', 'new_station', 'excel_copy'] for scenario in WRITE_SCENARIOS]
CASES += [('excel_paste', s) for s in ['success', 'reject', 'throw', 'missing', 'invalid', 'selection_changed', 'editing', 'destroyed']]
CASES += [('new_station', s) for s in ['business_error', 'network_error', 'duplicate_pending']]
CASES += [('excel_copy', 'editing'), ('excel_copy', 'no_selection')]

PROGRAM = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let messages=[],prompts=[],alerts=[],children=[],copied=new Set(),writes=[],reads=0,commands=0,posts=[],reloads=0;
let copiedResolve,copiedReject,postResolve,postReject,selected=0,focused=0,prevented=0,edits=[],unhandled=[];
process.on('unhandledRejection',e=>unhandled.push(e));
const icon={className:'bi bi-clipboard'};
const button={disabled:false,getAttribute:()=> 'CONTRACT-FIXTURE',querySelector:()=>icon,classList:{add:c=>copied.add(c),remove:c=>copied.delete(c)},addEventListener(e,h){this[e]=h;}};
const input={value:'FIXTURE-TOKEN-OR-URL',focus(){focused++;},select(){selected++;}};
const status={textContent:'服务器地址已复制'};
const cell={dataset:{value:'12.5'},textContent:'12.5',focus(){focused++;}};
const table={addEventListener(e,h){this[e]=h;},contains:()=>true};
const doc={activeElement:cell,querySelector:()=>({content:'fixture-csrf'}),getElementById(id){return ({copyMobileBaseUrl:button,mobileBaseUrl:input,mobileConnectStatus:status,'token-7':input,wsCode:{value:'FIXTURE'},wsName:{value:'虚构工作站'},wsWarehouse:{value:'2'}})[id];},body:{appendChild(t){children.push(t);},removeChild(t){children.splice(children.indexOf(t),1);}},createElement(){return {style:{},value:'',focus(){},select(){selected++;},remove(){doc.body.removeChild(this);}};},execCommand(cmd){assert.equal(cmd,'copy');commands++;if(p.scenario.endsWith('_throw'))throw Error('copy denied');return p.scenario.endsWith('_truthy')?'truthy':p.scenario.endsWith('_true');}};
const clipboard={writeText(value){writes.push(value);if(p.scenario.startsWith('modern_throw'))throw Error('blocked synchronously');return new Promise((resolve,reject)=>{copiedResolve=resolve;copiedReject=reject;});},readText(){reads++;if(p.scenario==='throw')throw Error('read blocked');if(p.scenario==='reject')return Promise.reject(Error('read denied'));return new Promise(resolve=>{copiedResolve=resolve;});}};
const ctx={Headers,FormData,document:doc,navigator:{clipboard:p.scenario.startsWith('missing')||p.scenario==='missing'?undefined:clipboard},setTimeout:()=>1,clearTimeout(){},showToast:(m,t)=>messages.push({m:String(m),t}),prompt:(m,v)=>{prompts.push({m,v});return null;},alert:m=>alerts.push(m),location:{reload(){reloads++;}},fetch:(u,o)=>{posts.push({u,o});return new Promise((resolve,reject)=>{postResolve=resolve;postReject=reject;});},console};
ctx.window=ctx;vm.createContext(ctx);
const flush=async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));};
let excel;
function invoke(){if(p.entry==='contract')return ctx.copyCellValue(button);if(p.entry==='mobile')return button.click();if(p.entry==='token')return ctx.copyToken(7);if(p.entry==='new_station')return ctx.addWs();return table.keydown({ctrlKey:true,key:p.entry==='excel_paste'?'v':'c',preventDefault(){prevented++;}});}
(async()=>{
if(p.entry==='contract')vm.runInContext(p.contract,ctx);
if(p.entry==='mobile')vm.runInContext(p.mobile,ctx);
if(['token','new_station'].includes(p.entry)){vm.runInContext(p.api,ctx);vm.runInContext(p.routing,ctx);}
if(p.entry.startsWith('excel')){vm.runInContext(p.excel,ctx);excel=Object.create(ctx.ExcelTable.prototype);excel.table=table;excel.currentCell=cell;excel.isEditing=p.scenario==='editing';excel._boundListeners=[];excel.startEdit=(c,v)=>edits.push({c,v});excel.setupCopyPaste();if(p.scenario==='no_selection')excel.currentCell=null;}
invoke();
if(p.entry==='new_station'){
 assert.equal(posts.length,1);assert.equal(posts[0].u,'/print_routing/workstations');assert.equal(posts[0].o.method,'POST');assert.equal(new Headers(posts[0].o.headers).get('X-CSRFToken'),'fixture-csrf');assert.deepEqual(JSON.parse(posts[0].o.body),{code:'FIXTURE',name:'虚构工作站',warehouse_id:'2'});
 if(p.scenario==='duplicate_pending'){invoke();assert.equal(posts.length,1,'in-flight create must not repeat POST');}
 if(p.scenario==='network_error')postReject(Error('offline'));
 else postResolve({ok:true,status:200,json:()=>Promise.resolve(p.scenario==='business_error'?{status:'error',msg:'编码重复'}:{status:'success',data:{msg:'工作站创建成功',token:'FIXTURE-NEW-TOKEN'}})});
 await flush();
 if(['network_error','business_error'].includes(p.scenario)){
  assert.equal(writes.length,0);assert.equal(alerts.length,0);assert.equal(reloads,0);assert(messages.some(x=>x.t==='danger'));invoke();assert.equal(posts.length,2,'create failure allows explicit retry');return;
 }
}
if(p.entry==='excel_paste'){
 if(['editing'].includes(p.scenario)){assert.equal(reads,0);assert.equal(prevented,0);return;}
 if(['success','invalid','selection_changed','destroyed'].includes(p.scenario)){
  if(p.scenario==='selection_changed')excel.currentCell={dataset:{value:'9'}};
  if(p.scenario==='destroyed')excel.currentCell=null;
  copiedResolve(p.scenario==='invalid'?'invalid':'22.25');
 }
 await flush();assert.equal(unhandled.length,0);assert.equal(prevented,1);
 if(p.scenario==='success'){assert.equal(edits.length,1);assert.equal(edits[0].c,cell);assert.equal(edits[0].v,'22.25');}
 else {assert.equal(edits.length,0);if(!['selection_changed','destroyed'].includes(p.scenario))assert(messages.some(x=>x.t==='danger'&&/粘贴|剪贴板/.test(x.m)));}
 return;
}
if(['editing','no_selection'].includes(p.scenario)){assert.equal(writes.length,0);assert.equal(prevented,0);return;}
if(!p.scenario.startsWith('missing')&&!p.scenario.startsWith('modern_throw')){
 assert.equal(writes.length,1);assert.equal(commands,0,'legacy copy must wait for modern failure');assert.equal(copied.size,0);assert.equal(messages.filter(x=>/已复制|已生成并复制/.test(x.m)).length,0,'no optimistic success');assert.equal(alerts.length,0,'do not acknowledge copy while pending');assert.equal(reloads,0);
 if(p.entry==='mobile')assert(!status.textContent.includes('已复制'),'clear stale success while retrying');
 if(p.scenario==='modern_success'||p.scenario==='duplicate_pending')copiedResolve();else copiedReject(Error('permission denied'));
}
await flush();assert.equal(unhandled.length,0,'all clipboard rejections handled');assert.equal(children.length,0,'temporary copy element cleaned');
const success=p.scenario==='modern_success'||p.scenario==='duplicate_pending'||p.scenario.endsWith('_true');
if(p.entry==='contract'){
 assert.equal(copied.has('copied'),success);assert.equal(icon.className,success?'bi bi-check-lg':'bi bi-clipboard');if(!success){assert(messages.some(x=>x.t==='danger'&&x.m.includes('复制失败')));assert.equal(prompts.length,1);assert.equal(prompts[0].v,'CONTRACT-FIXTURE');}
}else if(p.entry==='mobile'){
 assert.equal(status.textContent.includes('已复制'),success);if(!success){assert(status.textContent.includes('复制失败'));assert(status.textContent.includes('手动'));assert(selected>0);}
}else if(p.entry==='new_station'){
 assert.equal(posts.length,1,'clipboard failure never creates another workstation');assert.equal(reloads,1);assert.equal(alerts.length,1,'keep one existing manual acknowledgement of the new token');assert(alerts[0].includes('FIXTURE-NEW-TOKEN'));assert.equal(alerts[0].includes('已生成并复制'),success);if(!success){assert(alerts[0].includes('复制失败'));assert(alerts[0].includes('手动'));}assert(!messages.some(x=>x.t==='danger'&&x.m.includes('新增失败')));
}else{
 assert.equal(messages.some(x=>/已复制/.test(x.m)),success);if(!success){assert(messages.some(x=>x.t==='danger'&&x.m.includes('复制失败')));if(p.entry==='token')assert(selected>0);else {assert.equal(prompts.length,1);assert.equal(prompts[0].v,'12.5');}}
}
if(p.entry==='excel_copy'){assert.equal(prevented,1);assert.equal(excel.currentCell,cell);assert.equal(excel.isEditing,false);}
if(['modern_success','duplicate_pending'].includes(p.scenario))assert.equal(commands,0);else assert.equal(commands,1);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


@pytest.mark.parametrize('entry,scenario', CASES)
def test_clipboard_waits_for_confirmed_result_and_preserves_manual_retry(entry, scenario):
    contract = (ROOT / 'app/templates/contract.html').read_text(encoding='utf-8')
    routing = (ROOT / 'app/templates/print_routing.html').read_text(encoding='utf-8')
    mobile = (ROOT / 'app/templates/mobile_connect.html').read_text(encoding='utf-8')
    payload = dict(
        entry=entry, scenario=scenario,
        contract=contract[contract.index('function copyCellValue('):contract.index("document.addEventListener('DOMContentLoaded'", contract.index('function copyCellValue('))],
        mobile=mobile.split('<script>', 1)[1].split('</script>', 1)[0],
        routing=routing[routing.index('function copyToken('):routing.index('function editWs(')],
        excel=(ROOT / 'app/static/js/excel-table.js').read_text(encoding='utf-8'),
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
    )
    node = shutil.which('node')
    assert node, 'Node is required for the real browser-script regression'
    result = subprocess.run([node, '-e', PROGRAM], input=json.dumps(payload), capture_output=True,
                            text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
