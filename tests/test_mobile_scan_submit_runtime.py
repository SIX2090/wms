"""Execute the real H5 bindings and submit listener in four modes (BUG-2026-10-21-009)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mode", ["in", "out", "query", "check"])
@pytest.mark.parametrize("scenario", ["success", "network", "prepare", "batch", "http", "html", "expired401", "expired419", "business"])
def test_scan_submit_runtime(mode, scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    source = (ROOT / "app/templates/mobile_scan.html").read_text(encoding="utf-8")
    bindings = source[source.index("    var mode = shell.dataset.mode"):source.index("    function newRequestId")]
    listener = source[source.index("    scanForm.addEventListener('submit'"):source.index("    var cameraBtn =")]
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(process.argv[1]);let handler,requests=[],messages=[],queueRenders=0,fail=p.scenario;
const button={disabled:false};
const fields={scanCode:{value:'AUD-M001'},submitBtn:button,
 scanForm:{addEventListener:(name,fn)=>{handler=fn;}},quantityInput:{value:'2'},
 warehouseInput:{value:'Audit A',closest:()=>({classList:{contains:()=>p.mode==='query'}}),focus:()=>{}},
 remarkInput:{value:'memo'},targetInput:{value:'target'},
 batchMode:{checked:p.scenario==='batch' && ['in','out'].includes(p.mode)}};
if(p.mode==='check'){fields.scanAreaInput={value:'A1'};fields.scanReasonInput={value:'damaged'};}
const material={code:'AUD-M001'};
const ctx={shell:{dataset:{mode:p.mode,canWrite:'1'}},document:{getElementById:id=>fields[id]??null,querySelector:()=>({content:'fixture-csrf'})},
 Promise,Headers,FormData:class{},confirm:()=>false,setTimeout(){},location:{href:'original'},checkOrderSelect:{value:'9'},checkOrderTip:null,
 lookupMaterial:()=>Promise.resolve(material),newRequestId:()=>{if(fail==='prepare')throw new Error('prepare failed');return 'req-1';},
 setStatus:(msg)=>messages.push(msg),csrfHeaders:x=>x,sessionExpiredError:()=>null,
 fetch:(url,options)=>{requests.push({url,data:JSON.parse(options.body)});return fail==='network'?Promise.reject(new Error('offline')):Promise.resolve({ok:!['http','html','expired401','expired419'].includes(fail),status:fail==='http'?400:fail==='html'?503:fail==='expired401'?401:fail==='expired419'?419:200,json:()=>fail==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve({status:['http','business'].includes(fail)?'error':'success',msg:['http','business'].includes(fail)?'fixture failure':'ok',data:{material}})});},
 renderMaterial:()=>{},addHistory:()=>{},resetForNextScan:()=>{},refreshCheckProgress:()=>{},
 renderBatchQueue:()=>{queueRenders++;}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.bindings,ctx);vm.runInContext(p.listener,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 handler({preventDefault:()=>{}});await flush();await flush();
 assert.equal(button.disabled,false,'submit must recover on success and exceptions');
 const batch=fields.batchMode.checked;
 if(fail==='prepare'){assert.equal(requests.length,0);assert(messages.includes('prepare failed'));}
 else if(batch){assert.equal(requests.length,0);assert.equal(ctx.batchQueue.length,1);assert.equal(queueRenders,1);}
 else{assert.equal(requests.length,1,'real submit listener must send a request: '+JSON.stringify(messages));assert.equal(requests[0].data.area,p.mode==='check'?'A1':'');
  assert.equal(requests[0].data.reason,p.mode==='check'?'damaged':'');
  if(p.mode==='check')assert.equal(requests[0].data.check_id,'9');
  if(fail==='network')assert(messages.includes('offline'));else if(['http','business'].includes(fail))assert(messages.includes('fixture failure'));else if(fail==='html')assert(messages.includes('请求失败 (503)'));else if(fail.startsWith('expired'))assert(messages.includes('登录已过期，请重新登录'));else assert(messages.includes('ok'));}
 if(['network','prepare','http','html','expired401','expired419','business'].includes(fail)){fail='success';handler({preventDefault:()=>{}});await flush();await flush();assert.equal(button.disabled,false);assert(messages.includes('ok'),'retry must work after failure');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, "-e", script, json.dumps(dict(mode=mode, scenario=scenario, bindings=bindings, listener=listener, api=(ROOT / "app/static/js/api.js").read_text(encoding="utf-8")))], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
