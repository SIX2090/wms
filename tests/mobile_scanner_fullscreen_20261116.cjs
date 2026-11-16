'use strict';
// Real vendored ZXing pixels/errors; optional actual Chromium + canvas camera.
// Never imports WMS, opens a DB, uses hardware or contacts an existing service.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const opts={};
for(let i=2;i<process.argv.length;i+=2){assert(process.argv[i].startsWith('--')&&process.argv[i+1]);opts[process.argv[i].slice(2)]=process.argv[i+1];}
const root=path.resolve(opts.root||path.join(__dirname,'..'));
const sourceFile=path.resolve(opts.source||path.join(root,'app/templates/mobile_scan.html'));
const source=fs.readFileSync(sourceFile,'utf8');
const libraryPath=path.join(root,'app/static/cdn/zxing-library-0.23.0.min.js');
const start=source.indexOf('    function stopBarcodeScanner()'),end=source.indexOf('    function addHistory(',start);
assert(start>=0&&end>start,'The real stop/start handler block must be present');
const handlers=source.slice(start,end);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const proof={template_sha256:sha(source),sdk_sha256:sha(fs.readFileSync(libraryPath)),scope:'Synthetic pixels/streams only; no WMS app/database/production/hardware/external URL',checks:[]};

function quietSDK(operation){const warn=console.warn,error=console.error;console.warn=()=>{};console.error=()=>{};try{return operation();}finally{console.warn=warn;console.error=error;}}
function pixels(Z,text){const size=256,out=new Uint8ClampedArray(size*size).fill(255);if(text){const matrix=new Z.QRCodeWriter().encode(text,Z.BarcodeFormat.QR_CODE,size,size,new Map());for(let y=0;y<size;y++)for(let x=0;x<size;x++)out[y*size+x]=matrix.get(x,y)?0:255;}return new Z.BinaryBitmap(new Z.HybridBinarizer(new Z.RGBLuminanceSource(out,size,size)));}
function decode(Z,text){return quietSDK(()=>{const reader=new Z.MultiFormatReader();reader.setHints(new Map([[Z.DecodeHintType.POSSIBLE_FORMATS,[Z.BarcodeFormat.QR_CODE]]]));return reader.decodeWithState(pixels(Z,text));});}
function nodeHarness(Z){
  const callbacks=[],messages=[],timers=[];let lookups=0;
  const element=()=>({hidden:true,value:'',events:{},srcObject:null,focus(){},addEventListener(name,fn){this.events[name]=fn;},click(){this.events.click?.();}});
  class Reader extends Z.BrowserMultiFormatReader{decodeFromVideoDevice(_,video,callback){callbacks.push(callback);video.srcObject={getTracks:()=>[{stop(){}}]};return Promise.resolve();}}
  const context={Map,Promise,Error,DOMException,console,document:{},window:{addEventListener(){}},
    ZXing:{...Z,BrowserMultiFormatReader:Reader},barcodeScanner:element(),barcodeVideo:element(),barcodeBtn:element(),closeBarcodeBtn:element(),scanCode:element(),zxingCodeReader:null,
    setTimeout(fn,delay){timers.push({fn,delay});return timers.length;},clearTimeout(){},setStatus(message){messages.push(message);},lookupMaterial(){lookups++;}};
  vm.createContext(context);vm.runInContext(handlers,context,{filename:sourceFile});
  return {context,callbacks,messages,get lookups(){return lookups;},begin(){context.barcodeBtn.click();const timer=timers.find(t=>t.delay===100);assert(timer,'Real delayed start must be scheduled');timer.fn();}};
}
async function nodeCheck(scenario){
  const Z=require(libraryPath),h=nodeHarness(Z);h.begin();assert.equal(h.callbacks.length,1);
  if(scenario==='fatal-callback'){
    h.callbacks[0](null,new DOMException('Synthetic camera disconnected','NotReadableError'));
    assert.equal(h.context.barcodeScanner.hidden,true);assert.equal(h.lookups,0);assert(h.messages.some(m=>m.includes('扫码失败')));
  }else{
    let miss;
    if(scenario==='decode-miss'){try{decode(Z,null);}catch(error){miss=error;}assert(miss instanceof Z.NotFoundException,'A real blank bitmap must generate the actual SDK NotFoundException');}
    else if(scenario==='checksum-miss')miss=new Z.ChecksumException('Synthetic invalid checksum');
    else if(scenario==='format-miss')miss=new Z.FormatException('Synthetic invalid format');
    else throw Error('Unknown scenario '+scenario);
    proof.actual_sdk_error={name:miss.name,kind:miss.getKind(),message:miss.message};
    h.callbacks[0](null,miss);
    assert.equal(h.context.barcodeScanner.hidden,false,'Expected decode miss must leave scanner open for the next frame');
    assert.equal(h.lookups,0);assert(!h.messages.some(m=>m.startsWith('扫码失败')),'An expected decode miss must not become a fatal camera error');
    const result=decode(Z,'WMS-SYN-QR-20261116');assert.equal(result.getText(),'WMS-SYN-QR-20261116');
    h.callbacks[0](result);h.callbacks[0](result);
    assert.equal(h.lookups,1,'The actual decoded QR result must be delivered exactly once');assert.equal(h.context.scanCode.value,'WMS-SYN-QR-20261116');assert.equal(h.context.barcodeScanner.hidden,true);
  }
  proof.checks.push(scenario);proof.real_sdk_pixels=scenario!=='fatal-callback';proof.real_browser=false;proof.passed=true;
}

function fixture(){
  const htmlStart=source.indexOf('<div class="mobile-barcode-scanner"'),htmlEnd=source.indexOf('<!-- 拍照识物预览区 -->',htmlStart);
  assert(htmlStart>=0&&htmlEnd>htmlStart,'Use actual scanner DOM');
  const styles=[...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');assert(styles.includes('.mobile-barcode-scanner'));
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/icons.css"><style>html,body{margin:0}*{box-sizing:border-box}button{font:inherit} ${styles}</style></head><body><button id="barcodeBtn">开始条码扫描</button><input id="scanCode"><div id="scanStatus"></div><div id="syntheticContainingCard" style="position:relative;transform:translateZ(0);max-width:280px;height:220px;margin:24px auto">${source.slice(htmlStart,htmlEnd)}</div><script src="/sdk.js"></script><script src="/fixture.js"></script></body></html>`;
}
function browserScript(){return `
var barcodeScanner=document.getElementById('barcodeScanner'),barcodeVideo=document.getElementById('barcodeVideo'),barcodeBtn=document.getElementById('barcodeBtn'),closeBarcodeBtn=document.getElementById('closeBarcodeBtn'),scanCode=document.getElementById('scanCode'),zxingCodeReader=null;
window.__lookups=[];window.__statuses=[];window.__misses=[];window.__streams=[];window.__pending=[];window.__mediaMode='live';
function setStatus(message,type){__statuses.push({message,type});document.getElementById('scanStatus').textContent=message;}
function lookupMaterial(){__lookups.push(scanCode.value);}
var cameraCanvas=document.createElement('canvas');cameraCanvas.width=640;cameraCanvas.height=640;var cameraContext=cameraCanvas.getContext('2d'),cameraPayload=null;
function drawBlank(){cameraContext.fillStyle='white';cameraContext.fillRect(0,0,640,640);}
function drawQR(text){cameraPayload=text;drawBlank();var matrix=new ZXing.QRCodeWriter().encode(text,ZXing.BarcodeFormat.QR_CODE,220,220,new Map());cameraContext.fillStyle='black';for(var y=0;y<220;y++)for(var x=0;x<220;x++)if(matrix.get(x,y))cameraContext.fillRect(210+x,210+y,1,1);}
function freshStream(){var stream=cameraCanvas.captureStream(12);__streams.push(stream);return stream;}
drawBlank();
// captureStream produces frames when the real canvas changes; paint blank
// frames continuously too, instead of relying on a pre-capture static paint.
setInterval(function(){if(cameraPayload)drawQR(cameraPayload);else drawBlank();},80);
navigator.mediaDevices.getUserMedia=function(){if(__mediaMode==='permission')return Promise.reject(new DOMException('Synthetic permission denied','NotAllowedError'));if(__mediaMode==='missing')return Promise.reject(new DOMException('Synthetic device absent','NotFoundError'));if(__mediaMode==='deferred')return new Promise(resolve=>__pending.push(resolve));return Promise.resolve(freshStream());};
var originalDecode=ZXing.BrowserMultiFormatReader.prototype.decodeFromVideoDevice;
ZXing.BrowserMultiFormatReader.prototype.decodeFromVideoDevice=function(device,video,callback){return originalDecode.call(this,device,video,function(result,error){if(error)__misses.push({name:error.name,kind:typeof error.getKind==='function'?error.getKind():null,message:error.message});return callback(result,error);});};
${handlers}
window.__fixtureReady=true;`;
}
async function browserCheck(){
  const http=require('node:http'),{chromium}=require(path.resolve(opts['playwright-module']));
  const output=path.resolve(opts.output);fs.mkdirSync(output,{recursive:true});
  const content=new Map([['/',[fixture(),'text/html; charset=utf-8']],['/sdk.js',[fs.readFileSync(libraryPath),'text/javascript']],['/fixture.js',[browserScript(),'text/javascript']],['/icons.css',[fs.readFileSync(path.join(root,'app/static/cdn/bootstrap-icons-1.10.0.css')),'text/css']],['/fonts/bootstrap-icons.woff2',[fs.readFileSync(path.join(root,'app/static/cdn/fonts/bootstrap-icons.woff2')),'font/woff2']],['/fonts/bootstrap-icons.woff',[fs.readFileSync(path.join(root,'app/static/cdn/fonts/bootstrap-icons.woff')),'font/woff']]]);
  const server=http.createServer((req,res)=>{if(req.method!=='GET'){res.writeHead(405);res.end();return;}const value=content.get(new URL(req.url,'http://127.0.0.1').pathname);if(!value){res.writeHead(404);res.end();return;}res.writeHead(200,{'Content-Type':value[1],'Cache-Control':'no-store'});res.end(value[0]);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const address=server.address();assert(address.port>=10240&&address.address==='127.0.0.1');
  const origin='http://127.0.0.1:'+address.port;let browser,activePage;proof.real_browser=true;proof.captureStream_not_hardware=true;proof.external=[];proof.pageErrors=[];proof.scenarios=[];
  try{
    browser=await chromium.launch({executablePath:path.resolve(opts['chromium-executable']),headless:true});
    async function pageFor(label,viewport={width:375,height:812},large=false){const context=await browser.newContext({viewport,isMobile:true,deviceScaleFactor:1});await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){proof.external.push(route.request().url());return route.abort();}return route.continue();});const page=await context.newPage();activePage=page;page.on('pageerror',error=>proof.pageErrors.push(error.message));await page.goto(origin+'/');await page.waitForFunction(()=>window.__fixtureReady===true);if(large)await page.addStyleTag({content:'.mobile-barcode-header,.mobile-barcode-hint,#closeBarcodeBtn{font-size:24px!important;line-height:1.5!important}'});proof.scenarios.push({label,viewport,large,fontStress:large?'Test fixture minimum 24px text, not a real OS/browser setting':null});return {page,context};}
    async function begin(page){await page.locator('#barcodeBtn').click();await page.waitForFunction(()=>__misses.length>=1);}
    if(opts['browser-case']!=='layout'){
    const {page,context}=await pageFor('blank-then-real-qr');await begin(page);
    const blank=await page.evaluate(()=>({visible:!barcodeScanner.hidden,miss:__misses[0],live:__streams.some(s=>s.getTracks().some(t=>t.readyState==='live')),lookups:__lookups.length,status:__statuses.at(-1)}));proof.blank=blank;
    assert(blank.visible&&blank.live&&blank.lookups===0,'First actual blank video frame must not close scanner or report fatal failure');assert.equal(blank.miss.kind,'NotFoundException');
    await page.evaluate(()=>drawQR('WMS-CANVAS-QR-20261116'));await page.waitForFunction(()=>__lookups.length===1);
    await page.waitForFunction(()=>barcodeScanner.hidden&&barcodeVideo.srcObject===null&&__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));
    assert.deepEqual(await page.evaluate(()=>__lookups),['WMS-CANVAS-QR-20261116']);await page.waitForTimeout(350);assert.equal(await page.evaluate(()=>__lookups.length),1);proof.checks.push('real-blank-frame-keeps-scanning-then-actual-qr-delivered-once');await context.close();
    }
    for(const [label,viewport,large] of [['375',{width:375,height:812},false],['414',{width:414,height:896},false],['landscape',{width:812,height:375},false],['large-font',{width:375,height:812},true]]){
      const {page,context}=await pageFor('geometry-'+label,viewport,large);if(opts['browser-case']==='layout'){await page.evaluate(()=>__mediaMode='deferred');await page.locator('#barcodeBtn').click();await page.waitForFunction(()=>__pending.length===1);}else await begin(page);
      const geometry=await page.evaluate(()=>{const box=s=>{const b=document.querySelector(s).getBoundingClientRect();return {x:b.x,y:b.y,width:b.width,height:b.height,right:b.right,bottom:b.bottom};};return {viewport:{width:innerWidth,height:innerHeight},scanner:box('#barcodeScanner'),video:box('#barcodeVideo'),frame:box('.mobile-barcode-frame'),header:box('.mobile-barcode-header'),hint:box('.mobile-barcode-hint'),movedToBody:barcodeScanner.parentElement===document.body,scrollLocked:document.body.classList.contains('mobile-barcode-open'),bodyOverflow:getComputedStyle(document.body).overflow};});
      proof.scenarios.at(-1).geometry=geometry;
      const w=geometry.viewport.width,h=geometry.viewport.height;for(const name of ['scanner','video']){assert(Math.abs(geometry[name].x)<=1&&Math.abs(geometry[name].y)<=1&&Math.abs(geometry[name].width-w)<=1&&Math.abs(geometry[name].height-h)<=1,label+' '+name+' must cover the full web viewport');}
      assert(geometry.movedToBody,'The actual handler must move the same scanner node out of a transformed containing card');
      assert(geometry.frame.x<=16&&geometry.frame.y<=16&&geometry.frame.right>=w-16&&geometry.frame.bottom>=h-16,label+' guide corners must follow viewport edges, not a central small box');assert(geometry.header.bottom<=h&&geometry.hint.y>=0&&geometry.hint.bottom<=h,'Controls/hint must stay within viewport');assert(geometry.scrollLocked&&['hidden','clip'].includes(geometry.bodyOverflow),'Opening the scanner must lock background scrolling');
      await page.screenshot({path:path.join(output,'scanner-'+label+'.png'),fullPage:true});await page.locator('#closeBarcodeBtn').click();if(opts['browser-case']==='layout')await page.evaluate(()=>__pending[0](freshStream()));await page.waitForFunction(()=>barcodeScanner.hidden&&barcodeVideo.srcObject===null&&__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));assert.equal(await page.evaluate(()=>document.body.classList.contains('mobile-barcode-open')),false);await context.close();proof.checks.push('fullscreen-'+label);
    }
    for(const [mode,text] of [['permission','权限被拒绝'],['missing','未找到摄像头']]){const {page,context}=await pageFor('fatal-'+mode);await page.evaluate(mode=>__mediaMode=mode,mode);await page.locator('#barcodeBtn').click();await page.waitForFunction(()=>__statuses.some(s=>s.type==='error'));assert(await page.evaluate(text=>barcodeScanner.hidden&&__lookups.length===0&&__statuses.some(s=>s.message.includes(text)),text),'Genuine camera acquisition errors must remain fatal and actionable');await context.close();proof.checks.push('fatal-'+mode);}
    const late=await pageFor('late-acquisition-after-close');await late.page.evaluate(()=>__mediaMode='deferred');await late.page.locator('#barcodeBtn').click();await late.page.waitForFunction(()=>__pending.length===1);await late.page.locator('#closeBarcodeBtn').click();await late.page.evaluate(()=>__pending[0](freshStream()));await late.page.waitForFunction(()=>__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')));assert(await late.page.evaluate(()=>barcodeScanner.hidden&&barcodeVideo.srcObject===null&&__lookups.length===0));await late.context.close();proof.checks.push('real-sdk-late-stream-stopped-after-close');
    assert.equal(proof.pageErrors.length,0);assert.equal(proof.external.length,0);proof.passed=true;
  }catch(error){proof.passed=false;proof.error=error.stack;if(activePage&&!activePage.isClosed())try{proof.finalBrowserState=await activePage.evaluate(()=>({ready:window.__fixtureReady,hidden:barcodeScanner.hidden,statuses:__statuses,misses:__misses.length,streams:__streams.map(s=>s.getTracks().map(t=>t.readyState)),video:{readyState:barcodeVideo.readyState,currentTime:barcodeVideo.currentTime,paused:barcodeVideo.paused,width:barcodeVideo.videoWidth,height:barcodeVideo.videoHeight}}));await activePage.screenshot({path:path.join(output,'failure.png'),fullPage:true});}catch{}throw error;}
  finally{try{if(browser)await browser.close();}finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}}
}
async function main(){try{if(opts.browser==='true')await browserCheck();else await nodeCheck(opts.scenario||'decode-miss');console.log(JSON.stringify(proof));}catch(error){proof.passed=false;proof.error=error.message;console.error(error.message);process.exitCode=1;}finally{if(opts.evidence)fs.writeFileSync(path.resolve(opts.evidence),JSON.stringify(proof,null,2));}}
main();
