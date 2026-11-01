'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [root,page,scenario,evidence]=process.argv.slice(2),p=JSON.parse(fs.readFileSync(0,'utf8'));
const handlers={},requests=[],pending=[],messages=[],timers=[];let confirms=0,reloads=0;
const buttons=[7,8,9].map((id,index)=>({dataset:{id:String(id)},disabled:index===2,
 addEventListener(name,callback){this[name+'Handler']=callback;}}));
const document={getElementById:id=>({id}),querySelector:selector=>selector.includes('csrf-token')?{content:'qa52-public-csrf'}:null,
 querySelectorAll(selector){return selector==='.revertBtn'?buttons:[];}};
function $(arg){if(arg===document)return{ready(fn){fn();}};return{
 change(fn){handlers[arg]=fn;},submit(fn){handlers[arg]=fn;},click(fn){handlers[arg]=fn;},
 data(key){return arg.dataset?.[key];},val(){return'7';},each(){},prop(){return false;}};}
const ctx={document,$,Headers,FormData:class{},initCheckAll(){},
 showToast:(message,type)=>messages.push({message,type}),
 confirm(){confirms++;return true;},showConfirm(){confirms++;return Promise.resolve(true);},
 setTimeout(fn,delay){timers.push({fn,delay});},location:{href:'/original',reload(){reloads++;}},
 bootstrap:{Modal:{getInstance:()=>({hide(){}})}},
 fetch(url,options){requests.push({url,method:options.method,csrf:options.headers['X-CSRFToken'],body:options.body});
  return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(root+'/app/static/js/api.js','utf8'),ctx);
vm.runInContext(p.script,ctx);
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
function click(button){if(button.disabled)return Promise.resolve();
 const fn=page==='transfer'?handlers['.revertBtn']:button.clickHandler;assert(fn);
 return Promise.resolve(fn.call(button,{preventDefault(){}}));}
function success(index){pending[index].resolve({status:200,ok:true,json:()=>Promise.resolve({status:'success',msg:'合成反提交成功'})});}
function state(){return{requests:[...requests],confirms,reloads,timers:timers.map(t=>t.delay),
 buttons:buttons.map(button=>({id:button.dataset.id,disabled:button.disabled,pending:button.dataset.revertPending||null})),messages:[...messages]};}
const proof={page,scenario,actual_template_script:true,actual_api_wrapper:true,
 real_browser:false,real_server:false,real_database:false,real_inventory:false,real_network:false};
async function run(){
 const a=buttons[0],b=buttons[1];
 const first=click(a);
 if(scenario==='pending-double-click'){
  click(a);const other=click(b);click(buttons[2]);await settle();proof.during_requests=state();
  assert.equal(requests.filter(r=>r.url==='/'+page+'/7/revert').length,1,'same pending row must not dispatch another revert');
  assert.equal(requests.filter(r=>r.url==='/'+page+'/8/revert').length,1,'independent row remains usable');
  assert.equal(confirms,2,'duplicate click must not open a second confirmation');
  assert(a.disabled&&b.disabled&&buttons[2].disabled);
  pending[0].reject(Error('QA52 synthetic network failure'));await first;await settle();proof.after_a_failure=state();
  assert(!a.disabled&&b.disabled&&buttons[2].disabled,'failed row unlocks without unlocking another inflight row');
  const retry=click(a);await settle();assert.equal(requests.length,3,'only a fresh manual retry dispatches after failure');
  assert.equal(requests[2].url,'/'+page+'/7/revert');
  success(2);await retry;await settle();assert(a.disabled&&b.disabled,'late A result must not unlock pending B');
  success(1);await other;await settle();assert(a.disabled&&b.disabled&&buttons[2].disabled);
  assert.deepEqual(timers.map(t=>t.delay),[650,650]);
 }else{
  await settle();assert.equal(requests.length,1);success(0);await first;await settle();
  proof.before_navigation=state();assert.deepEqual(timers.map(t=>t.delay),[650]);assert.equal(reloads,0);
  await click(a);await settle();proof.after_second_click=state();
  assert.equal(requests.length,1,'success waiting for refresh must not dispatch another revert');
  assert.equal(confirms,1);assert(a.disabled);assert(!b.disabled&&buttons[2].disabled);
  timers.shift().fn();assert.equal(reloads,1);
 }
 for(const request of requests){assert.equal(request.method,'POST');assert.equal(request.csrf,'qa52-public-csrf');assert.equal(request.body,undefined);
  assert(/^\/(transfer|adjustment)\/[78]\/revert$/.test(request.url),'no delete/save/complete path permitted');}
 proof.final_state=state();
}
const watchdog=setTimeout(()=>{process.stderr.write('QA52 unresolved simulation\n');process.exit(91);},5000);
run().then(()=>{proof.passed=true;}).catch(error=>{proof.passed=false;proof.error=String(error);proof.final_state=state();process.stderr.write(error.stack+'\n');process.exitCode=1;})
 .finally(()=>{clearTimeout(watchdog);fs.writeFileSync(evidence,JSON.stringify(proof,null,2));});
