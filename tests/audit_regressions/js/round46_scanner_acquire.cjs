'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [root,scenario,evidence]=process.argv.slice(2),flush=()=>new Promise(resolve=>setImmediate(resolve));
const source=fs.readFileSync(root+'/app/templates/mobile_scan.html','utf8');
const library=fs.readFileSync(root+'/app/static/cdn/zxing-library-0.23.0.min.js','utf8');
const pending=[],instances=[],loops=[],streams=[],timers=new Map(),messages=[];let timerId=0,lookups=0,allowPlay=scenario!=='cancel-before-playing';
function element(){return {hidden:true,value:'',events:{},focus(){},addEventListener(key,fn){this.events[key]=fn;},click(){this.events.click?.();}};}
class Video{
 constructor(){this.handlers={};this.attributes={};this._stream=null;this.currentTime=0;this.paused=true;this.ended=false;this.readyState=0;}
 get srcObject(){return this._stream;}
 set srcObject(value){this._stream=value;this.currentTime=0;this.paused=true;this.readyState=0;}
 setAttribute(key,value){this.attributes[key]=value;}
 removeAttribute(key){delete this.attributes[key];}
 addEventListener(key,fn){(this.handlers[key]??=new Set()).add(fn);}
 removeEventListener(key,fn){this.handlers[key]?.delete(fn);}
 emit(key){for(const fn of [...(this.handlers[key]||[])])fn({type:key});}
 play(){if(allowPlay)queueMicrotask(()=>{this.currentTime=1;this.paused=false;this.readyState=4;this.emit('playing');});return Promise.resolve();}
}
const ctx={console:{log(){},warn(){},error(message){messages.push(String(message));}},
 Map,Promise,Error,HTMLVideoElement:Video,
 navigator:{mediaDevices:{getUserMedia(constraints){assert.equal(constraints.video.facingMode,'environment');return new Promise(resolve=>pending.push({resolve,constraints}));}}},
 document:{createElement(){throw Error('No canvas/image or physical capture allowed');}},
 setTimeout(fn,delay){const id=++timerId;timers.set(id,{fn,delay});return id;},clearTimeout(id){timers.delete(id);},
 barcodeScanner:element(),barcodeVideo:new Video(),barcodeBtn:element(),closeBarcodeBtn:element(),
 scanCode:element(),zxingCodeReader:null,setStatus:message=>messages.push(message),lookupMaterial:()=>lookups++,
 window:{handlers:{},addEventListener(key,fn){(this.handlers[key]??=[]).push(fn);}}};
vm.createContext(ctx);vm.runInContext(library,ctx,{filename:'bundled-zxing-0.23.0.js'});
const BaseReader=ctx.ZXing.BrowserMultiFormatReader;
// Keep actual SDK acquisition, stream attachment, playback and reset. Skip ONLY pixels/decoding loop.
ctx.ZXing.BrowserMultiFormatReader=class extends BaseReader{
 constructor(...args){super(...args);instances.push(this);}
 decodeContinuously(video,callback){this._stopContinuousDecode=false;loops.push({reader:this,video,callback});}
};
vm.runInContext(source.slice(source.indexOf('    function stopBarcodeScanner()'),source.indexOf('    function addHistory(')),ctx);
function stream(id){const tracks=[0,1].map(index=>({id:id+'-'+index,readyState:'live',stops:0,stop(){this.stops++;this.readyState='ended';}}));
 const result={id,tracks,getTracks:()=>tracks,getVideoTracks:()=>tracks};streams.push(result);return result;}
function begin(){ctx.barcodeBtn.click();const timer=[...timers].find(([,item])=>item.delay===100);assert(timer);timers.delete(timer[0]);timer[1].fn();}
async function settle(){for(let i=0;i<4;i++)await flush();}
function leave(){for(const fn of ctx.window.handlers.pagehide||[])fn({type:'pagehide',persisted:true});}
function active(){return loops.filter(loop=>loop.reader._stopContinuousDecode===false);}
function state(){return {visible:!ctx.barcodeScanner.hidden,attached_stream:ctx.barcodeVideo.srcObject?.id||null,
 active_decoders:active().length,lookups,code:ctx.scanCode.value,
 streams:streams.map(value=>({id:value.id,tracks:value.tracks.map(track=>({state:track.readyState,stops:track.stops}))}))};}
const proof={scenario,real_browser:false,real_hardware:false,real_network:false,
 bundled_sdk_acquisition_attachment_reset:true,pixel_decode_substituted:true};
async function run(){
 begin();assert.equal(pending.length,1);const a=stream('A');
 if(scenario==='cancel-after-request')ctx.closeBarcodeBtn.click();
 else if(scenario==='pagehide-after-request')leave();
 else if(scenario==='old-acquire-after-new-session'){
  begin();assert.equal(pending.length,2);const b=stream('B');pending[1].resolve(b);await settle();
  assert.equal(ctx.barcodeVideo.srcObject,b);assert.equal(active().length,1);
 }else if(scenario==='cancel-before-playing'){
  pending[0].resolve(a);await settle();assert.equal(ctx.barcodeVideo.srcObject,a);assert.equal(loops.length,0);
  ctx.closeBarcodeBtn.click();ctx.barcodeVideo.emit('playing');await settle();
 }else throw Error('Unknown scenario');
 if(scenario!=='cancel-before-playing'){pending[0].resolve(a);await settle();}
 proof.after_late_completion=state();
 assert(a.tracks.every(track=>track.readyState==='ended'),'late acquired stream A must not remain live after cancellation');
 if(scenario==='old-acquire-after-new-session'){
  const b=streams.find(value=>value.id==='B');assert.equal(ctx.barcodeVideo.srcObject,b,'late old A must not replace new B video');
  assert(b.tracks.every(track=>track.readyState==='live'),'old completion must not stop new B');
  assert.equal(active().length,1);assert.equal(active()[0].reader,instances[1]);
 }else{
  assert.equal(ctx.barcodeVideo.srcObject,null);assert(ctx.barcodeScanner.hidden);
  assert.equal(active().length,0,'late playing completion must not restart an obsolete decoder');
 }
 assert.equal(lookups,0);assert.equal(ctx.scanCode.value,'');
 // Positive control: current stream decodes exactly once, then normal close releases resources.
 allowPlay=true;
 if(scenario!=='old-acquire-after-new-session'){
  begin();const b=stream('FRESH');pending.at(-1).resolve(b);await settle();
 }
 const current=active().at(-1);assert(current);current.callback({getText:()=> ' QA46-CURRENT '});
 assert.equal(lookups,1);assert.equal(ctx.scanCode.value,'QA46-CURRENT');assert.equal(ctx.barcodeVideo.srcObject,null);
 assert(ctx.barcodeScanner.hidden);assert(streams.every(value=>value.tracks.every(track=>track.readyState==='ended')));
 proof.normal_control=state();proof.passed=true;
}
run().catch(error=>{proof.passed=false;proof.error=String(error);proof.final_state=state();process.stderr.write(error.stack+'\n');process.exitCode=1;})
 .finally(()=>fs.writeFileSync(evidence,JSON.stringify(proof,null,2)));
