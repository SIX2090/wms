"""Run the real template callbacks and WMS API, including delayed replies."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['success','cancel','zero','preview_error','malformed',
    'changed','late','post_error','html','network'])
def test_wechat_cleanup_actual_controls_and_transport(scenario):
    page = (ROOT/'app/templates/wechat_share.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8')),mode=p.scenario;
const ids=['autoSend','autoSendRiskHint','wechatCleanupPanel','wechatCleanupDays','wechatCleanupImages','wechatCleanupPreview','wechatCleanupConfirm'];
const nodes=Object.fromEntries(ids.map(id=>[id,{hidden:true,disabled:false,checked:false,style:{},textContent:'',addEventListener(){}}]));
nodes.wechatCleanupDays.value='90';nodes.wechatCleanupConfirm.disabled=true;
const buttons=[{disabled:false},nodes.wechatCleanupConfirm,{disabled:true}];
const requests=[],confirms=[],alerts=[],toasts=[];let release,reloads=0;
const ctx={Headers,FormData,document:{getElementById:id=>nodes[id],querySelector:()=>({content:'synthetic-csrf'}),querySelectorAll:()=>buttons},
showToast:(m,t)=>toasts.push({m,t}),confirm:m=>{confirms.push(m);assert(buttons.every(b=>b.disabled));return mode!=='cancel';},
alert:m=>alerts.push(m),location:{reload(){reloads++;}},setTimeout(){},
fetch:(url,options)=>new Promise((resolve,reject)=>{requests.push({url,options});release=()=>{
 if(mode==='network'&&options.method==='POST'){reject(Error('offline'));return;}
 const preview=options.method==='GET';
 const bad=preview&&mode==='preview_error'||!preview&&mode==='post_error';
 resolve({ok:!bad,status:bad?409:200,json:async()=>{
  if(!preview&&mode==='html')throw SyntaxError('invalid JSON');
  return bad?{status:'error',msg:'fixture error'}:preview?{status:'success',data:mode==='malformed'?null:{count:mode==='zero'?0:3,protected_count:2,preview_token:'signed-fixture',cutoff:'2026-08-03'}}:{status:'success',msg:'已清理 3 条；图片文件保留'};
 }});
};})};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const run=code=>vm.runInContext(code,ctx),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 run('openWechatShareCleanup()');assert.equal(nodes.wechatCleanupPanel.hidden,false);
 assert(nodes.wechatCleanupConfirm.disabled);assert(!nodes.wechatCleanupImages.checked);
 const pending=run('previewWechatShareCleanup()');await flush();
 await run('previewWechatShareCleanup()');await run('confirmWechatShareCleanup()');assert.equal(requests.length,1);
 assert.equal(requests[0].url,'/wechat_share/logs/cleanup_preview?retention_days=90&delete_images=0');
 assert.equal(requests[0].options.method,'GET');assert.equal(requests[0].options.body,undefined);
 if(mode==='late'){nodes.wechatCleanupDays.value='30';run('resetWechatShareCleanupPreview()');}
 release();await pending;
 if(['zero','preview_error','malformed','late'].includes(mode)){
  assert(nodes.wechatCleanupConfirm.disabled);await run('confirmWechatShareCleanup()');assert.equal(requests.length,1);assert.equal(confirms.length,0);return;
 }
 assert(!nodes.wechatCleanupConfirm.disabled);assert(nodes.wechatCleanupPreview.textContent.includes('3 条'));
 if(mode==='changed'){nodes.wechatCleanupImages.checked=true;run('resetWechatShareCleanupPreview()');await run('confirmWechatShareCleanup()');assert.equal(requests.length,1);return;}
 const writing=run('confirmWechatShareCleanup()');await flush();await run('confirmWechatShareCleanup()');
 assert.equal(confirms.length,1);assert(confirms[0].includes('3 条'));assert(confirms[0].includes('不会撤回'));
 if(mode==='cancel'){await writing;assert.equal(requests.length,1);assert(nodes.wechatCleanupConfirm.disabled);return;}
 assert.equal(requests.length,2);const req=requests[1];assert.equal(req.url,'/wechat_share/logs/cleanup');
 assert.equal(req.options.method,'POST');assert.equal(req.options.headers['X-CSRFToken'],'synthetic-csrf');
 assert.deepEqual(JSON.parse(req.options.body),{retention_days:90,delete_images:false,preview_token:'signed-fixture'});
 release();await writing;
 if(mode==='success'){assert.equal(reloads,1);assert.equal(alerts.length,1);assert(alerts[0].includes('3 条'));}
 else{assert.equal(reloads,0);assert.equal(toasts.at(-1).t,'danger');assert(nodes.wechatCleanupConfirm.disabled);assert(!buttons[0].disabled);}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps({
        'scenario': scenario, 'script': script,
        'api': (ROOT/'app/static/js/api.js').read_text(encoding='utf-8')}),
        encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    for callback in ['openWechatShareCleanup()', 'previewWechatShareCleanup()', 'confirmWechatShareCleanup()']:
        assert f'onclick="{callback}"' in page
