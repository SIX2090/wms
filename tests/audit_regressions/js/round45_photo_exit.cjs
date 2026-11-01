'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [root,scenario,evidence]=process.argv.slice(2);
const text=fs.readFileSync(root+'/app/templates/mobile_scan.html','utf8');
const start=text.indexOf('    var cameraBtn ='),end=text.indexOf('    window.setTimeout(',start);
assert(start>0&&end>start);
const fields={},listeners={},readers=[],requests=[],messages=[],timers=new Map();let counter=0,lookups=0,renders=0;
function element(){return {hidden:true,disabled:false,value:'',events:{},addEventListener(k,fn){this.events[k]=fn;},click(){this.events.click?.();}};}
for(const key of ['cameraBtn','cameraFileInput','recognizePreview','recognizePreviewImg','recognizeLoading','closePreviewBtn'])fields[key]=element();
const ctx={document:{getElementById:key=>fields[key]},window:{addEventListener(key,fn){(listeners[key]??=[]).push(fn);}},
 FileReader:class{constructor(){readers.push(this);}readAsDataURL(){}},FormData:class{append(){}},AbortController,
 setTimeout(fn,delay){const id=++counter;timers.set(id,{fn,delay});return id;},clearTimeout(id){timers.delete(id);},
 scanCode:element(),setStatus:(message)=>messages.push(message),lookupMaterial:()=>lookups++,renderMatches:()=>renders++,
 WMS:{api:{postRaw(url,body,options){assert.equal(url,'/mobile/api/recognize_material');return new Promise(resolve=>requests.push({resolve,options}));}}}};
vm.createContext(ctx);vm.runInContext(text.slice(start,end),ctx);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const emitLeave=()=>{for(const fn of listeners.pagehide||[])fn({type:'pagehide',persisted:true});};
const select=()=>fields.cameraFileInput.events.change({target:{files:[{name:'QA45_SYNTHETIC.png'}]}});
const read=()=>readers.at(-1).onload({target:{result:'data:image/png;base64,QA45_SYNTHETIC'}});
const answer=(request,code)=>request.resolve({status:'success',matches:[{code}]});
const proof={scenario,real_browser:false,real_device:false,real_network:false};
async function run(){
 select();
 if(scenario==='leave-during-read'){
  assert.equal(requests.length,0);emitLeave();read();await flush();
  proof.after_leave={requests:requests.length,camera_disabled:fields.cameraBtn.disabled,preview_hidden:fields.recognizePreview.hidden};
  assert.equal(requests.length,0,'pagehide must invalidate a pending file read before it can submit recognition');
 }else{
  read();assert.equal(requests.length,1);
  if(scenario==='leave-during-request'){
   emitLeave();proof.aborted_on_leave=requests[0].options.signal.aborted;
   answer(requests[0],'QA45-OLD');await flush();await flush();
   proof.after_leave={lookups,renders,code:ctx.scanCode.value,camera_disabled:fields.cameraBtn.disabled,preview_hidden:fields.recognizePreview.hidden,timers:timers.size};
   assert(proof.aborted_on_leave,'pagehide must abort the in-flight recognition request');
  }else if(scenario==='leave-before-success-callback'){
   answer(requests[0],'QA45-OLD');emitLeave();await flush();await flush();
   proof.after_leave={lookups,renders,code:ctx.scanCode.value,camera_disabled:fields.cameraBtn.disabled,preview_hidden:fields.recognizePreview.hidden,timers:timers.size};
  }else throw Error('Unknown scenario');
 }
 assert.equal(lookups,0,'a departed page must not select a late recognition result');
 assert.equal(renders,0);assert.equal(ctx.scanCode.value,'');
 assert(!fields.cameraBtn.disabled&&fields.recognizePreview.hidden&&fields.recognizeLoading.hidden);
 assert.equal(timers.size,0);
 // Simulate a restored page receiving a NEW explicit selection, not auto replay.
 const oldCount=requests.length;select();read();assert.equal(requests.length,oldCount+1);
 answer(requests.at(-1),'QA45-NEW');await flush();await flush();
 assert.equal(lookups,1);assert.equal(ctx.scanCode.value,'QA45-NEW');assert(!fields.cameraBtn.disabled);assert.equal(timers.size,0);
 proof.normal_new_selection={lookups,code:ctx.scanCode.value,old_result_ignored:true};
 proof.passed=true;
}
run().catch(error=>{proof.passed=false;proof.error=String(error);process.stderr.write(error.stack+'\n');process.exitCode=1;})
 .finally(()=>fs.writeFileSync(evidence,JSON.stringify(proof,null,2)));
