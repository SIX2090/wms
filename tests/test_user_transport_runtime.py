"""Real user-page callbacks with the production client; synthetic credentials only."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('action', ['add', 'edit', 'enable', 'disable', 'reset'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_json', 'html', 'invalid_json', 'null', 'primitive', '401', '419', 'network', 'cancel'])
def test_user_real_dom_transport(action, scenario):
    page = (ROOT / 'app/templates/user.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
    for endpoint, url in [('add_user', '/user/add'), ('update_user_status', '/user/status'), ('reset_user_password', '/user/reset_password')]:
        script = script.replace('{{ url_for("' + endpoint + '") }}', url)
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario,reloads=0,confirms=0,resolveRequest,resolveConfirm,modalShows=0;
const sent=[],messages=[],timers=[],handlers={},nodes={};
const fields={addForm:{username:'fixture-new',password:'synthetic-test-only',role:'warehouse',csrf_token:'fixture-csrf'},
 editForm:{user_id:'7',username:'fixture-edited',role:'purchase',status:'normal',csrf_token:'fixture-csrf'},
 resetForm:{user_id:'7',new_password:'synthetic-reset-only',bootstrap_pwd:'synthetic-confirm-only',csrf_token:'fixture-csrf'}};
for(const id of ['editUserId','editUsername','editRole','editStatus','resetUserId','resetUsername','resetBootstrapGroup','resetBootstrapPwd','editModal','resetModal'])nodes[id]={value:'',style:{},required:false};
const statusButton={disabled:false};
for(const [id,data] of Object.entries(fields))nodes[id]={id,fields:data,button:{disabled:false},addEventListener:(event,fn)=>handlers[id]=fn,querySelector(){return this.button;}};
class TestFormData{constructor(form){this.fields={...form.fields};}}
const ctx={Headers,FormData:TestFormData,document:{addEventListener:(event,fn)=>fn(),getElementById:id=>nodes[id],querySelector:s=>s.includes('new_password')?{}:{content:'fixture-csrf'}},
 initCheckAll(){},bootstrap:{Modal:class{show(){modalShows++;}}},showToast:(m,t)=>messages.push({m,t}),
 showConfirm:()=>{confirms++;return new Promise(r=>resolveConfirm=r);},confirm:()=>false,
 location:{href:'original',reload(){reloads++;}},setTimeout:(fn,delay)=>timers.push({fn,delay}),
 fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>resolveRequest=()=>{
  if(mode==='network'){reject(Error('offline'));return;}
  const status=mode==='http_json'?409:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
  const body=mode==='null'?null:mode==='primitive'?'unexpected':{status:['business','http_json'].includes(mode)?'error':'success',msg:'specific server explanation'};
  resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});
 })}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
// Open the existing modals through their real helpers, preserving fields and bootstrap confirmation.
ctx.editUser(7,'fixture-edited','purchase','normal');assert.equal(nodes.editUserId.value,7);assert.equal(nodes.editUsername.value,'fixture-edited');assert.equal(nodes.editRole.value,'purchase');assert.equal(nodes.editStatus.value,'normal');
ctx.resetPassword(7,'fixture-target',true);assert.equal(nodes.resetUserId.value,7);assert.equal(nodes.resetUsername.value,'fixture-target');assert.equal(nodes.resetBootstrapGroup.style.display,'');assert.equal(nodes.resetBootstrapPwd.required,true);
ctx.resetPassword(7,'fixture-target',false);assert.equal(nodes.resetBootstrapGroup.style.display,'none');assert.equal(nodes.resetBootstrapPwd.required,false);assert.equal(nodes.resetBootstrapPwd.value,'');
const initialShows=modalShows,isStatus=['enable','disable'].includes(p.action),formId={add:'addForm',edit:'editForm',reset:'resetForm'}[p.action];
const button=isStatus?statusButton:nodes[formId].button;
const click=()=>isStatus?ctx.toggleUserStatus(7,'fixture-target',p.action==='enable'?'normal':'disabled',button):handlers[formId].call(nodes[formId],{preventDefault(){}});
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const first=click();await flush();assert(button.disabled,'lock action immediately');
 await click();await flush();
 if(isStatus){assert.equal(confirms,1,'one human confirmation');assert.equal(sent.length,0);resolveConfirm(mode!=='cancel');await flush();}
 if(isStatus&&mode==='cancel'){await first;assert.equal(sent.length,0);assert.equal(button.disabled,false);return;}
 assert.equal(sent.length,1);await click();assert.equal(sent.length,1,'in-flight repeat must not send');
 const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.u,isStatus?'/user/status':{add:'/user/add',edit:'/user/7/edit',reset:'/user/reset_password'}[p.action]);
 assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
 if(isStatus){assert.equal(h.get('Content-Type'),'application/json');assert.deepEqual(JSON.parse(req.o.body),{user_id:7,status:p.action==='enable'?'normal':'disabled'});}
 else{assert(req.o.body instanceof TestFormData);assert(!h.has('Content-Type'));assert.deepEqual(req.o.body.fields,fields[formId]);}
 resolveRequest();await first;await flush();assert.equal(modalShows,initialShows,'submission does not reopen/replace modal');
 if(['success','cancel'].includes(mode)){
  if(p.action==='edit'){assert.equal(reloads,1);assert.equal(timers.length,0);}
  else{assert.equal(reloads,0);assert.equal(timers.length,1);assert.equal(timers[0].delay,650);assert.equal(messages.at(-1).t,'success');}
  await click();assert.equal(sent.length,1,'keep success locked through navigation');
  if(p.action!=='edit'){timers[0].fn();assert.equal(reloads,1);}
 }else{
  assert.equal(reloads,0);assert.equal(timers.filter(t=>t.delay===650).length,0);assert.equal(button.disabled,false);assert.equal(messages.at(-1).t,'danger');
  if(['business','http_json'].includes(mode))assert(messages.at(-1).m.includes('specific server explanation'));
  if(mode==='html')assert(messages.at(-1).m.includes('503'));
  mode='success';const retry=click();await flush();if(isStatus){resolveConfirm(true);await flush();}resolveRequest();await retry;assert.equal(sent.length,2);
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for actual user-page callback checks'
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'action': action, 'scenario': scenario,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize('was_admin,is_admin', [(True, True), (True, False), (False, True)])
def test_reset_target_change_clears_both_password_fields(was_admin, is_admin):
    page = (ROOT / 'app/templates/user.html').read_text(encoding='utf-8')
    script = re.search(r'<script>(.*?)</script>', page, re.S)[1]
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
const nodes={},password={value:''};
for(const id of ['resetUserId','resetUsername','resetBootstrapGroup','resetBootstrapPwd'])nodes[id]={value:'',style:{},required:false};
const ctx={document:{addEventListener:(e,f)=>f(),getElementById:id=>nodes[id],querySelector:()=>password},initCheckAll(){},bootstrap:{Modal:class{show(){}}}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.script,ctx);
ctx.resetPassword(7,'first fixture',p.was_admin);password.value='previous synthetic password';nodes.resetBootstrapPwd.value='previous synthetic bootstrap';
ctx.resetPassword(9,'second fixture',p.is_admin);
assert.equal(password.value,'','new password must never carry to another target');
assert.equal(nodes.resetBootstrapPwd.value,'','bootstrap confirmation must be re-entered');
assert.equal(nodes.resetUserId.value,9);assert.equal(nodes.resetUsername.value,'second fixture');
assert.equal(nodes.resetBootstrapPwd.required,p.is_admin);assert.equal(nodes.resetBootstrapGroup.style.display,p.is_admin?'':'none');
'''
    node = shutil.which('node')
    assert node
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'was_admin': was_admin, 'is_admin': is_admin,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
