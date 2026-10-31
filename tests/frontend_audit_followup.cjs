'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2],scenario=process.argv[3];
const read=p=>fs.readFileSync(root+'/'+p,'utf8');
function fn(text,name){const start=text.indexOf('function '+name+'(');assert(start>=0,name);const open=text.indexOf('{',start);let depth=0;for(let i=open;i<text.length;i++){if(text[i]==='{')depth++;if(text[i]==='}'&&!--depth)return text.slice(start,i+1);}throw Error(name);}
function node(){const classes=new Set();return {value:'',disabled:false,checked:false,textContent:'',innerHTML:'',style:{},events:{},children:[],className:'',classList:{add:x=>classes.add(x),remove:x=>classes.delete(x),contains:x=>classes.has(x),toggle(x,on){on?classes.add(x):classes.delete(x);}},addEventListener(k,f){this.events[k]=f;},appendChild(n){n.parent=this;this.children.push(n);},remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this);},insertRow(){const n=node();n.cells=[];n.insertCell=()=>{const c=node();n.cells.push(c);return c;};this.children.push(n);return n;},focus(){}};}
const flush=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
(async()=>{
 if(scenario.startsWith('workstation-')||scenario.startsWith('route-')){
  const source=read('app/templates/print_routing.html'),fields=new Proxy({},{get:(o,k)=>o[k]??=node()});
  const ctx={document:{getElementById:k=>fields[k]},bootstrap:{Modal:class{show(){}}},onRuleWorkstationChange(){}};vm.createContext(ctx);
  const enabled=scenario.endsWith('-enabled');
  if(scenario.startsWith('workstation')){fields.wsEditEnabled.checked=!enabled;vm.runInContext(fn(source,'editWs'),ctx);ctx.editWs(1,'QA',2,enabled);assert.equal(fields.wsEditEnabled.checked,enabled);}
  else {vm.runInContext(fn(source,'prepareRuleModal')+'\n'+fn(source,'editRule'),ctx);ctx.editRule(1,'QA','out_order',2,3,4,100,enabled);assert.equal(fields.ruleEnabled.checked,enabled);}
  return;
 }
 if(scenario==='acceptance-load-race'){
  const fields=new Proxy({},{get:(o,k)=>o[k]??=node()}),go=node();fields.decision.querySelector=()=>go;
  let savedResponse;const ctx={document:{getElementById:k=>fields[k],createElement:node},Date,WMS:{api:{getRaw:async u=>u.includes('daily_snapshots')?{status:'ok',snapshots:[],latest_package_id:7}:new Promise(r=>savedResponse=r),postRaw:async()=>({status:'ok',package_db_id:8,validation_passed:true,validation_failures:[],seven_days_zero:true,package:{start_date:'2026-10-25',end_date:'2026-10-31'}})}}};
  vm.createContext(ctx);vm.runInContext(read('app/templates/ai_acceptance.html').match(/<script>([\s\S]*?)<\/script>/)[1],ctx);await flush();await fields.buildButton.onclick();assert(savedResponse);savedResponse({status:'ok',package:{id:7,go_no_go_decision:'no_go',decision_reason:'OBSOLETE saved reason'}});await flush();assert.equal(fields.packageStatus.textContent,'可签署');assert(!fields.signButton.disabled);assert.notEqual(fields.reason.value,'OBSOLETE saved reason');return;
 }
 if(scenario==='alert-parent-count'){
  const bells=[node(),node()];bells.forEach(b=>{b.classList.add('has-unread');const badge=node();badge.className='print-alert-badge';b.appendChild(badge);b.querySelector=()=>b.children[0]||null;});
  const action=node(),doc={querySelectorAll:s=>s==='.mark-read-btn'?[action]:[bells[0]],getElementById:()=>null,createElement:node};
  const parentDoc={querySelectorAll:()=>[bells[1]],createElement:node};let count=3,reloads=0;
  action.getAttribute=()=> '1';
  const ctx={document:doc,parent:{document:parentDoc},location:{reload(){reloads++;}},showToast(){},WMS:{api:{post:()=>Promise.resolve({unread_count:count})}}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(read('app/templates/print_alerts.html').match(/<script>([\s\S]*?)<\/script>/)[1],ctx);
  action.events.click();await flush();assert.equal(bells[1].children[0].textContent,'3');count=0;action.events.click();await flush();assert.equal(bells[1].children.length,0);assert(!bells[1].classList.contains('has-unread'));assert.equal(reloads,2);return;
 }
 if(scenario==='audit-parent'){
  const calls=[];let localClicks=0;const ctx={window:{parent:{WmsAiAssistant:{ask:x=>calls.push(x)}}},document:{getElementById:()=>({click(){localClicks++;}})},setTimeout(){},showToast(){}};
  vm.createContext(ctx);vm.runInContext(fn(read('app/templates/operation_audit.html'),'askAiAudit'),ctx);ctx.askAiAudit();assert.deepEqual(calls,['操作日志审计']);assert.equal(localClicks,0);return;
 }
 if(scenario==='audit-busy'){
  const src=read('app/static/js/pages/ai-assistant.js'),start=src.indexOf('window.WmsAiAssistant =');assert(start>=0,'shared assistant entry point');const end=src.indexOf("messages.addEventListener('click'",start);const panel=node(),calls=[],ctx={panel,calls,showToast(){}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext('let isSending=false;function sendAssistantMessage(t){calls.push(t);isSending=true;}\n'+src.slice(start,end),ctx);assert.equal(ctx.WmsAiAssistant.ask('操作日志审计'),true);assert(panel.classList.contains('open'));assert.equal(ctx.WmsAiAssistant.ask('操作日志审计'),false);assert.equal(calls.length,1);return;
 }
 if(scenario.startsWith('acceptance-')){
  const fields=new Proxy({},{get:(o,k)=>o[k]??=node()}),go=node();fields.decision.querySelector=()=>go;
  const decision=scenario.slice('acceptance-'.length),ctx={document:{getElementById:k=>fields[k],createElement:node},Date,WMS:{api:{getRaw:async u=>u.includes('daily_snapshots')?{status:'ok',snapshots:[],latest_package_id:7}:{status:'ok',package:{id:7,start_date:'2026-10-25',end_date:'2026-10-31',go_no_go_decision:decision,decision_reason:'QA saved reason',seven_day_summary:{all_absolute_zero:true}}}}}};
  vm.createContext(ctx);vm.runInContext(read('app/templates/ai_acceptance.html').match(/<script>([\s\S]*?)<\/script>/)[1],ctx);await flush();assert.equal(fields.reason.value,'QA saved reason');assert.equal(fields.packageStatus.textContent,{no_go:'不通过',go:'已通过',pending:'待签署'}[decision]);assert.equal(fields.signButton.disabled,decision!=='pending');assert(go.disabled,'restored evidence must not silently grant go permission');assert(fields.packagePanel.textContent.includes('2026-10-25'));return;
 }
 if(scenario.startsWith('ocr-')){
  const fields=new Proxy({},{get:(o,k)=>o[k]??=node()}),readers=[],pending=[],toasts=[];
  fields.recognizeBtn.disabled=true;fields.documentType.value='delivery_note';
  class Reader{constructor(){readers.push(this);}readAsDataURL(){}}
  const request=(url,data,options,raw)=>new Promise((resolve,reject)=>pending.push({url,data,options,resolve:body=>resolve(raw?{json:async()=>body}:body),reject}));
  const ctx={document:{getElementById:k=>fields[k],querySelector:()=>({content:'QA csrf'})},FileReader:Reader,AbortController,FormData:class{append(){}},escapeHtml:x=>String(x),showToast:(...x)=>toasts.push(x),fetch:(u,o)=>request(u,o.body,o,true),WMS:{api:{postRaw:(u,d,o)=>request(u,d,o,false)}}};ctx.window={addEventListener(){}};vm.createContext(ctx);vm.runInContext(read('app/templates/document_ocr.html').match(/<script>([\s\S]*?)<\/script>/)[1],ctx);
  const choose=name=>fields.fileInput.events.change({target:{files:[{name,type:'image/png',size:100}]}});
  const loaded=()=>readers.at(-1).onload({target:{result:'data:image/png;base64,QA'}});
  const click=()=>fields.recognizeBtn.events.click.call(fields.recognizeBtn,{});
  choose('A.png');
  if(scenario==='ocr-read-type-change'){fields.documentType.value='purchase';assert(fields.documentType.events.change);fields.documentType.events.change();loaded();assert(!fields.recognizeBtn.disabled);assert.equal(fields.uploadPreview.style.display,'block');return;}
  if(scenario==='ocr-clear-reader'){fields.clearImageBtn.events.click({stopPropagation(){}});loaded();assert(fields.recognizeBtn.disabled);assert.equal(fields.uploadPreview.style.display,'none');return;}
  if(scenario==='ocr-file-error'){assert.equal(typeof readers[0].onerror,'function');readers[0].onerror();assert(fields.recognizeBtn.disabled);assert(toasts.some(x=>/读取失败/.test(x[0])));return;}
  loaded();click();assert.equal(pending.length,1);assert(fields.recognizeBtn.disabled);
  const success={status:'success',reply:'QA OLD result',items:[{code:'QA-OLD',name:'old',quantity:2}]};
  if(scenario==='ocr-clear')fields.clearImageBtn.events.click({stopPropagation(){}});
  if(scenario==='ocr-replace'){choose('B.png');loaded();}
  if(scenario==='ocr-type-change'){fields.documentType.value='purchase';assert(fields.documentType.events.change);fields.documentType.events.change();}
  pending[0].resolve(scenario==='ocr-error'?{status:'error',msg:'QA rejected'}:success);await flush();
  if(['ocr-clear','ocr-replace','ocr-type-change'].includes(scenario)){
   assert(!fields.resultContent.innerHTML.includes('QA-OLD'),'obsolete response must not render');
   assert.equal(fields.recognizeBtn.disabled,scenario==='ocr-clear');
   if(scenario==='ocr-clear')assert(pending[0].options.signal.aborted);return;
  }
  assert(!fields.recognizeBtn.disabled);assert(fields.resultContent.innerHTML.includes(scenario==='ocr-error'?'QA rejected':'QA-OLD'));return;
 }
 throw Error('unknown '+scenario);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
