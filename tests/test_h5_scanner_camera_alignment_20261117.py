"""Real ZXing stream-entry/focus contract; synthetic media and no app or DB."""
from pathlib import Path
import shutil
import subprocess

import pytest


PROGRAM = r"""
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict');
const root=process.argv[1],scenario=process.argv[2];
const Z=require(path.join(root,'app/static/cdn/zxing-library-0.23.0.min.js'));
const source=fs.readFileSync(path.join(root,'app/templates/mobile_scan.html'),'utf8');
const begin=source.indexOf('    function stopBarcodeScanner()'),end=source.indexOf('    function addHistory(',begin);
assert(begin>=0&&end>begin,'The real scanner handler block is required');
const originalTimer=globalThis.setTimeout,originalNavigator=Object.getOwnPropertyDescriptor(globalThis,'navigator');
const acquisition=[],sdkTimers=[],uiTimers=[],readers=[],messages=[],unhandled=[],allMedia=[];
const warnings=console.warn,errors=console.error;
let lookups=0;
const unhandledListener=error=>unhandled.push(error);
process.on('unhandledRejection',unhandledListener);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
const element=()=>({hidden:true,value:'',srcObject:null,events:{},focus(){},removeAttribute(){},
  addEventListener(name,fn){this.events[name]=fn;},removeEventListener(){}});
class ActualReader extends Z.BrowserMultiFormatReader {
  constructor(hints){super(hints);this.attaches=0;this.decoded=0;readers.push(this);}
  // Only the DOM/playback edge is synthetic. The real SDK still performs its
  // video-device -> constraints -> stream -> reset -> continuous-decode chain.
  attachStreamToVideo(stream,video){this.attaches++;this.stream=stream;this.videoElement=video;video.srcObject=stream;return Promise.resolve(video);}
  decode(){this.decoded++;const size=64,pixels=new Uint8ClampedArray(size*size).fill(255);
    return this.decodeBitmap(new Z.BinaryBitmap(new Z.HybridBinarizer(new Z.RGBLuminanceSource(pixels,size,size))));}
}
class LegacyAdapter {
  constructor(){readers.push(this);}
  reset(){}
  decodeFromVideoDevice(){this.opened=true;return Promise.resolve();}
}
const ctx={Map,Promise,Error,console,document:{},window:{addEventListener(){}},
  ZXing:{...Z,BrowserMultiFormatReader:scenario==='legacy-adapter'?LegacyAdapter:ActualReader},
  barcodeScanner:element(),barcodeVideo:element(),barcodeBtn:element(),closeBarcodeBtn:element(),scanCode:element(),zxingCodeReader:null,
  setTimeout(fn,delay){uiTimers.push({fn,delay});return uiTimers.length;},clearTimeout(){},
  setStatus(message,type){messages.push({message,type});},lookupMaterial(){lookups++;}};
function beginSession(){ctx.barcodeBtn.events.click();const reader=ctx.zxingCodeReader,timer=uiTimers.shift();assert(timer&&timer.delay===100);timer.fn();return reader;}
function stream(mode='continuous'){
  let rejectFocus;
  const pending=new Promise((resolve,reject)=>{rejectFocus=reject;});
  const track={readyState:'live',stops:0,capabilityReads:0,constraints:[],
    stop(){this.stops++;this.readyState='ended';},
    getCapabilities(){this.capabilityReads++;if(mode==='capabilities-throw')throw Error('synthetic capability failure');
      if(mode==='empty-capabilities')return {};
      if(mode==='manual-only')return {focusMode:['manual']};
      if(mode==='string-capability')return {focusMode:'continuous'};
      return {focusMode:['manual','continuous']};},
    applyConstraints(value){this.constraints.push(value);
      if(mode==='apply-throw')throw Error('synthetic optional focus failure');
      if(mode==='apply-reject')return Promise.reject(Error('synthetic optional focus rejection'));
      if(mode==='apply-pending')return pending;
      return Promise.resolve();}};
  if(mode==='no-capability-api')delete track.getCapabilities;
  if(mode==='no-apply-api')delete track.applyConstraints;
  if(mode==='ended-track')track.readyState='ended';
  const video={track,getTracks:()=>[track],getVideoTracks:()=>[track],rejectFocus};
  if(mode==='no-video-tracks-api')delete video.getVideoTracks;
  if(mode==='video-tracks-throw')video.getVideoTracks=()=>{throw Error('synthetic video-track API failure');};
  if(mode==='video-tracks-empty'){
    // A video-only request with no video tracks has no active tracks to stop.
    // Keep getTracks consistent with getVideoTracks rather than inventing an
    // unreachable camera track hidden from the native SDK's stop routine.
    video.getVideoTracks=()=>[];video.getTracks=()=>[];
  }
  allMedia.push(video);
  return video;
}
async function acquired(reader,media){
  const request=acquisition.shift();assert(request,'The real SDK must request a camera');
  assert.deepEqual(request.constraints,{video:{facingMode:'environment'}},'Keep the original rear-camera acquisition protocol');
  request.resolve(media);await flush();await flush();
  assert.equal(reader.attaches,1,'Optional focus must not block or replace the real SDK stream entry');
  assert(reader.decoded>=1,'The real SDK continuous loop must reach real blank-pixel decoding');
  assert.equal(ctx.barcodeVideo.srcObject,media);assert.equal(ctx.barcodeScanner.hidden,false);
}
function focusApplied(media){assert.equal(media.track.constraints.length,1,'A supported continuous-focus track must receive exactly one focus request');
  assert.deepEqual(JSON.parse(JSON.stringify(media.track.constraints[0])),{advanced:[{focusMode:'continuous'}]});}
async function run(){
  globalThis.setTimeout=(fn,delay)=>{sdkTimers.push({fn,delay});return sdkTimers.length;};
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaDevices:{getUserMedia(constraints){return new Promise((resolve,reject)=>acquisition.push({constraints,resolve,reject}));}}}});
  console.warn=()=>{};console.error=()=>{};
  vm.createContext(ctx);vm.runInContext(source.slice(begin,end),ctx,{filename:'real-mobile-scanner-handler.js'});
  if(scenario==='legacy-adapter'){
    const reader=beginSession();await flush();assert(reader.opened);assert.equal(ctx.barcodeScanner.hidden,false);ctx.stopBarcodeScanner();
  }else if(scenario==='stale-stream'||scenario==='cancelled-stream'){
    const first=beginSession(),request=acquisition.shift(),old=stream();assert(request);
    let current,newMedia;
    if(scenario==='stale-stream'){current=beginSession();newMedia=stream();await acquired(current,newMedia);focusApplied(newMedia);}
    else ctx.closeBarcodeBtn.events.click();
    request.resolve(old);await flush();await flush();
    assert.equal(first.attaches,0,'A late old stream cannot attach to the shared video');
    assert.equal(first.decoded,0);assert.equal(old.track.capabilityReads,0,'Identity validation must precede capability reads');
    assert.equal(old.track.constraints.length,0,'A cancelled stream cannot request focus');assert(old.track.stops>=1);
    if(current){assert.equal(ctx.zxingCodeReader,current);assert.equal(ctx.barcodeVideo.srcObject,newMedia);assert.equal(newMedia.track.stops,0);}
    else{assert.equal(ctx.zxingCodeReader,null);assert.equal(ctx.barcodeVideo.srcObject,null);assert(ctx.barcodeScanner.hidden);}
  }else if(scenario==='late-focus-rejection'){
    const first=beginSession(),old=stream('apply-pending');await acquired(first,old);focusApplied(old);
    const current=beginSession(),currentMedia=stream();await acquired(current,currentMedia);focusApplied(currentMedia);
    const before=JSON.stringify(messages);old.rejectFocus(Error('synthetic late focus rejection'));await flush();await flush();
    assert.equal(JSON.stringify(messages),before,'A late optional failure cannot overwrite the new session status');
    assert.equal(ctx.zxingCodeReader,current);assert.equal(ctx.barcodeVideo.srcObject,currentMedia);assert.equal(currentMedia.track.stops,0);assert.equal(ctx.barcodeScanner.hidden,false);
    assert(old.track.stops>=1);assert.equal(old.track.constraints.length,1);
  }else{
    const reader=beginSession(),media=stream(scenario);await acquired(reader,media);
    if(['continuous','apply-throw','apply-reject','apply-pending'].includes(scenario))focusApplied(media);
    else assert.equal(media.track.constraints.length,0,'Unsupported/ended tracks must keep the camera default');
    if(scenario==='apply-pending'){
      assert(reader.decoded>=1,'Never await focus before decoding');media.rejectFocus(Error('synthetic focus settlement'));await flush();
    }
    assert(!messages.some(item=>item.type==='error'),'Optional camera controls must not report a fatal scanner error');
    assert.equal(media.track.stops,0,'An optional focus failure must not stop the active stream');
    if(['no-video-tracks-api','video-tracks-throw','video-tracks-empty'].includes(scenario)){
      assert.equal(media.track.capabilityReads,0,'Unavailable stream-track APIs cannot trigger capability access');
      ctx.closeBarcodeBtn.events.click();await flush();
      assert.equal(ctx.barcodeVideo.srcObject,null,'Cancel must detach the unsupported stream');
      assert(media.getTracks().every(track=>track.readyState==='ended'),'Cancel must release every actual stream track');
      assert(!messages.some(item=>item.type==='error'),'API fallback and cancel cannot report a camera failure');
    }
  }
  ctx.stopBarcodeScanner();await flush();await flush();
  assert.equal(lookups,0);assert.equal(unhandled.length,0,'Every optional focus rejection must be consumed');
  assert.equal(ctx.zxingCodeReader,null);assert.equal(ctx.barcodeVideo.srcObject,null);assert(ctx.barcodeScanner.hidden);
  assert(allMedia.every(media=>media.getTracks().every(track=>track.readyState==='ended')),'No synthetic media track may survive cancellation');
  console.log(JSON.stringify({passed:true,scenario,real_sdk_stream_entry:scenario!=='legacy-adapter',real_blank_pixel_decoder:scenario!=='legacy-adapter',synthetic_capabilities:true}));
}
run().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;}).finally(()=>{
  globalThis.setTimeout=originalTimer;
  if(originalNavigator)Object.defineProperty(globalThis,'navigator',originalNavigator);else delete globalThis.navigator;
  console.warn=warnings;console.error=errors;process.removeListener('unhandledRejection',unhandledListener);
});
"""


@pytest.mark.parametrize('scenario', [
    'continuous', 'no-capability-api', 'empty-capabilities', 'manual-only',
    'string-capability', 'no-apply-api', 'ended-track', 'capabilities-throw',
    'apply-throw', 'apply-reject', 'apply-pending', 'stale-stream',
    'cancelled-stream', 'late-focus-rejection', 'legacy-adapter',
    'no-video-tracks-api', 'video-tracks-throw', 'video-tracks-empty',
])
def test_real_zxing_camera_focus_stream_boundaries(scenario):
    root = Path(__file__).resolve().parents[1]
    node = shutil.which('node')
    assert node, 'Node is required for the actual vendored ZXing contract'
    result = subprocess.run(
        [node, '--max-old-space-size=96', '--require',
         str(root / 'tests/audit_regressions/network_guard.cjs'),
         '-e', PROGRAM, str(root), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"passed":true' in result.stdout
