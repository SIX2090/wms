'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [root,scenario,evidence]=process.argv.slice(2);
function func(source,name){
 const match=new RegExp('(?:async )?function '+name+'\\(').exec(source);assert(match,name);
 let depth=0;for(let end=source.indexOf('{',match.index);end<source.length;end++){
  depth+=(source[end]==='{')-(source[end]==='}');if(!depth)return source.slice(match.index,end+1);
 }throw Error('Unclosed function '+name);
}
const template=fs.readFileSync(root+'/app/templates/adjustment_add.html','utf8');
const shared=fs.readFileSync(root+'/app/static/js/app.js','utf8');
const reason='合成仓库库存不足 <img src=x onerror=alert(1)>';
const fields={},buttons=[],calls=[],pending=[],messages=[],timers=[],navigation=[];let confirms=0;
class Element{
 constructor(tag){this.tag=tag;this.attrs={};this.children=[];this.style={};this._text='';this.value='';this.disabled=false;}
 getAttribute(k){return this.attrs[k]??null;}setAttribute(k,v){this.attrs[k]=String(v);}removeAttribute(k){delete this.attrs[k];}
 set textContent(v){this._text=String(v??'');this.children=[];}get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 set innerHTML(v){throw Error('Completion reason must not become HTML');}
 replaceChildren(...nodes){this.children=nodes;this._text='';}get firstChild(){return this.children[0]||null;}
 insertBefore(n,before){const index=this.children.indexOf(before);this.children.splice(index<0?this.children.length:index,0,n);return n;}
 focus(){this.focused=true;}scrollIntoView(){this.scrolled=true;}
}
const content=new Element('main');
function all(){const out=[];function visit(n){out.push(n);n.children.forEach(visit);}visit(content);return out;}
for(const [name,value] of Object.entries({date:'2026-11-01',warehouse_id:'2',order_id:'',adjustment_no:'QA50-PREVIEW',adjustment_type:'surplus',remark:'QA50-SYNTHETIC'})){
 const e=new Element('input');e.value=value;fields[name]=e;
}
for(const [key,disabled] of [['submitAdjustment',false],['submitAdjustment',false],['completeAdjustment',false],['submitAdjustment',true]]){
 const e=new Element('button');e.setAttribute('data-document-action',key);e.disabled=disabled;buttons.push(e);
}
const embedded=scenario==='http400';
const document={body:{classList:{contains:()=>embedded}},
 querySelector(selector){
  if(selector==='.embedded-content')return content;
  if(selector.startsWith('meta'))return{content:'qa50-public-csrf'};
  if(selector==='.footer-bar .btn-primary')return null; // Actual template has no footer-bar element.
  const names=[...selector.matchAll(/\[name="([^"]+)"\]/g)].map(match=>match[1]);
  for(const name of names)if(fields[name])return fields[name];return null;
 },
 querySelectorAll(selector){const keys=[...selector.matchAll(/data-document-action="([^"]+)"/g)].map(match=>match[1]);
  return keys.length?buttons.filter(button=>keys.includes(button.getAttribute('data-document-action'))):buttons;},
 createElement:tag=>new Element(tag),getElementById:id=>all().find(n=>n.id===id)||null};
let href='/adjustment/add'+(embedded?'?embedded=1':'');
const location={origin:'http://qa50.invalid',search:embedded?'?embedded=1':'',get href(){return href;},set href(v){href=v;navigation.push(v);}};
const ctx={document,Headers,FormData,URL,URLSearchParams,Promise,location,readonly:false,
 confirm(){confirms++;return true;},showToast:(message,type)=>messages.push({message,type}),
 collectItems:()=>({invalidRows:[],items:[{material_id:1,code:'QA50-M',quantity:2,location:'',reason:'synthetic'}]}),
 setTimeout(fn,delay){timers.push({fn,delay});},
 fetch(url,options){calls.push({url,body:JSON.parse(options.body),csrf:options.headers['X-CSRFToken']});
  return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);
vm.runInContext(fs.readFileSync(root+'/app/static/js/api.js','utf8'),ctx);
vm.runInContext(fs.readFileSync(root+'/app/static/js/document-action.js','utf8'),ctx);
for(const name of ['withEmbeddedParam','preserveEmbeddedUrl','showDocumentCompletionIssue'])vm.runInContext(func(shared,name),ctx);
for(const name of ['submitForm','completeAdjustment'])vm.runInContext(func(template,name),ctx);
const settle=async()=>{for(let i=0;i<8;i++)await new Promise(resolve=>setImmediate(resolve));};
const response=(status,body)=>({ok:status>=200&&status<300,status,json:()=>Promise.resolve(body)});
const proof={scenario,actual_template_functions:true,actual_api_wrapper:true,actual_document_action_lock:true,
 real_browser:false,real_network:false,real_database:false,real_inventory:false};
function observe(){return {calls:calls.map(c=>({url:c.url,body:c.body})),saved_id:fields.order_id.value,
 saved_number:fields.adjustment_no.value,panel:document.getElementById('wmsCompletionIssue')?.textContent||'',
 navigation:[...navigation],timers:timers.map(t=>t.delay),buttons:buttons.map(b=>({disabled:b.disabled,busy:b.getAttribute('aria-busy')})),messages:[...messages],confirms};}
async function duplicate(){ctx.submitForm(true);ctx.submitForm(false);ctx.completeAdjustment();await settle();}
async function run(){
 let finished=false;
 const first=ctx.submitForm(scenario!=='plain_save').then(()=>{finished=true;});
 ctx.submitForm(true);await settle();assert.equal(calls.length,1);assert.equal(calls[0].url,'/adjustment/add');
 assert.equal(calls[0].body.warehouse_id,'2');assert(!('warehouse' in calls[0].body));
 assert.equal(calls[0].csrf,'qa50-public-csrf');assert.equal(calls[0].body.order_id,'');
 if(scenario==='save_network')pending[0].reject(Error('合成保存网络中断'));
 else pending[0].resolve(response(200,scenario==='save_error'?{status:'error',msg:reason}:{status:'success',id:17,adjustment_no:'QA50-SAVED-17'}));
 await settle();
 if(scenario.startsWith('save_')){
  assert(finished,'save failure must settle');await first;assert.equal(calls.length,1);assert.equal(navigation.length,0);
  assert.equal(fields.order_id.value,'');assert.equal(content.children.length,0);assert(!buttons[0].disabled&&!buttons[1].disabled&&buttons[3].disabled);
  ctx.submitForm(true);await settle();assert.equal(calls.length,2,'save failure may be manually retried');
  proof.control=observe();return;
 }
 assert.equal(String(fields.order_id.value),'17');assert.equal(fields.adjustment_no.value,'QA50-SAVED-17');
 if(scenario==='plain_save'){
  assert.equal(calls.length,1);await duplicate();assert.equal(calls.length,1);
  assert.deepEqual(timers.map(t=>t.delay),[500]);timers.splice(0).forEach(t=>t.fn());await settle();assert(finished);await first;
  assert.equal(new URL(location.href,location.origin).pathname,'/adjustment/17');proof.control=observe();return;
 }
 assert.equal(calls.length,2);assert.equal(calls[1].url,'/adjustment/17/complete');assert.deepEqual(calls[1].body,{});
 await duplicate();assert.equal(calls.length,2,'completion in flight must not resave or reconfirm');
 if(scenario==='network')pending[1].reject(Error('合成完成网络中断'));
 else pending[1].resolve(response(scenario==='http400'?400:scenario==='http500'?500:200,
  {status:scenario==='success'?'success':'error',msg:reason}));
 await settle();proof.before_timer_delivery=observe();
 if(scenario==='success'){
  assert.deepEqual(timers.map(t=>t.delay),[600]);await duplicate();assert.equal(calls.length,2);
  timers.splice(0).forEach(t=>t.fn());await settle();assert(finished);await first;
  assert.equal(new URL(location.href,location.origin).pathname,'/adjustment/17');assert.equal(content.children.length,0);
  proof.control=observe();return;
 }
 timers.splice(0).forEach(t=>t.fn());await settle();proof.after_response=observe();
 // Capture whether a new write is possible independently of the feedback assertion.
 await duplicate();proof.after_repeat_attempt=observe();
 const panel=document.getElementById('wmsCompletionIssue');
 assert(panel,'saved adjustment must retain a persistent completion recovery panel');
 assert.equal(navigation.length,0,'failed or uncertain completion must not auto-navigate');
 assert.equal(calls.length,2,'saved completion result must be checked before any resubmission');
 assert.equal(confirms,0,'blocked completion must not open another confirmation');
 assert(buttons.every(button=>button.disabled),'saved result awaiting review must keep all write controls disabled');
 assert.equal(String(fields.order_id.value),'17');assert.equal(fields.adjustment_no.value,'QA50-SAVED-17');
 assert(panel.textContent.includes('QA50-SAVED-17'),'recovery feedback must identify the saved adjustment number');
 assert(panel.textContent.includes(['http500','network'].includes(scenario)?'完成结果待核对':'本次完成请求未成功'));
 assert(panel.textContent.includes(scenario==='network'?'合成完成网络中断':reason));
 assert.equal(panel.getAttribute('role'),'alert');assert(panel.focused&&panel.scrolled);
 assert(!all().some(n=>['img','script'].includes(n.tag)),'error reason must be literal text');
 const link=all().find(n=>n.tag==='a');assert(link);const target=new URL(link.href,location.origin);
 assert.equal(target.pathname,'/adjustment/17');assert.equal(target.searchParams.get('embedded'),embedded?'1':null);
 assert(finished,'recovery feedback must settle the action promise without navigation');await first;
}
const watchdog=setTimeout(()=>{process.stderr.write('QA50 unresolved simulation; no silent async exit\n');process.exit(91);},5000);
run().then(()=>{proof.passed=true;}).catch(error=>{proof.passed=false;proof.error=String(error);proof.final_state=observe();process.stderr.write(error.stack+'\n');process.exitCode=1;})
 .finally(()=>{clearTimeout(watchdog);fs.writeFileSync(evidence,JSON.stringify(proof,null,2));});
