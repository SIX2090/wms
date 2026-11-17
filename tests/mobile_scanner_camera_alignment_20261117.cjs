'use strict';
// Actual Chrome compositor + captureStream + vendored ZXing. No WMS import,
// production endpoint, physical camera, dependency installation or optical-focus claim.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const crypto=require('node:crypto'),zlib=require('node:zlib'),assert=require('node:assert/strict');
const opts={};for(let i=2;i<process.argv.length;i+=2){assert(process.argv[i].startsWith('--')&&process.argv[i+1]);opts[process.argv[i].slice(2)]=process.argv[i+1];}
for(const key of ['playwright-module','chromium-executable','output'])assert(opts[key],`Missing --${key}`);
const root=path.resolve(opts.root||path.join(__dirname,'..'));
const sourceFile=path.resolve(opts.source||path.join(root,'app/templates/mobile_scan.html'));
const source=fs.readFileSync(sourceFile,'utf8'),sdk=fs.readFileSync(path.join(root,'app/static/cdn/zxing-library-0.23.0.min.js'));
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const begin=source.indexOf('    function stopBarcodeScanner()'),end=source.indexOf('    function addHistory(',begin);
assert(begin>=0&&end>begin,'Actual scanner handler block is required');
const domStart=source.indexOf('<div class="mobile-barcode-scanner"'),domEnd=source.indexOf('<!-- 拍照识物预览区 -->',domStart);
assert(domStart>=0&&domEnd>domStart,'Actual scanner DOM is required');
const styles=[...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(m=>m[1]).join('\n');
const output=path.resolve(opts.output);fs.mkdirSync(output,{recursive:true});
const proof={sourceFile,source_sha256:hash(source),sdk_sha256:hash(sdk),realChrome:true,
  syntheticMedia:true,opticalFocusVerified:false,sourceFrame:{width:640,height:480},cases:[],external:[],pageErrors:[]};

// Chrome screenshots are non-interlaced 8-bit RGB/RGBA PNGs. Decode with Node's
// built-in zlib so the regression does not introduce a PNG/tooling dependency.
function pngPixels(buffer){
  assert.equal(buffer.subarray(1,4).toString(),'PNG');
  let width,height,channels;const compressed=[];
  for(let offset=8;offset<buffer.length;){const length=buffer.readUInt32BE(offset),kind=buffer.toString('ascii',offset+4,offset+8),data=buffer.subarray(offset+8,offset+8+length);
    if(kind==='IHDR'){width=data.readUInt32BE(0);height=data.readUInt32BE(4);assert.equal(data[8],8);assert.equal(data[12],0);assert([2,6].includes(data[9]));channels=data[9]===6?4:3;}
    if(kind==='IDAT')compressed.push(data);offset+=length+12;
  }
  const raw=zlib.inflateSync(Buffer.concat(compressed)),stride=width*channels,pixels=Buffer.alloc(stride*height);
  assert.equal(raw.length,(stride+1)*height);
  const paeth=(a,b,c)=>{const p=a+b-c,pa=Math.abs(p-a),pb=Math.abs(p-b),pc=Math.abs(p-c);return pa<=pb&&pa<=pc?a:pb<=pc?b:c;};
  for(let y=0,input=0;y<height;y++){const filter=raw[input++];assert(filter<=4);for(let x=0;x<stride;x++){
    const p=y*stride+x,left=x>=channels?pixels[p-channels]:0,up=y?pixels[p-stride]:0,corner=y&&x>=channels?pixels[p-stride-channels]:0;
    const predictor=[0,left,up,Math.floor((left+up)/2),paeth(left,up,corner)][filter];pixels[p]=(raw[input++]+predictor)&255;
  }}return {width,height,channels,pixels};
}
function markerBounds(image){
  const bounds={};for(const key of ['left','right','top','bottom'])bounds[key]={count:0,minX:Infinity,minY:Infinity,maxX:-1,maxY:-1};
  for(let y=0;y<image.height;y++)for(let x=0;x<image.width;x++){
    const p=(y*image.width+x)*image.channels,r=image.pixels[p],g=image.pixels[p+1],b=image.pixels[p+2];let key;
    // Channel ratios also recognize the real header/hint's dark gradients over
    // the markers; white text and the blue guide are excluded.
    if(r>45&&b>45&&g<Math.min(r,b)*.35&&Math.min(r,b)>Math.max(r,b)*.7)key='left';
    else if(g>45&&r<g*.35&&b<g*.35)key='right';
    else if(g>45&&b>45&&r<Math.min(g,b)*.35&&Math.min(g,b)>Math.max(g,b)*.7)key='top';
    else if(r>45&&g>r*.3&&g<r*.72&&b<g*.35)key='bottom';
    if(key){const v=bounds[key];v.count++;v.minX=Math.min(v.minX,x);v.maxX=Math.max(v.maxX,x);v.minY=Math.min(v.minY,y);v.maxY=Math.max(v.maxY,y);}
  }return bounds;
}
function html(){return `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/icons.css"><style>html,body{margin:0}*{box-sizing:border-box}button{font:inherit}${styles}</style><button id="barcodeBtn">扫码</button><input id="scanCode"><div id="scanStatus"></div><div style="transform:translateZ(0);max-width:280px;height:220px;margin:24px auto">${source.slice(domStart,domEnd)}</div><script src="/sdk.js"></script><script src="/fixture.js"></script>`;}
function script(){return `
var barcodeScanner=document.getElementById('barcodeScanner'),barcodeVideo=document.getElementById('barcodeVideo'),barcodeBtn=document.getElementById('barcodeBtn'),closeBarcodeBtn=document.getElementById('closeBarcodeBtn'),scanCode=document.getElementById('scanCode'),zxingCodeReader=null;
window.__streams=[];window.__lookups=[];window.__statuses=[];
function setStatus(message,type){__statuses.push({message,type});document.getElementById('scanStatus').textContent=message;}
function lookupMaterial(){__lookups.push(scanCode.value);}
var cameraCanvas=document.createElement('canvas');cameraCanvas.width=640;cameraCanvas.height=480;
var cameraContext=cameraCanvas.getContext('2d'),tick=0;
function paintEdges(){cameraContext.fillStyle='#eeeeee';cameraContext.fillRect(0,0,640,480);
cameraContext.fillStyle='#ff00ff';cameraContext.fillRect(0,0,20,480);
cameraContext.fillStyle='#00ff00';cameraContext.fillRect(620,0,20,480);
cameraContext.fillStyle='#00ffff';cameraContext.fillRect(0,0,640,20);
cameraContext.fillStyle='#ff8000';cameraContext.fillRect(0,460,640,20);
cameraContext.fillStyle=(++tick%2)?'#dddddd':'#cccccc';cameraContext.fillRect(319,239,2,2);}
paintEdges();setInterval(paintEdges,80);
navigator.mediaDevices.getUserMedia=function(){var stream=cameraCanvas.captureStream(12);__streams.push(stream);return Promise.resolve(stream);};
${source.slice(begin,end)}
window.__fixtureReady=true;`;}
async function main(){
  const {chromium}=require(path.resolve(opts['playwright-module']));
  const content=new Map([['/',[html(),'text/html; charset=utf-8']],['/sdk.js',[sdk,'text/javascript']],['/fixture.js',[script(),'text/javascript']],
    ['/icons.css',[fs.readFileSync(path.join(root,'app/static/cdn/bootstrap-icons-1.10.0.css')),'text/css']],
    ['/fonts/bootstrap-icons.woff2',[fs.readFileSync(path.join(root,'app/static/cdn/fonts/bootstrap-icons.woff2')),'font/woff2']],
    ['/fonts/bootstrap-icons.woff',[fs.readFileSync(path.join(root,'app/static/cdn/fonts/bootstrap-icons.woff')),'font/woff']]]);
  const server=http.createServer((request,response)=>{const value=content.get(new URL(request.url,'http://127.0.0.1').pathname);if(request.method!=='GET'||!value){response.writeHead(404);response.end();return;}response.writeHead(200,{'Content-Type':value[1],'Cache-Control':'no-store'});response.end(value[0]);});
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));const address=server.address();assert(address.port>=10240);
  const origin='http://127.0.0.1:'+address.port;let browser;
  try{
    browser=await chromium.launch({executablePath:path.resolve(opts['chromium-executable']),headless:true});proof.chromeVersion=browser.version();
    for(const [label,viewport] of [['375',{width:375,height:812}],['414',{width:414,height:896}],['landscape',{width:812,height:375}]]){
      const record={label,viewport,phase:'fixture'};proof.cases.push(record);
      const context=await browser.newContext({viewport,isMobile:true,deviceScaleFactor:1});
      await context.route('**/*',route=>{if(new URL(route.request().url()).origin!==origin){proof.external.push(route.request().url());return route.abort();}return route.continue();});
      const page=await context.newPage();page.on('pageerror',error=>proof.pageErrors.push(error.message));
      try{
        await page.goto(origin+'/');await page.waitForFunction(()=>window.__fixtureReady===true);await page.locator('#barcodeBtn').click();
        await page.waitForFunction(()=>!barcodeScanner.hidden&&barcodeVideo.readyState>=2&&barcodeVideo.currentTime>0&&barcodeVideo.videoWidth===640&&barcodeVideo.videoHeight===480);
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        record.geometry=await page.evaluate(()=>{const box=node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};const track=__streams[0].getVideoTracks()[0];return {video:box(barcodeVideo),guide:box(document.querySelector('.mobile-barcode-frame')),intrinsic:{width:barcodeVideo.videoWidth,height:barcodeVideo.videoHeight},objectFit:getComputedStyle(barcodeVideo).objectFit,focusCapability:track.getCapabilities?.().focusMode||null};});
        const screenshot=await page.screenshot({path:path.join(output,label+'.png'),animations:'disabled'}),image=pngPixels(screenshot);
        assert.equal(image.width,viewport.width);assert.equal(image.height,viewport.height);record.image_sha256=hash(screenshot);record.markers=markerBounds(image);
        record.phase='visual';const scale=Math.min(viewport.width/640,viewport.height/480),expected={x:(viewport.width-640*scale)/2,y:(viewport.height-480*scale)/2,width:640*scale,height:480*scale};record.expected=expected;
        for(const name of ['left','right','top','bottom'])assert(record.markers[name].count>30,`${label}: ${name} source-frame edge is cropped from the actual video screenshot`);
        const actual={x:record.markers.left.minX,y:record.markers.top.minY,right:record.markers.right.maxX+1,bottom:record.markers.bottom.maxY+1};actual.width=actual.right-actual.x;actual.height=actual.bottom-actual.y;record.actual=actual;
        for(const [value,wanted] of [[actual.x,expected.x],[actual.y,expected.y],[actual.width,expected.width],[actual.height,expected.height]])assert(Math.abs(value-wanted)<=3,`${label}: rendered source edges must match a complete centred frame: ${value} vs ${wanted}`);
        assert(Math.abs(actual.width/actual.height-640/480)<.025,`${label}: real rendered frame must retain its aspect ratio`);
        const guide=record.geometry.guide;assert(Math.abs(guide.x-8)<=1&&Math.abs(guide.y-8)<=1&&Math.abs(guide.right-(viewport.width-8))<=1&&Math.abs(guide.bottom-(viewport.height-8))<=1,'Viewport guide must remain inset8 independently of the letterboxed image');
        assert.equal(await page.evaluate(()=>__lookups.length),0);record.passed=true;
      }catch(error){record.passed=false;record.failure={phase:record.phase,message:error.message};}
      finally{try{await page.locator('#closeBarcodeBtn').click({timeout:1500});await page.waitForFunction(()=>barcodeScanner.hidden&&barcodeVideo.srcObject===null&&__streams.every(s=>s.getTracks().every(t=>t.readyState==='ended')),{},{timeout:3000});record.mediaReleased=true;}catch(error){record.cleanupFailure=error.message;record.passed=false;}await context.close();}
    }
    proof.passed=proof.cases.every(record=>record.passed)&&proof.external.length===0&&proof.pageErrors.length===0;
  }finally{if(browser)await browser.close();server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{proof.passed=false;proof.fixtureFailure=error.stack;}).finally(()=>{fs.writeFileSync(path.join(output,'proof.json'),JSON.stringify(proof,null,2));console.log(JSON.stringify(proof));if(!proof.passed)process.exitCode=1;});
