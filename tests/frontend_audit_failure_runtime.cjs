'use strict';
// Run verbatim production handlers with synthetic DOM/I/O, never a browser/device.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2],scenario=process.argv[3];
const read=p=>fs.readFileSync(root+'/'+p,'utf8').replace(/\r\n/g,'\n');
function fn(text,name){const start=text.indexOf('function '+name+'(');assert(start>=0,name);const open=text.indexOf('{',start);let depth=0;for(let i=open;i<text.length;i++){if(text[i]==='{')depth++;if(text[i]==='}'&&!--depth)return text.slice(start,i+1); }throw Error(name);}
function node(value=''){return {value,hidden:false,disabled:false,textContent:'',events:{},children:[],dataset:{},classList:{contains:()=>false},focus(){},click(){this.events.click?.({});},addEventListener(k,f){this.events[k]=f;},getTracks(){return [];},querySelectorAll(){return [];}};}
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 if(scenario.startsWith('material-empty-')){
  const source=read('app/templates/material.html'),start=source.indexOf('    window.fixEmptyFields ='),end=source.indexOf('    // 删除全部物料入口',start),messages=[];let reloads=0;
  const ctx={window:{},confirm:()=>true,showToast:(m,t)=>messages.push({m,t}),location:{reload(){reloads++;}},WMS:{api:{postRaw:()=>scenario.endsWith('error')?Promise.reject(Error('缺少计量单位，尚未修改物料')):Promise.resolve({status:'success',msg:'已修复 1 条物料的空字段'})}}};
  vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);ctx.window.fixEmptyFields();await flush();await flush();
  assert.equal(reloads,scenario.endsWith('error')?0:1);assert.equal(messages.length,1);assert.equal(messages[0].t,scenario.endsWith('error')?'danger':'success');return;
 }
 if(scenario.startsWith('acceptance-')){
  const source=read('app/templates/ai_acceptance.html'),fields={},calls=[],go={disabled:false};
  const element=()=>({...node(),appendChild(){},insertRow(){return {cells:[],insertCell(){const cell={};this.cells.push(cell);return cell;}};},querySelector:()=>go});
  const field=k=>fields[k]??=element();field('decision').value='go';field('reason').value='SYN';
  const result=u=>u.includes('daily_snapshots')?{status:'ok',snapshots:[]}:{status:'ok',package_db_id:1,validation_passed:scenario==='acceptance-valid',validation_failures:[],seven_days_zero:scenario==='acceptance-valid',package:{}};
  const request=(u,p)=>{calls.push({u,p});return Promise.resolve(result(u));};
  const ctx={document:{getElementById:field,createElement:element},WMS:{api:{getRaw:request,postRaw:request}},fetch:async(u,o)=>({ok:true,json:async()=>{calls.push({u,p:o});return result(u);}}),Date};
  vm.createContext(ctx);vm.runInContext(source.match(/<script>([\s\S]*?)<\/script>/)[1],ctx);await flush();await field('buildButton').onclick();
  field('decision').value='go';await field('signButton').onclick();
  if(scenario==='acceptance-invalid'){
   assert(go.disabled);assert.equal(calls.filter(c=>c.u.endsWith('/go_no_go')).length,0);assert(field('message').textContent.includes('不能签署'));return;
  }
  assert.equal(field('packageStatus').textContent,'已通过');assert(field('signButton').disabled);return;
 }
 if(scenario.startsWith('photo-')){
  const source=read('app/templates/mobile_scan.html'),start=source.indexOf('    var cameraBtn ='),end=source.indexOf('    window.setTimeout(',start);
  const fields=Object.fromEntries(['cameraBtn','cameraFileInput','recognizePreview','recognizePreviewImg','recognizeLoading','closePreviewBtn'].map(k=>[k,node()]));
  const readers=[],calls=[],messages=[];let lookups=0,resolve;
  class Reader{constructor(){readers.push(this);}readAsDataURL(){} }
  const ctx={document:{getElementById:k=>fields[k]},window:{},FileReader:Reader,FormData:class{append(){}},AbortController,
   setTimeout:()=>1,clearTimeout(){},scanCode:node(),setStatus:(m,t)=>messages.push({m,t}),lookupMaterial:()=>lookups++,renderMatches(){},
   WMS:{api:{postRaw:(u,data,options)=>{calls.push({u,data,options});return new Promise(r=>resolve=r);}}}};
  vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
  if(scenario==='photo-cancel-empty'){fields.cameraFileInput.events.change({target:{files:[]}});assert.equal(calls.length,0);assert.equal(readers.length,0);return;}
  fields.cameraFileInput.events.change({target:{files:[{name:'SYN.png'}]}});
  if(scenario==='photo-read-error'){
   readers[0].onerror();await flush();assert.equal(calls.length,0,'failed file read must not upload');assert(messages.some(x=>/读取失败/.test(x.m)));assert(!fields.cameraBtn.disabled);return;
  }
  if(scenario==='photo-close-before-read'){
   fields.closePreviewBtn.events.click();readers[0].onload({target:{result:'data:image/png;base64,SYN'}});await flush();assert.equal(calls.length,0,'closed preview must ignore old reader');return;
  }
  readers[0].onload({target:{result:'data:image/png;base64,SYN'}});await flush();
  assert.equal(calls.length,1);fields.closePreviewBtn.events.click();
  assert(calls[0].options.signal.aborted,'closing must abort recognition');
  resolve({status:'success',matches:[{code:'STALE'}]});await flush();await flush();
  assert.equal(lookups,0,'late canceled recognition must not select material');assert(!fields.cameraBtn.disabled);return;
 }
 if(scenario.startsWith('scanner-')){
  const source=read('app/templates/mobile_scan.html'),messages=[],timers=[],scanner=node(),video=node();scanner.hidden=true;
  const ctx={barcodeScanner:scanner,barcodeVideo:video,zxingCodeReader:null,scanCode:node(),setStatus:(m,t)=>messages.push({m,t}),lookupMaterial(){},setTimeout:f=>timers.push(f),Map};
  if(scenario!=='scanner-missing')ctx.ZXing={BrowserMultiFormatReader:class{reset(){}decodeFromVideoDevice(){return Promise.reject({name:'NotAllowedError'});}},BarcodeFormat:{},DecodeHintType:{}};
  vm.createContext(ctx);vm.runInContext(fn(source,'stopBarcodeScanner')+'\n'+fn(source,'startBarcodeScanner'),ctx);ctx.startBarcodeScanner();
  if(scenario==='scanner-missing'){assert(messages.some(x=>/库加载失败/.test(x.m)));return;}
  assert.equal(scanner.hidden,false,'scanner must remain visible while opening camera');
  timers.forEach(f=>f());await flush();assert(messages.some(x=>/权限被拒绝/.test(x.m)));assert.equal(scanner.hidden,true);return;
 }
 if(scenario.startsWith('printer-')||scenario.startsWith('rule-')){
  const source=read('app/templates/print_routing.html'),fields={},calls=[],messages=[];
  const defaults={printerAddWsId:'1',printerAddName:'SYN',printerAddSystemName:'',printerAddType:'mixed',printerAddEnabled:'1',ruleName:'SYN',ruleEvent:'in_order',ruleWarehouse:'',ruleWorkstation:'1',rulePrinter:'2',rulePriority:'100',ruleEditId:'',ruleEnabled:'1'};
  Object.entries(defaults).forEach(([k,v])=>fields[k]=node(v));
  if(scenario==='printer-whitespace')fields.printerAddName.value='  ';
  if(scenario==='printer-no-station')fields.printerAddWsId.value='';
  if(scenario==='rule-whitespace')fields.ruleName.value='  ';
  if(scenario==='rule-priority-zero')fields.rulePriority.value='0';
  if(scenario==='rule-priority-fraction')fields.rulePriority.value='1.5';
  if(scenario==='rule-bad-event')fields.ruleEvent.value='bad';
  const ctx={document:{getElementById:k=>fields[k]},WMS:{api:{post:(u,d)=>{calls.push({u,d});return Promise.resolve({msg:'SYN'});}}},showToast:(m,t)=>messages.push({m,t}),location:{reload(){}}};
  vm.createContext(ctx);const name=scenario.startsWith('printer-')?'addPrinter':'saveRule';vm.runInContext(fn(source,name),ctx);ctx[name]();await flush();
  assert.equal(calls.length,0,'invalid config must be rejected before request');assert(messages.length);return;
 }
 if(scenario==='checkbox-resizer'){
  const source=read('app/static/js/app.js'),box={tagName:'INPUT',type:'checkbox',classList:{contains:()=>false}},resizer={tagName:'SPAN',classList:{contains:k=>k==='cb-col-resizer'}},text={nodeType:3,textContent:'column_0'};
  const th={children:[box,resizer],firstElementChild:box,childNodes:[text,box,resizer],insertBefore(){throw Error('must not insert checkbox label');}};
  const ctx={Array};vm.createContext(ctx);vm.runInContext(fn(source,'setHeaderLabel'),ctx);ctx.setHeaderLabel(th,'column_0');assert.equal(text.textContent,'');return;
 }
 if(scenario==='quality-card'||scenario==='quality-low-correction'||scenario==='quality-high-correction'){
  const source=read('app/templates/ai_business_quality.html'),container=node();
  const ctx={document:{getElementById:()=>container,querySelector:()=>container},escapeHtml:x=>x};vm.createContext(ctx);
  if(scenario==='quality-card'){
   vm.runInContext(fn(source,'renderMetricsCards'),ctx);ctx.renderMetricsCards({human_correction_rate:{label:'人工修正率',rate:0.1,numerator:1,denominator:10}});
   assert(container.innerHTML.includes('text-success'));return;
  }
  vm.runInContext(fn(source,'renderLowQualitySamples'),ctx);
  const metrics=Object.fromEntries(['classification_accuracy','header_accuracy','line_recall','material_match_rate','draft_adoption_rate','duplicate_interception_rate'].map(k=>[k,0.6]));
  metrics.human_correction_rate=scenario==='quality-low-correction'?0:1;
  ctx.renderLowQualitySamples({by_dimension:{source:{SYN:metrics}}});
  assert.equal(container.innerHTML.includes('source-SYN'),scenario==='quality-high-correction');return;
 }
 if(scenario==='quality-improved-color'){
  const source=read('app/templates/ai_business_quality.html'),container=node();
  const ctx={document:{getElementById:()=>container},escapeHtml:x=>x};vm.createContext(ctx);vm.runInContext(fn(source,'renderVersionComparison'),ctx);
  ctx.renderVersionComparison({baseline_version:'SYN-B',current_version:'SYN-C',generated_at:'SYN',deltas:{human_correction_rate:-0.3},regressions:[],baseline_metrics:{human_correction_rate:{label:'人工修正率',rate:0.4}},current_metrics:{human_correction_rate:{rate:0.1}}});
  assert(container.innerHTML.includes('提升'),'lower correction must display improvement');assert(!container.innerHTML.includes('badge bg-danger'));return;
 }
 throw Error('Unknown scenario '+scenario);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
