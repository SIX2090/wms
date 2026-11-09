'use strict';
// 禁止在隔离能力验证完成前加载驱动或启动浏览器。
throw new Error('浏览器验证已阻止：隔离能力尚未证明');
// CI-only real Chrome; every server and database is owned by an OS temp folder.
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net');
const {spawn,spawnSync}=require('node:child_process');
const {randomUUID}=require('node:crypto');
const {chromium}=require('../tools/browser_checks/node_modules/playwright-core');
const repo=path.resolve(__dirname,'..'), output=path.join(repo,'output/browser-material');
fs.mkdirSync(output,{recursive:true});
const scratch=fs.mkdtempSync(path.join(os.tmpdir(),'wms-browser-'));
const proof={scope:'Real Chrome,synthetic temporary databases only;no production/hardware/external requests',phases:[]};
const password='AuditOnly2026!';
let activePage;
function check(value,message){if(!value)throw new Error(message);}
function benchmarkName(index){return '同场景合成录入-'+index;}
async function submitAndObserve(page, pathname, trigger) {
 const origin = new URL(page.url()).origin;
 const matches = url => url.origin === origin && url.pathname === pathname;
 let resolveSnapshot,rejectSnapshot,forwarded=0;
 const snapshot = new Promise((resolve,reject)=>{resolveSnapshot=resolve;rejectSnapshot=reject;});
 const relay = async route => {
  if(route.request().method()!=='POST')return route.fallback();
  let upstream;
  try{
   forwarded++;
   upstream=await route.fetch({maxRedirects:0,maxRetries:0});
   const captured={status:upstream.status(),text:await upstream.text()};
   resolveSnapshot(captured);
   await route.fulfill({response:upstream});
  }catch(error){rejectSnapshot(error);await route.abort().catch(()=>{});}
  finally{if(upstream)await upstream.dispose();}
 };
 await page.route(matches,relay);
 try{
  const [captured,response]=await Promise.all([
   snapshot,page.waitForResponse(r=>matches(new URL(r.url()))&&r.request().method()==='POST'),
   Promise.resolve().then(trigger)
  ]);
  check(forwarded===1,'Expected one upstream write without retries');
  check(response.status()===captured.status,'Delivered status differs from upstream response');
  return captured;
 }finally{
  if(!page.isClosed())await page.unroute(matches,relay).catch(error=>{if(!page.isClosed())throw error;});
 }
}
async function ordinarySaveControl(page) {
 const control = page.getByRole('button', {name: /保存$/});
 check(await control.count() === 1, 'Expected exactly one visible ordinary save control');
 check(await control.getAttribute('data-wms-save-complete') === null &&
       await control.getAttribute('data-wms-save-complete-proxy') === null,
       'Refusing a save-and-complete action');
 return control;
}
function git(args){const r=spawnSync('git',args,{cwd:repo,encoding:'utf8'});check(r.status===0,'Git verification failed: '+args[0]);return r.stdout.trim();}
async function freePort(){const server=net.createServer();await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});const port=server.address().port;await new Promise(resolve=>server.close(resolve));return port;}
async function server(source,label){
 const root=path.join(scratch,label);fs.mkdirSync(root);const port=await freePort(),instance=randomUUID();
 const log=fs.createWriteStream(path.join(output,'server-'+label+'.log'));
 const child=spawn(process.env.PYTHON||'python',[path.join(repo,'tests/material_browser_server.py'),'--root',root,'--source-root',source,'--port',String(port),'--instance',instance],{cwd:repo,stdio:['ignore','pipe','pipe'],windowsHide:true});
 child.stderr.on('data',data=>log.write(data));let buffer='',ready=false;
 await new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('Isolated server startup timed out')),45000);
  child.once('error',reject);child.once('exit',code=>{if(!ready){clearTimeout(timer);reject(Error('Isolated server exited '+code));}});
  child.stdout.on('data',data=>{log.write(data);buffer+=data.toString();if(buffer.includes('"ready": true')&&buffer.includes(instance)){ready=true;clearTimeout(timer);resolve();}});
 }).catch(error=>{child.kill();throw error;});
 return {origin:'http://127.0.0.1:'+port,instance,root,async close(){if(child.exitCode===null){child.kill();await new Promise(resolve=>{child.once('exit',resolve);setTimeout(resolve,5000);});}log.end();}};
}
async function login(context,fixture,username){
 const page=await context.newPage();const response=await page.goto(fixture.origin+'/login');
 check(await response.headerValue('x-wms-isolated-test')===fixture.instance,'Wrong server;refusing credentials');
 await page.getByRole('tab',{name:'管理员',exact:true}).click();
 await page.getByRole('textbox',{name:'用户名',exact:true}).fill(username);
 await page.getByRole('textbox',{name:'密码',exact:true}).fill(password);
 await page.getByRole('button',{name:'登录',exact:true}).click();await page.waitForURL(url=>url.pathname!='/login');return page;
}
async function exercise(browser,fixture,migrated){
 const label=migrated?'current':'baseline',record={label,controls:[],posts:[],timings:[],pageErrors:[]};proof.phases.push(record);
 const context=await browser.newContext({viewport:{width:1180,height:900}});
 await context.route('**/*',route=>route.request().url().startsWith(fixture.origin+'/')?route.continue():route.abort());
 await context.addInitScript(()=>{window.__normalCspViolations=[];document.addEventListener('securitypolicyviolation',event=>window.__normalCspViolations.push(event.effectiveDirective));});
 const page=await login(context,fixture,'browser-a');activePage=page;
 page.on('pageerror',e=>record.pageErrors.push(e.message));page.on('dialog',d=>d.accept().catch(()=>{}));
 page.on('request',r=>{if(r.method()==='POST')record.posts.push(new URL(r.url()).pathname);});
 let response=await page.goto(fixture.origin+'/material/add?embedded=1');
 record.policyCount=(await response.headersArray()).filter(h=>h.name.toLowerCase()==='content-security-policy').length;
 check(record.policyCount===(migrated?2:1),'Unexpected page policy profile');
 for(let i=0;i<3;i++){
  record.stage='dialog-control-'+i;
  await page.getByTitle('新增单位',{exact:true}).click();await page.locator('#addUnitModal').waitFor({state:'visible'});
  await page.locator('#addUnitModal').getByRole('button',{name:'取消',exact:true}).click();
  check(await page.locator('#addUnitModal').count()===0,'Cancel did not close dialog');record.controls.push({url:page.url(),closed:true});
 }
 await page.getByTitle('新增单位',{exact:true}).click();await page.keyboard.press('Escape');
 record.escapeStillOpen=await page.locator('#addUnitModal').isVisible();check(record.escapeStillOpen===!migrated,'Escape behavior mismatch');
 if(record.escapeStillOpen)await page.locator('#addUnitModal').getByRole('button',{name:'取消',exact:true}).click();
 else check(await page.getByTitle('新增单位',{exact:true}).evaluate(el=>el===document.activeElement),'Escape did not restore focus');
 await page.getByTitle('新增单位',{exact:true}).click();
 await page.locator('#addUnitForm input[name=code]').fill('CI-UNIT');await page.locator('#addUnitForm input[name=name]').fill('合成浏览器单位');
 const unitsBefore=record.posts.filter(p=>p==='/unit/add').length;
 await page.locator('#addUnitForm button[type=submit]').dblclick();await page.waitForTimeout(900);
 record.unitDoublePosts=record.posts.filter(p=>p==='/unit/add').length-unitsBefore;
 check(record.unitDoublePosts===(migrated?1:2),'Repeated unit submit was not handled as expected');
 check(await page.locator('#unitSearch').inputValue()==='合成浏览器单位','New unit was not selected');
 if(migrated){
  await page.getByTitle('新增单位',{exact:true}).click();await page.locator('#addUnitForm input[name=code]').fill('PCS');
  await page.locator('#addUnitForm input[name=name]').fill('失败后保留单位输入');
  await page.locator('#addUnitForm button[type=submit]').click();await page.waitForTimeout(600);
  check(await page.locator('#addUnitForm input[name=name]').inputValue()==='失败后保留单位输入','Unit failure lost input');
  check(await page.locator('#addUnitForm button[type=submit]').isEnabled(),'Unit failure left save disabled');
  await page.keyboard.press('Escape');check(await page.locator('#addUnitModal').count()===0,'Unit retry dialog did not close');
 }
 await page.locator('#addMaterialForm input[name=code]').fill('CI-MATERIAL');await page.locator('#addMaterialForm input[name=name]').fill('合成物料重复点击');
 const materialBefore=record.posts.filter(p=>p==='/material/add').length;
 await page.locator('#addMaterialForm button[type=submit]').dblclick();await page.waitForTimeout(900);
 record.materialDoublePosts=record.posts.filter(p=>p==='/material/add').length-materialBefore;
 check(record.materialDoublePosts===(migrated?1:2),'Repeated material submit was not handled as expected');
 await page.goto(fixture.origin+'/material/add?embedded=1');
 await page.locator('#addMaterialForm input[name=code]').fill('SYN-M');await page.locator('#addMaterialForm input[name=name]').fill('保留物料输入');
 if(migrated){
  await page.locator('#addMaterialForm button[type=submit]').click();await page.waitForTimeout(650);
  check(await page.locator('#addMaterialForm input[name=name]').inputValue()==='保留物料输入','Material failure lost input');
  check(await page.locator('#addMaterialForm button[type=submit]').isEnabled(),'Material failure left save disabled');
 }
 await page.locator('#addMaterialForm input[name=code]').fill('CI-KEYBOARD');
 await page.locator('#unitSearch').fill('KG');await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
 check(await page.locator('#unitIdHidden').inputValue()==='2','Unit keyboard identity changed');
 const shortcutBefore=record.posts.filter(p=>p==='/material/add').length;
 await page.keyboard.press('Control+s');await page.waitForTimeout(750);
 record.shortcutPosts=record.posts.filter(p=>p==='/material/add').length-shortcutBefore;
 check(record.shortcutPosts===(migrated?1:0),'Ordinary save shortcut mismatch');
 if(migrated)await page.waitForURL(url=>url.pathname==='/material');
 for(let i=0;i<3;i++){
  record.stage='material-timing-'+i;
  await page.goto(fixture.origin+'/material/add?embedded=1');
  await page.locator('#addMaterialForm input[name=code]').fill('BENCH-'+label+'-'+i);
  await page.locator('#addMaterialForm input[name=name]').fill(benchmarkName(i));
  const begin=Date.now();
  const saved=await submitAndObserve(page,'/material/add',()=>page.locator('#addMaterialForm button[type=submit]').click());
  check(saved.status===200,'Benchmark material save failed: '+saved.status+' '+saved.text.slice(0,200));
  await page.waitForURL(url=>url.pathname==='/material');record.timings.push({flow:'material-create',milliseconds:Date.now()-begin});
 }
 for(const family of ['in_order','out_order'])for(let i=0;i<2;i++){
  record.stage=family+'-timing-'+i;
  await page.goto(fixture.origin+(family==='out_order'?'/other_out_order/add':'/in_order/add')+'?order_id=1&embedded=1');
  await page.locator('[name="remark"]').fill('同场景草稿-'+label+'-'+i);
  const control=await ordinarySaveControl(page),begin=Date.now();
  const saved=await submitAndObserve(page,'/'+family+'/add',()=>control.click());
  const body=JSON.parse(saved.text);
  check(saved.status===200&&body.status==='success','Core draft save failed');
  check(body.id===1,'Core draft save changed the document identity');
  await page.waitForURL(url=>url.pathname==='/'+family+'/1');
  record.timings.push({flow:family+'-draft-edit',milliseconds:Date.now()-begin});
 }
 if(migrated){
  record.stage='material-csp-and-second-account';
  await page.goto(fixture.origin+'/material/add?embedded=1');
  record.normalCspViolations=await page.evaluate(()=>window.__normalCspViolations);
  check(record.normalCspViolations.length===0,'CSP blocked a normal page operation');
  record.privateModule=await page.evaluate(()=>typeof window.showAddUnitModal==='undefined'&&typeof window.resolveMaterialRelation==='undefined');
  check(record.privateModule,'Material module leaked page globals');
  await page.evaluate(()=>{
   window.__violations=[];document.addEventListener('securitypolicyviolation',e=>window.__violations.push(e.effectiveDirective));
   const script=document.createElement('script');script.textContent='window.__probeInline=true';document.body.appendChild(script);
   const button=document.createElement('button');button.id='csp-inline-probe';button.textContent='安全探针';button.setAttribute('onclick','window.__probeAttribute=true');document.body.appendChild(button);
  });
  await page.locator('#csp-inline-probe').click();
  await page.addScriptTag({url:fixture.origin+'/__lab/csp-probe.js?instance='+fixture.instance});await page.waitForTimeout(200);
  record.csp=await page.evaluate(()=>({inline:!!window.__probeInline,attribute:!!window.__probeAttribute,eval:!!window.__probeEval,
    loaded:!!window.__probeLoaded,evalError:window.__probeEvalError,violations:window.__violations}));
  check(record.csp.loaded&&!record.csp.inline&&!record.csp.attribute&&!record.csp.eval&&record.csp.evalError==='EvalError','CSP did not block unapproved execution');
  await page.screenshot({path:path.join(output,'material-current.png')});
  const other=await browser.newContext();await other.route('**/*',route=>route.request().url().startsWith(fixture.origin+'/')?route.continue():route.abort());const otherPage=await login(other,fixture,'browser-b');
  const otherResponse=await otherPage.goto(fixture.origin+'/material/add?embedded=1');
  check((await otherResponse.headersArray()).filter(h=>h.name.toLowerCase()==='content-security-policy').length===2,'Second account lost page policy');
  await otherPage.locator('#unitSearch').fill('合成浏览器单位');await otherPage.keyboard.press('ArrowDown');await otherPage.keyboard.press('Enter');
  check(await otherPage.locator('#unitIdHidden').inputValue()!=='','Saved unit was not persistent for another account');await other.close();
  await page.getByRole('link',{name:/返回$/}).click();await page.waitForURL(url=>url.pathname==='/material');record.returnNavigation=true;
 }
 const state=await (await page.request.get(fixture.origin+'/__lab/state',{headers:{'X-Lab-Instance':fixture.instance}})).json();
 check(state.stock===25&&state.location_stock===25&&state.transaction_stock===25,'Entry actions changed inventory');
 check(state.inbound.every(r=>r.status==='pending')&&state.outbound.every(r=>r.status==='pending'),'Ordinary save completed a document');
 for(const code of ['CI-MATERIAL','BENCH-'+label+'-0'])check(state.materials.filter(r=>r.code===code).length===1,'Duplicate material rows');
 check(state.units.filter(r=>r.code==='CI-UNIT').length===1,'Duplicate unit rows');record.state=state;
 if(migrated)check(state.materials.filter(r=>r.code==='CI-KEYBOARD'&&r.unit_id===2).length===1,'Ordinary keyboard save did not persist the selected unit');
 check(record.pageErrors.length===0,'Unexpected page script error');await context.close();
}
(async()=>{
 let browser,fixture;
 try{
  proof.sha=git(['rev-parse','HEAD']);
  let base=process.env.WMS_BROWSER_BASELINE||'';
  if(!/^[0-9a-f]{40}$/.test(base)||/^0+$/.test(base))base=git(['rev-parse','HEAD^']);
  check(spawnSync('git',['merge-base','--is-ancestor',base,'HEAD'],{cwd:repo}).status===0,'Browser baseline is not an ancestor');
  const migratedBefore=spawnSync('git',['cat-file','-e',base+':app/static/js/pages/material-add.js'],{cwd:repo}).status===0;
  browser=await chromium.launch({channel:'chrome',headless:true});proof.browser=browser.version();
  if(!migratedBefore){
   const old=path.join(scratch,'old-source');fs.mkdirSync(old);const archive=path.join(scratch,'old-source.tar');
   check(spawnSync('git',['archive','--format=tar','--output',archive,base,'app'],{cwd:repo}).status===0,'Cannot archive accepted baseline');
   check(spawnSync('tar',['-xf',archive,'-C',old]).status===0,'Cannot extract owned baseline');
   proof.physicalBaseline=base;fixture=await server(old,'baseline-data');await exercise(browser,fixture,false);await fixture.close();fixture=null;
  }else proof.baselineNote='Parent already migrated;current regression remains mandatory. Earlier R8 baseline evidence retained.';
  fixture=await server(repo,'current-data');await exercise(browser,fixture,true);proof.success=true;
 }catch(error){
  proof.success=false;proof.failure=String(error.stack||error).replaceAll(password,'[synthetic-test-password]');process.exitCode=1;
  if(activePage&&!activePage.isClosed()){
   try{
    proof.failurePage={url:activePage.url(),title:await activePage.title(),buttons:await activePage.locator('button').evaluateAll(nodes=>nodes.map(node=>({text:node.textContent.trim(),visible:!!node.getClientRects().length,disabled:node.disabled,ordinary:node.hasAttribute('data-wms-save'),complete:node.hasAttribute('data-wms-save-complete')||node.hasAttribute('data-wms-save-complete-proxy')})))};
    await activePage.screenshot({path:path.join(output,'failure-page.png'),timeout:5000});
   }catch(snapshotError){proof.failureSnapshotError=String(snapshotError.message);}
  }
 }
 finally{if(fixture)await fixture.close();if(browser)await browser.close();fs.writeFileSync(path.join(output,'proof.json'),JSON.stringify(proof,null,2));}
 console.log(JSON.stringify({success:proof.success,browser:proof.browser,phases:proof.phases.map(p=>p.label),failure:proof.failure}));
})().catch(error=>{console.error(String(error).replaceAll(password,'[synthetic-test-password]'));process.exitCode=1;});
