"""Execute the actual WeChat buttons and production API without sending messages."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('action', ['save', 'run', 'force', 'resend', 'clear'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_json', 'html', 'invalid_json', 'null', '401', '419', 'network', 'cancel'])
def test_wechat_actual_buttons_and_transport(action, scenario):
    run_callback(action, scenario)


@pytest.mark.parametrize('status', ['sent', 'pending', 'failed', 'skipped', 'unknown'])
def test_resend_reports_delivery_status_separately(status):
    run_callback('resend', 'success', status)


@pytest.mark.parametrize('action', ['run', 'force'])
def test_master_switch_skip_is_not_sent_or_failed(action):
    run_callback(action, 'skipped')


def test_clear_skipped_payload():
    run_callback('clear_skipped', 'success')


def run_callback(action, scenario, log_status='sent'):
    page = (ROOT / 'app/templates/wechat_share.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
    buttons = re.findall(r'<button\b([^>]*onclick="([^"]+)"[^>]*)>', page)
    target = {'save': 'saveWechatShareConfig()', 'run': 'runWechatShareNow(false)',
              'force': 'runWechatShareNow(true)', 'resend': 'resendWechatShareLog({{ log.id }})',
              'clear': "clearWechatShareLogs('failed')", 'clear_skipped': "clearWechatShareLogs('failed')"}[action]
    button_source = next(attrs for attrs, callback in buttons if callback == target)
    callback = target.replace('{{ log.id }}', '7')
    if action == 'clear_skipped':
        callback = callback.replace('failed', 'skipped')
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario,resolveRequest,reloads=0,reentered=false;
const sent=[],messages=[],alerts=[],confirmations=[],events=[];
const buttons=[{disabled:false},{disabled:false},{disabled:true}];
const fields={csrf_token:'fixture-csrf',master_enabled:'1',sender_name:'fixture sender',sender_wechat_id:'fixture sender id',receiver_name:'fixture receiver',receiver_wechat_id:'fixture receiver id',receiver_search_key:'fixture search',receiver_type:'group',share_time:'15:30',wecom_webhook:'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=synthetic',helper_url:'http://127.0.0.1:8765/send',enabled:'1',share_in_order:'1',immediate_on_complete:'1',auto_send:'1'};
class TestFormData{constructor(form){this.fields=form?{...form.fields}:{};}append(k,v){this.fields[k]=v;}}
const nodes={autoSend:{addEventListener(){}},autoSendRiskHint:{style:{}},wechatShareForm:{fields}};
const ctx={Headers,FormData:TestFormData,document:{getElementById:id=>nodes[id],querySelector:()=>({content:'fixture-csrf'}),querySelectorAll:()=>buttons},
showToast:(m,t)=>messages.push({m,t}),confirm:m=>{
 if(m.includes('登录'))return false;
 confirmations.push(m);events.push('confirm');assert(buttons.every(b=>b.disabled),'lock before confirmation');
 if(!reentered){reentered=true;invoke();}return mode!=='cancel';
},alert:m=>{alerts.push(m);events.push('alert');assert.equal(reloads,0,'read result before reload');invoke();},
location:{href:'original',reload(){events.push('reload');reloads++;}},setTimeout(){},
fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>resolveRequest=()=>{
 if(mode==='network'){reject(Error('offline fixture'));return;}
 const status=mode==='http_json'?400:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
 const body=mode==='null'?null:{status:mode==='skipped'?'skipped':['business','http_json'].includes(mode)?'error':'success',msg:'fixture explanation',log_status:p.log_status,created:2,skipped:3};
 resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});
})}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const invoke=()=>vm.runInContext(p.callback,ctx),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const first=invoke();await flush();
 const confirmed=p.action!=='save';
 if(confirmed&&mode==='cancel'){await first;assert.equal(sent.length,0);assert.deepEqual(buttons.map(b=>b.disabled),[false,false,true]);assert.equal(alerts.length,0);return;}
 assert.equal(confirmations.length,confirmed?1:0);if(p.action==='force'){assert(confirmations[0].includes('重复发送'));assert(confirmations[0].includes('绕过'));}if(p.action==='run')assert(confirmations[0].includes('发送消息'));
 await invoke();assert.equal(sent.length,1,'pending action must not duplicate');
 const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.u,{save:'/wechat_share/save',run:'/wechat_share/run_now',force:'/wechat_share/run_now',resend:'/wechat_share/log/7/resend',clear:'/wechat_share/logs/clear',clear_skipped:'/wechat_share/logs/clear'}[p.action]);
 assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
 if(p.action==='resend')assert.equal(req.o.body,undefined);else{
  assert(req.o.body instanceof TestFormData);assert(!h.has('Content-Type'));
  assert.deepEqual(req.o.body.fields,p.action==='save'?fields:p.action==='force'?{force:'1'}:p.action==='run'?{}:{status:p.action==='clear_skipped'?'skipped':'failed'});
 }
 resolveRequest();await first;await flush();
 if(['success','cancel'].includes(mode)){
  assert.equal(alerts.length,1);assert.equal(reloads,1);assert.equal(events.at(-2),'alert');assert.equal(events.at(-1),'reload');assert(buttons.every(b=>b.disabled));
  if(['run','force'].includes(p.action))assert(alerts[0].includes('不代表全部发送成功'));
  if(p.action==='resend')assert(alerts[0].includes({sent:'已发送',pending:'待发送',failed:'发送失败',skipped:'已跳过',unknown:'未知'}[p.log_status]));
  await invoke();assert.equal(sent.length,1,'result/nav window remains locked');
 }else if(mode==='skipped'){
  assert.equal(alerts.length,1);assert.equal(alerts[0],'fixture explanation');assert.equal(messages.length,0);assert.equal(reloads,0);assert.deepEqual(buttons.map(b=>b.disabled),[false,false,true]);
 }else{
  assert.equal(alerts.length,0);assert.equal(reloads,0);assert.equal(messages.at(-1).t,'danger');assert.deepEqual(buttons.map(b=>b.disabled),[false,false,true]);
  if(['business','http_json'].includes(mode))assert(messages.at(-1).m.includes('fixture explanation'));if(mode==='html')assert(messages.at(-1).m.includes('503'));
  mode='success';const retry=invoke();await flush();resolveRequest();await retry;assert.equal(sent.length,2);assert.equal(reloads,1);
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for actual page callbacks'
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'callback': callback, 'action': action, 'scenario': scenario, 'log_status': log_status,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
    assert 'data-wechat-write' in button_source
    if action == 'force':
        assert '重新生成并再次发送今日入库单' in page
