'use strict';
// Real Chrome CSS animation geometry only. No production endpoint, camera,
// ZXing mock, device installation, dependency installation or hardware claim.
// Example:
// node tests/mobile_scanner_scanline_rhythm_20261117.cjs --root C:/wms \
//   --source C:/isolated/mobile_scan.html --playwright-module C:/tools/playwright-core \
//   --chromium-executable "C:/Program Files/Google/Chrome/Application/chrome.exe" \
//   --output C:/isolated/rhythm-evidence
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const crypto=require('node:crypto'),assert=require('node:assert/strict');
const opts={};
for(let i=2;i<process.argv.length;i+=2){
  assert(process.argv[i].startsWith('--')&&process.argv[i+1], 'Expected --option value');
  opts[process.argv[i].slice(2)]=process.argv[i+1];
}
for(const key of ['playwright-module','chromium-executable','output'])assert(opts[key], 'Missing --'+key);
const root=path.resolve(opts.root||path.join(__dirname,'..'));
const sourceFile=path.resolve(opts.source||path.join(root,'app/templates/mobile_scan.html'));
const source=fs.readFileSync(sourceFile,'utf8');
const hash=data=>crypto.createHash('sha256').update(data).digest('hex');
const start=source.indexOf('<div class="mobile-barcode-scanner"');
const end=source.indexOf('<!-- 拍照识物预览区 -->',start);
assert(start>=0&&end>start,'Actual scanner DOM is required');
const styles=[...source.matchAll(/<style[^>]*>([\s\S]*?)<\/style>/g)].map(x=>x[1]).join('\n');
assert(styles.length>0,'Actual template stylesheet is required');
const html='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0}*{box-sizing:border-box}'+styles+'</style>'+source.slice(start,end);
const output=path.resolve(opts.output);fs.mkdirSync(output,{recursive:true});
const times=[0,500,1000,1500,1999,2000,2250,2500,3000,3500,3999,4000];
const proof={sourceFile,source_sha256:hash(source),test_sha256:hash(fs.readFileSync(__filename)),
  realChrome:true,animationClock:'Web Animations pause/currentTime; real getBoundingClientRect',
  expected:{durationMs:2000,direction:'top-to-bottom',easing:'linear',repeat:'restart'},
  samplesMs:times,cameraAccess:false,productionAccess:false,external:[],pageErrors:[],cases:[]};
async function main(){
  const {chromium}=require(path.resolve(opts['playwright-module']));
  const server=http.createServer((request,response)=>{
    if(request.method!=='GET'||new URL(request.url,'http://127.0.0.1').pathname!=='/'){response.writeHead(404);response.end();return;}
    response.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'});response.end(html);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin='http://127.0.0.1:'+server.address().port;let browser;
  try{
    browser=await chromium.launch({executablePath:path.resolve(opts['chromium-executable']),headless:true});
    proof.chromeVersion=browser.version();
    proof.playwrightVersion=require(path.join(path.resolve(opts['playwright-module']),'package.json')).version;
    for(const [label,viewport] of [['375',{width:375,height:812}],['414',{width:414,height:896}],['landscape',{width:812,height:375}]]){
      const record={label,viewport,phase:'fixture',checks:[],samples:[],screenshots:[]};proof.cases.push(record);
      const context=await browser.newContext({viewport,isMobile:true,deviceScaleFactor:1});
      await context.route('**/*',route=>{
        if(new URL(route.request().url()).origin!==origin){proof.external.push(route.request().url());return route.abort();}
        return route.continue();
      });
      const page=await context.newPage();page.on('pageerror',error=>proof.pageErrors.push(error.message));
      const check=(name,condition,actual)=>record.checks.push({name,passed:Boolean(condition),actual});
      const close=(a,b)=>Math.abs(a-b)<=.8;
      try{
        await page.goto(origin+'/');
        await page.locator('#barcodeScanner').evaluate(node=>{node.hidden=false;});
        await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
        record.initialization=await page.evaluate(()=>{
          const frame=document.querySelector('.mobile-barcode-frame'),line=document.querySelector('.mobile-barcode-scan-line');
          if(!frame||!line)throw Error('Actual frame and line must exist in both baseline and candidate');
          const animations=frame.getAnimations({subtree:true}).filter(a=>a.animationName==='scanLineMove');
          if(animations.length!==1)throw Error('Expected one real scanLineMove animation, got '+animations.length);
          window.__rhythmAnimation=animations[0];__rhythmAnimation.pause();__rhythmAnimation.currentTime=0;
          const animation=__rhythmAnimation,timing=animation.effect.getTiming(),box=frame.getBoundingClientRect();
          return {animationName:animation.animationName,targetClass:animation.effect.target.className,
            duration:timing.duration,delay:timing.delay,iterations:timing.iterations===Infinity?'Infinity':timing.iterations,
            direction:timing.direction,cssTiming:getComputedStyle(animation.effect.target).animationTimingFunction,
            frame:{x:box.x,y:box.y,width:box.width,height:box.height}};
        });
        for(const time of times){
          const sample=await page.evaluate(time=>{
            __rhythmAnimation.currentTime=time;
            const frame=document.querySelector('.mobile-barcode-frame').getBoundingClientRect();
            const line=document.querySelector('.mobile-barcode-scan-line').getBoundingClientRect();
            return {time,currentTime:__rhythmAnimation.currentTime,playState:__rhythmAnimation.playState,
              x:line.x,y:line.y,width:line.width,height:line.height,bottom:line.bottom,
              frame:{x:frame.x,y:frame.y,width:frame.width,height:frame.height,bottom:frame.bottom}};
          },time);
          record.samples.push(sample);
          if([0,1000,1999,2000].includes(time)){
            const name=label+'-'+time+'ms.png';
            const image=await page.screenshot({path:path.join(output,name),animations:'allow'});
            record.screenshots.push({time,file:name,sha256:hash(image)});
          }
        }
        record.phase='behavior';
        const init=record.initialization,frame=init.frame,travel=frame.height-3;
        check('viewport guide remains inset8',close(frame.x,8)&&close(frame.y,8)&&close(frame.width,viewport.width-16)&&close(frame.height,viewport.height-16),frame);
        check('actual animation lasts exactly 2000ms',init.duration===2000,init.duration);
        check('actual animation repeats infinitely without delay or reverse',init.iterations==='Infinity'&&init.delay===0&&init.direction==='normal',init);
        for(const sample of record.samples){
          const expectedY=sample.frame.y+travel*((sample.time%2000)/2000);
          check('real position follows uniform downward 2s restart at '+sample.time+'ms',close(sample.y,expectedY),{actualY:sample.y,expectedY});
          check('line stays 3px high and inside guide at '+sample.time+'ms',close(sample.height,3)&&sample.y>=sample.frame.y-.8&&sample.bottom<=sample.frame.bottom+.8,{lineY:sample.y,height:sample.height,bottom:sample.bottom,frame:sample.frame});
          check('real animation is paused at the requested sample '+sample.time+'ms',sample.playState==='paused'&&sample.currentTime===sample.time,{playState:sample.playState,currentTime:sample.currentTime});
        }
        for(const cycle of [[0,500,1000,1500,1999],[2000,2250,2500,3000,3500,3999]]){
          for(let i=1;i<cycle.length;i++){
            const before=record.samples.find(x=>x.time===cycle[i-1]),after=record.samples.find(x=>x.time===cycle[i]);
            const expectedDelta=travel*(after.time-before.time)/2000;
            check('constant positive velocity '+before.time+'→'+after.time+'ms',after.y>before.y&&close(after.y-before.y,expectedDelta),{delta:after.y-before.y,expectedDelta});
          }
        }
        for(const time of [2000,4000]){
          const previous=record.samples.find(x=>x.time===time-1),current=record.samples.find(x=>x.time===time);
          check('cycle '+time+'ms restarts at top rather than reversing',previous.y>frame.y+travel*.99&&close(current.y,frame.y),{previousY:previous.y,currentY:current.y,top:frame.y});
        }
        record.passed=record.checks.every(x=>x.passed);
      }catch(error){record.passed=false;record.failure={phase:record.phase,message:error.stack};}
      finally{await context.close();}
    }
    proof.passed=proof.cases.every(x=>x.passed)&&proof.external.length===0&&proof.pageErrors.length===0;
  }finally{
    try{if(browser)await browser.close();}
    finally{server.closeAllConnections?.();await new Promise(resolve=>server.close(resolve));}
  }
}
main().catch(error=>{proof.passed=false;proof.fixtureFailure=error.stack;}).finally(()=>{
  fs.writeFileSync(path.join(output,'proof.json'),JSON.stringify(proof,null,2)+'\n');
  console.log(JSON.stringify({passed:proof.passed,chromeVersion:proof.chromeVersion,cases:proof.cases.map(x=>({label:x.label,phase:x.phase,passed:x.passed,failedChecks:x.checks.filter(c=>!c.passed),failure:x.failure})),fixtureFailure:proof.fixtureFailure}));
  if(!proof.passed)process.exitCode=1;
});
