'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(process.argv[2]+'/app/templates/mobile_scan.html','utf8');
const scenario=process.argv[3],flush=()=>new Promise(r=>setImmediate(r));
function node(){return {hidden:true,disabled:false,value:'',events:{},focus(){this.focused=true;},
 addEventListener(k,f){this.events[k]=f;},click(){this.events.click?.();}};}
async function run(){
 const messages=[],timers=new Map();let timerId=0,lookups=0;
 const ctx={Map,Promise,Error,AbortController,FormData:class{append(){}},
  setStatus:m=>messages.push(m),lookupMaterial:()=>lookups++,scanCode:node(),
  setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,delay});return id;},
  clearTimeout(id){timers.delete(id);}};
 function timer(delay){const found=[...timers].find(([,v])=>v.delay===delay);assert(found);timers.delete(found[0]);found[1].fn();}
 if(scenario.startsWith('scanner-')){
  const readerInstances=[],callbacks=[];let stops=0,resets=0;
  Object.assign(ctx,{barcodeScanner:node(),barcodeVideo:node(),barcodeBtn:node(),closeBarcodeBtn:node(),zxingCodeReader:null});
  ctx.window={addEventListener(k,fn){this[k]=fn;}};
  ctx.ZXing={BarcodeFormat:{},DecodeHintType:{},BrowserMultiFormatReader:class{
   constructor(){if(scenario==='scanner-init-throw')throw Error('synthetic init');readerInstances.push(this);}
   reset(){resets++;}
   decodeFromVideoDevice(_,video,callback){
    callbacks.push(callback);
    if(scenario==='scanner-sync-throw')throw Error('synthetic open');
    if(scenario==='scanner-no-device')return Promise.reject({name:'NotFoundError'});
    if(scenario==='scanner-busy')return Promise.reject({name:'NotReadableError'});
    video.srcObject={getTracks:()=>[
     {stop(){stops++;if(scenario==='scanner-track-stop-failure')throw Error('one track failed');}},
     {stop(){stops++;}}]};
    return Promise.resolve();
   }
  }};
  vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('    function stopBarcodeScanner()'),source.indexOf('    function addHistory(')),ctx);
  ctx.barcodeBtn.click();
  if(scenario==='scanner-init-throw'){assert(ctx.barcodeScanner.hidden);assert(messages.some(m=>m.includes('初始化失败')));return;}
  if(scenario==='scanner-cancel-before-open'){
   ctx.closeBarcodeBtn.click();timer(100);assert.equal(callbacks.length,0);assert(ctx.barcodeScanner.hidden);return;
  }
  timer(100);await flush();
  if(['scanner-no-device','scanner-busy','scanner-sync-throw'].includes(scenario)){
   assert(ctx.barcodeScanner.hidden);assert(messages.some(m=>m.includes(scenario==='scanner-no-device'?'未找到摄像头':scenario==='scanner-busy'?'占用':'无法打开摄像头')));assert.equal(lookups,0);return;
  }
  if(scenario==='scanner-disconnect'){
   callbacks[0](null,{name:'NotReadableError',message:'synthetic disconnected'});
   assert(messages.some(m=>m.includes('扫码失败')));
  }else if(scenario==='scanner-duplicate'){
   const result={getText:()=> ' QA30-CODE '};callbacks[0](result);callbacks[0](result);
   assert.equal(lookups,1);assert.equal(ctx.scanCode.value,'QA30-CODE');
  }else if(scenario==='scanner-late-callback'){
   ctx.closeBarcodeBtn.click();callbacks[0]({getText:()=> 'STALE'});assert.equal(lookups,0);assert.equal(ctx.scanCode.value,'');
  }else if(scenario==='scanner-pagehide')ctx.window.pagehide();
  else if(scenario==='scanner-track-stop-failure')ctx.closeBarcodeBtn.click();
  else throw Error('unhandled '+scenario);
  assert.equal(stops,2);assert.equal(ctx.barcodeVideo.srcObject,null);assert(ctx.barcodeScanner.hidden);assert(resets>=1);
  ctx.stopBarcodeScanner();assert.equal(stops,2,'release is idempotent');return;
 }
 const fields=Object.fromEntries(['cameraBtn','cameraFileInput','recognizePreview','recognizePreviewImg','recognizeLoading','closePreviewBtn'].map(k=>[k,node()]));
 const readers=[],requests=[];
 ctx.document={getElementById:id=>fields[id]};ctx.window={};ctx.renderMatches=()=>{};
 ctx.FileReader=class{constructor(){readers.push(this);}readAsDataURL(){}};
 ctx.WMS={api:{postRaw(url,body,options){return new Promise((resolve,reject)=>{
  requests.push({resolve,reject,options});options.signal.addEventListener('abort',()=>reject(Object.assign(Error('aborted'),{name:'AbortError'})));
 })}}};
 vm.createContext(ctx);vm.runInContext(source.slice(source.indexOf('    var cameraBtn ='),source.indexOf('    window.setTimeout(',source.indexOf('    var cameraBtn ='))),ctx);
 function select(){fields.cameraFileInput.events.change({target:{files:[{name:'QA30.png'}]}});readers.at(-1).onload({target:{result:'data:image/png;base64,synthetic'}});}
 select();assert(fields.cameraBtn.disabled);assert.equal(requests.length,1);
 if(scenario==='photo-timeout'){timer(60000);await flush();assert(requests[0].options.signal.aborted);assert(messages.some(m=>m.includes('识别超时')));}
 else if(scenario==='photo-network'){requests[0].reject(Error('synthetic offline'));await flush();assert(messages.includes('synthetic offline'));}
 else if(scenario==='photo-business-error'){requests[0].resolve({status:'error',msg:'synthetic rejected'});await flush();assert(messages.includes('synthetic rejected'));}
 else if(scenario==='photo-superseded'){
  select();await flush();assert(requests[0].options.signal.aborted);assert(fields.cameraBtn.disabled,'old finally cannot unlock new request');
  requests[0].resolve({status:'success',matches:[{code:'STALE'}]});requests[1].resolve({status:'success',matches:[{code:'QA30-NEW'}]});
  await flush();await flush();assert.equal(lookups,1);assert.equal(ctx.scanCode.value,'QA30-NEW');
 }else throw Error('unhandled '+scenario);
 await flush();assert(!fields.cameraBtn.disabled);assert(fields.recognizeLoading.hidden);assert.equal(timers.size,0,'network timeout timer released');
 if(scenario!=='photo-superseded')assert.equal(lookups,0);
}
run().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
