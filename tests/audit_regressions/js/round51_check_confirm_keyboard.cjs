'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [root,scenario,evidence]=process.argv.slice(2),p=JSON.parse(fs.readFileSync(0,'utf8'));
const shared=fs.readFileSync(root+'/app/static/js/app.js','utf8');
function func(source,name){const match=new RegExp('function '+name+'\\(').exec(source);assert(match,name);let depth=0;
 for(let i=source.indexOf('{',match.index);i<source.length;i++){depth+=(source[i]==='{')-(source[i]==='}');if(!depth)return source.slice(match.index,i+1);}throw Error(name);}
const calls=[],pending=[],timers=[],messages=[],handlers={},modals=new Map();let saveClicks=0,prevented=0,forceButton=null;
const fields=Object.fromEntries(Object.entries({order_id:'7',order_no:'FIXTURE-7',date:'2026-11-01',warehouse_id:'1',remark:'QA51 synthetic'})
 .map(([name,value])=>[name,{value}]));
const rowFields=Object.fromEntries(Object.entries({'.material-code':'M1','.unit-id':'1','.line-area':'区域','.system-stock':'2','.actual-stock':'3','.line-reason':'合成盘盈'})
 .map(([key,value])=>[key,{value,style:{}}]));
const row={dataset:{counted:'true'},querySelector:key=>rowFields[key]||null};
const buttons=p.controls.map(attrs=>({attrs,disabled:'disabled' in attrs,
 getAttribute(key){return this.attrs[key]??null;},hasAttribute(key){return key in this.attrs;},
 matches(selector){return selector===':disabled'&&this.disabled;},closest(){return null;},getClientRects(){return[{}];},
 click(){if(this.disabled)return;if('data-wms-save' in this.attrs)saveClicks++;return vm.runInContext(this.attrs.onclick,ctx);}}));
class Modal{
 constructor(){this.id='';this.attrs={};this.style={};this.innerHTML='';}
 setAttribute(key,value){this.attrs[key]=String(value);}getAttribute(key){return this.attrs[key]??null;}
 remove(){modals.delete(this.id);forceButton=null;}
 getClientRects(){return modals.has(this.id)?[{}]:[];}
}
const content={querySelectorAll(selector){assert.equal(selector,'button[data-wms-save]');return buttons.filter(b=>'data-wms-save' in b.attrs);}};
const document={
 querySelector(selector){
  if(selector==='.embedded-content')return content;
  if(selector.startsWith('meta'))return{content:'qa51-public-csrf'};
  const name=(selector.match(/name="([^"]+)"/)||[])[1];if(name)return fields[name]||null;
  for(const part of selector.split(',').map(s=>s.trim())){
   if(part==='#completeConfirmModal'&&modals.has('completeConfirmModal'))return modals.get('completeConfirmModal');
   if(part==='[role="dialog"]')for(const modal of modals.values())if(modal.attrs.role==='dialog')return modal;
   // The actual custom modal has no Bootstrap/show class or cb-confirm-overlay class.
  }return null;
 },
 querySelectorAll(selector){if(selector==='#docTableBody tr')return[row];
  if(selector==='.doc-header button, #forceCompleteBtn')return[...buttons,...(forceButton?[forceButton]:[])];return[];},
 getElementById(id){return id==='forceCompleteBtn'?forceButton:modals.get(id)||null;},
 addEventListener(name,handler){(handlers[name]??=[]).push(handler);},createElement(){return new Modal();},
 body:{appendChild(modal){modals.set(modal.id,modal);forceButton={disabled:false,onclick:null};}}};
const ctx={document,FormData:class{},URLSearchParams,Promise,
 location:{href:'/check/7',reload(){throw Error('No reload expected');}},
 showToast:(message,type)=>messages.push({message,type}),confirm(){throw Error('No native confirmation expected');},
 showDocumentCompletionIssue(){throw Error('Unexpected completion failure in keyboard-only scenario');},
 setTimeout(fn,delay){timers.push({fn,delay});},
 fetch(url,options){calls.push({url,body:JSON.parse(options.body),csrf:options.headers['X-CSRFToken']});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
ctx.window=ctx;ctx.getComputedStyle=()=>({visibility:'visible'});
vm.createContext(ctx);vm.runInContext(fs.readFileSync(root+'/app/static/js/api.js','utf8'),ctx);
vm.runInContext(fs.readFileSync(root+'/app/static/js/decimal-input.js','utf8'),ctx);
vm.runInContext(p.script,ctx);vm.runInContext(func(shared,'initKeyboardShortcuts'),ctx);ctx.initKeyboardShortcuts();
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
function pressSave(){const event={ctrlKey:true,metaKey:false,altKey:false,shiftKey:false,key:'s',keyCode:83,repeat:false,
 defaultPrevented:false,isComposing:false,target:{tagName:'BODY',isContentEditable:false},preventDefault(){prevented++;this.defaultPrevented=true;}};
 for(const handler of handlers.keydown||[])handler(event);}
const proof={scenario,actual_rendered_check_template:true,actual_global_keyboard_handler:true,actual_api_wrapper:true,
 real_browser:false,real_server:false,real_database:false,real_inventory:false,real_network:false};
function observe(){const modal=modals.get('completeConfirmModal');return{calls:[...calls],save_clicks:saveClicks,prevented,
 modal_present:!!modal,modal_attrs:modal?.attrs||{},pending:vm.runInContext('!!submitForm.pending',ctx),
 completed:vm.runInContext('!!submitForm.completed',ctx),navigation:ctx.location.href,messages:[...messages]};}
async function run(){
 const first=ctx.runComplete('/check/7/complete',false,7);assert.equal(calls.length,1);
 assert.deepEqual(calls[0].body,{force:false});assert.equal(calls[0].csrf,'qa51-public-csrf');
 pending[0].resolve({ok:true,status:200,json:()=>Promise.resolve({status:'confirm',code:'period_movement',
  msg:'合成盘点期间发生变动，请核对',count:1,samples:[{code:'QA51-M',name:'合成物料',net:3}]})});
 await first;await settle();assert(modals.has('completeConfirmModal'));assert.equal(calls.length,1);
 assert.equal(vm.runInContext('!!submitForm.pending',ctx),false);
 if(scenario==='after-cancel'){
  const modal=modals.get('completeConfirmModal');
  const cancel=modal.innerHTML.match(/class="btn btn-secondary" onclick="([^"]+)"/);assert(cancel,'actual cancel handler');
  vm.runInContext(cancel[1],ctx);assert(!modals.has('completeConfirmModal'));
 }
 pressSave();await settle();proof.after_shortcut=observe();
 if(scenario==='open-risk-dialog'){
  assert.equal(calls.length,1,'Ctrl+S must not save the underlying check while its risk dialog is open');
  assert.equal(saveClicks,0);assert(modals.has('completeConfirmModal'));assert.equal(ctx.location.href,'/check/7');
  assert(!calls.some(call=>call.body.force===true));
 }else{
  assert.equal(calls.length,2,'ordinary save resumes only after actual cancellation');assert.equal(saveClicks,1);
  assert.equal(calls[1].url,'/check/save_table');assert.equal(calls[1].body.order_id,'7');
  assert(!calls.some(call=>call.body.force===true));
  pending[1].resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',id:7,order_no:'FIXTURE-7'})});
  await settle();assert(timers.some(t=>t.delay===500));
 }
 assert.equal(prevented,1);proof.final_state=observe();
}
const watchdog=setTimeout(()=>{process.stderr.write('QA51 unresolved simulation\n');process.exit(91);},5000);
run().then(()=>{proof.passed=true;}).catch(error=>{proof.passed=false;proof.error=String(error);proof.final_state=observe();process.stderr.write(error.stack+'\n');process.exitCode=1;})
 .finally(()=>{clearTimeout(watchdog);fs.writeFileSync(evidence,JSON.stringify(proof,null,2));});
