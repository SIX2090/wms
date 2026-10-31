'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root=process.argv[2],scenario=process.argv[3],read=p=>fs.readFileSync(root+'/'+p,'utf8');
const flush=async()=>{await new Promise(setImmediate);await new Promise(setImmediate);};
class Ev {constructor(type,options={}){this.type=type;this.bubbles=!!options.bubbles;}preventDefault(){}stopPropagation(){this.stopped=true;}}
class E {
 constructor(tag){this.tagName=tag.toUpperCase();this.nodeType=1;this.children=[];this.attrs={};this.dataset={};this.events={};this.text='';this.checked=false;this.disabled=false;this.value='';}
 get childNodes(){return this.children;}
 get className(){return this.attrs.class||'';}set className(v){this.attrs.class=v;}
 get classList(){return {contains:x=>this.className.split(' ').includes(x),add:x=>{if(!this.className.split(' ').includes(x))this.className+=' '+x;}};}
 get textContent(){return this.text+this.children.map(x=>x.textContent).join('');}set textContent(v){this.text=String(v);this.children=[];}
 set innerHTML(v){assert.equal(v,'<span class="wms-mobile-field-label"></span><span class="wms-mobile-field-value"></span>');this.children=[];for(const c of ['wms-mobile-field-label','wms-mobile-field-value']){const e=new E('span');e.className=c;this.appendChild(e);}}
 setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k]??null;}removeAttribute(k){delete this.attrs[k];}
 appendChild(e){if(e.parentNode)e.parentNode.children=e.parentNode.children.filter(x=>x!==e);e.parentNode=this;this.children.push(e);return e;}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this);}
 matches(s){s=s.trim();if(s.includes(','))return s.split(',').some(x=>this.matches(x));const attr=s.match(/\[([^=\]]+)(?:="?([^"\]]+)"?)?\]/);if(attr){if(!(attr[1] in this.attrs)||attr[2]!==undefined&&this.attrs[attr[1]]!==attr[2])return false;s=s.replace(attr[0],'');}const [tag,cls]=s.split('.');return (!tag||this.tagName===tag.toUpperCase())&&(!cls||this.className.split(' ').includes(cls));}
 querySelectorAll(s){s=s.replace(/,\s*/g,',');if(s.includes(' ')){const parts=s.split(' ');return this.querySelectorAll(parts.at(-1)).filter(e=>{for(let p=e.parentNode;p;p=p.parentNode)if(p.matches(parts[0]))return true;return false;});}const found=[];for(const e of this.children){if(e.matches(s))found.push(e);found.push(...e.querySelectorAll(s));}return found;}
 querySelector(s){return this.querySelectorAll(s)[0]||null;}
 closest(s){for(let n=this;n;n=n.parentNode)if(n.matches(s))return n;return null;}
 insertAdjacentElement(where,e){assert.equal(where,'afterend');const p=this.parentNode;e.parentNode=p;p.children.splice(p.children.indexOf(this)+1,0,e);}
 cloneNode(deep){const e=new E(this.tagName);e.attrs={...this.attrs};e.dataset={...this.dataset};e.text=this.text;e.checked=this.checked;e.disabled=this.disabled;e.value=this.value;if(deep)this.children.forEach(n=>e.appendChild(n.cloneNode(true)));return e;}
 addEventListener(t,f){(this.events[t]??=[]).push(f);}
 dispatchEvent(e){e.target??=this;for(const f of this.events[e.type]||[])f.call(this,e);if(e.bubbles&&!e.stopped&&this.parentNode)this.parentNode.dispatchEvent(e);return true;}
 click(){if(!this.disabled)this.dispatchEvent(new Ev('click',{bubbles:true}));}
}
function fixture(image=true){
 const doc=new E('document'),wrap=doc.appendChild(new E('div'));wrap.className='table-responsive wms-mobile-table-scroll';
 const table=wrap.appendChild(new E('table'));table.className='table wms-mobile-table';table.setAttribute('id','materialTable');
 const head=table.appendChild(new E('thead')),hr=head.appendChild(new E('tr'));
 for(const label of ['选择','物料编码','状态','图片','操作','备注']){const th=hr.appendChild(new E('th'));th.textContent=label;}
 const tbody=table.appendChild(new E('tbody')),row=tbody.appendChild(new E('tr')),cells=Array.from({length:6},()=>row.appendChild(new E('td')));
 const check=cells[0].appendChild(new E('input'));check.setAttribute('type','checkbox');check.setAttribute('id','source-check');check.setAttribute('name','ids');check.value='1';
 cells[1].textContent='QA材料<&>';const badge=cells[2].appendChild(new E('span'));badge.className='badge';badge.textContent='启用';
 const calls=[];const action=(cell,title)=>{const b=cell.appendChild(new E('button'));b.setAttribute('id',title);b.setAttribute('onclick','inline-original');b.textContent=title;b.addEventListener('click',()=>calls.push(title));return b;};
 const statusAction=action(cells[2],'停用'),extra=action(cells[4],'其他操作');
 let picture;if(image){picture=cells[3].appendChild(new E('img'));picture.setAttribute('src','/static/local.png');picture.setAttribute('id','source-image');picture.setAttribute('onclick','previewOriginal');picture.addEventListener('click',()=>calls.push('preview'));}else picture=action(cells[3],'找图');
 cells[5].textContent='<img src=x onerror=bad()> & 正常文本';
 let sourceChanges=0;table.addEventListener('change',()=>sourceChanges++);
 const ctx={document:{querySelectorAll:s=>doc.querySelectorAll(s),createElement:t=>new E(t)},isMobileViewport:()=>scenario!=='desktop',Event:Ev};vm.createContext(ctx);
 const source=read('app/static/js/app.js');vm.runInContext(source.slice(source.indexOf('function textFromCell('),source.indexOf('function inputLabelFromCell(')),ctx);
 if(scenario==='entry-grid')table.classList.add('wms-entry-grid');ctx.initMobileListCards();
 return {ctx,doc,table,row,cells,check,calls,picture,statusAction,extra,get sourceChanges(){return sourceChanges;},get card(){return doc.querySelector('.wms-mobile-list-card');}};
}
(async()=>{
 if(['abort','network','server','session','reject-identity','unhandled-abort','unhandled-network'].includes(scenario)){
  const source=read('app/templates/base.html'),start=source.indexOf('    (function() {'),end=source.indexOf('    // Global CSRF helpers',start);assert(start>=0&&end>start);
  const error=scenario==='network'?new TypeError('offline'):new DOMException('cancelled','AbortError'),toasts=[],confirms=[];
  const listeners={},ctx={Headers,addEventListener:(t,f)=>{listeners[t]=f;},document:{querySelector:()=>({content:'csrf-test'})},location:{origin:'http://localhost',href:'unchanged'},fetch:()=>['server','session'].includes(scenario)?Promise.resolve({status:scenario==='server'?503:401}):Promise.reject(error),wmsGlobalErrorToast:m=>toasts.push(m),confirm:m=>{confirms.push(m);return false;},setTimeout(){}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
  if(scenario.startsWith('unhandled-')){listeners.unhandledrejection({reason:scenario==='unhandled-abort'?error:new TypeError('offline')});assert.equal(toasts.length,scenario==='unhandled-abort'?0:1);return;}
  let caught;await ctx.fetch('/fixture',{method:'POST'}).catch(e=>{caught=e;});await flush();
  if(scenario==='reject-identity')assert.equal(caught,error,'caller must still receive the original cancellation');
  else if(scenario==='abort')assert.equal(toasts.length,0,'active cancellation must not be reported as a network failure');
  else if(scenario==='network')assert.equal(toasts.length,1,'real network failures still need fallback');
  else if(scenario==='server')assert.match(toasts[0],/503/);
  else assert.equal(confirms.length,1);
  return;
 }
 const f=fixture(scenario!=='find-image');
 if(['desktop','entry-grid'].includes(scenario)){assert.equal(f.card,null);return;}
 assert(f.card);const cardCheck=f.card.querySelector('input[type="checkbox"]');
 if(scenario==='select'){assert(cardCheck,'visible card needs a selection control');cardCheck.checked=true;cardCheck.dispatchEvent(new Ev('change',{bubbles:true}));assert(f.check.checked);assert.equal(f.sourceChanges,1);assert.match(cardCheck.getAttribute('aria-label'),/QA材料/);}
 else if(['source-select','select-all'].includes(scenario)){assert(cardCheck);f.check.checked=true;(scenario==='source-select'?f.check:f.table).dispatchEvent(new Ev('change',{bubbles:true}));assert(cardCheck.checked);}
 else if(scenario==='disabled-select'){assert(cardCheck);f.check.disabled=true;f.table.dispatchEvent(new Ev('change'));assert(cardCheck.disabled);cardCheck.checked=true;cardCheck.dispatchEvent(new Ev('change'));assert(!f.check.checked);}
 else if(scenario==='image'){assert.equal(f.card.querySelector('img')?.getAttribute('src'),'/static/local.png');}
 else if(scenario==='image-click'){assert(f.card.querySelector('img'));f.card.querySelector('img').click();assert.deepEqual(f.calls,['preview']);}
 else if(scenario==='find-image'){const b=f.card.querySelectorAll('button').find(e=>e.textContent==='找图');assert(b,'image field button must remain available');b.click();assert.deepEqual(f.calls,['找图']);}
 else if(scenario==='actions'){const b=f.card.querySelectorAll('button').find(e=>e.textContent==='停用');assert(b);b.click();assert.deepEqual(f.calls,['停用']);}
 else if(scenario==='all-actions'){assert(f.card.querySelectorAll('button').some(e=>e.textContent==='其他操作'),'later action cell must not disappear');}
 else if(scenario==='status-once'){assert.equal(f.card.querySelectorAll('button').filter(e=>e.textContent==='停用').length,1,'status controls should appear once');}
 else if(scenario==='reinit'){f.ctx.initMobileListCards();assert.equal(f.doc.querySelectorAll('.wms-mobile-list-card').length,1);}
 else if(scenario==='text'){assert(f.card.textContent.includes('<img src=x onerror=bad()> & 正常文本'));assert.equal(f.card.querySelectorAll('img').length,1);}
 else if(scenario==='unique-ids'){assert.equal(f.card.querySelectorAll('[id]').length,0);}
 else if(scenario==='disabled-action'){f.statusAction.disabled=true;const b=f.card.querySelectorAll('button').find(e=>e.textContent==='停用');assert(b);b.click();assert.deepEqual(f.calls,[]);}
 else throw Error(scenario);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
