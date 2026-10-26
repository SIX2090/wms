'use strict';
const fs = require('fs');
const vm = require('vm');
const assert = require('assert/strict');
const path = require('path');
const sourcePath = process.argv[2] || path.resolve(__dirname, '../app/static/js/quick-select.js');
const scenarios = [];
function test(name, fn) { scenarios.push([name, fn]); }
function setup(secondEntity = 'customer') {
  let now = 0, nextTimer = 0, menu;
  const timers = new Map(), pending = [], inputs = [], hidden = { value: '' };
  function el(tag) {
    const node = { tag, style: {}, dataset: {}, attrs: {}, listeners: {}, isConnected: true, value: '',
      children: [], scrollTop:0, clientHeight:290, scrollHeight:1000,
      classList: { add() {}, remove() {} }, appendChild(n) { this.children.push(n); if(typeof n==='object')n.parent=this; },
      remove(){this.parent.children=this.parent.children.filter(n=>n!==this);},
      insertAdjacentHTML(_,html){this.innerHTML+=html;},
      querySelector(selector){return this.children.find(n=>'.'+n.className===selector)||null;},
      focus(){document.activeElement=this;this.dispatch('focus');},
      setAttribute(k,v) { this.attrs[k] = v; },
      getAttribute(k) { return this.attrs[k] ?? null; }, addEventListener(k,f) { (this.listeners[k] ||= []).push(f); },
      dispatch(type, event = {}) { const ev = Object.assign({ type, target: this, prevented: false, preventDefault() { this.prevented = true; } }, event); for (const fn of this.listeners[type] || []) fn(ev); return ev; },
      dispatchEvent(ev) { return this.dispatch(ev.type, ev); }, getBoundingClientRect() { return { left:0, bottom:50, top:20, width:200 }; },
      contains(target) { return target === this || target?.parent === this; }, scrollIntoView() {},
      querySelectorAll() { return (this._ksItems || []).map((_,idx) => ({ classList:{add(){},remove(){}}, scrollIntoView(){}, getAttribute(){return String(idx);} })); }
    }; return node;
  }
  function input(name, submit = false, entity = 'supplier') {
    const n = el('input'); n.value = name; n.attrs = {'data-ks':entity,'data-ks-put':'name','data-ks-id':'#selectedId'};
    if(submit) n.attrs['data-ks-submit']='1';
    n.form = { submitted:0, requestSubmit(){this.submitted++;}, submit(){this.submitted++;} }; inputs.push(n); return n;
  }
  const a = input('A'), b = input('B',false,secondEntity);
  const document = Object.assign(el('document'), { readyState:'complete', activeElement:a,
    body:{appendChild(n){if(n.className === 'ks-menu') menu=n;}},head:{appendChild(){}},createElement:el,createTextNode:v=>v,
    getElementById(){return null;},querySelectorAll:()=>inputs,querySelector:()=>hidden });
  const window = Object.assign(el('window'), { innerHeight:800, innerWidth:1000 });
  class XHR {
    open(method,url){this.method=method;this.url=url;}setRequestHeader(){}send(){pending.push(this);}
    reply(items, total=items.length, offset=Number(new URL(this.url,'http://qa.invalid').searchParams.get('offset')||0)) { this.status=200;this.readyState=4;this.responseText=JSON.stringify({status:'success',total,data:items,offset});this.onreadystatechange(); }
    fail(){this.onerror();}
  }
  vm.runInNewContext(fs.readFileSync(sourcePath,'utf8'), {window,document,XMLHttpRequest:XHR,
    setTimeout(fn,ms=0){const id=++nextTimer;timers.set(id,{fn,at:now+ms});return id;},clearTimeout:id=>timers.delete(id),
    Date:{now:()=>now},Event:class{constructor(type,opts){this.type=type;Object.assign(this,opts);}} }, {filename:sourcePath});
  function tick(ms=200){const target=now+ms;for(let count=0;count<100;count++){const ready=[...timers].filter(([,t])=>t.at<=target).sort((x,y)=>x[1].at-y[1].at);if(!ready.length)break;const [id,t]=ready[0];timers.delete(id);now=t.at;t.fn();}now=target;}
  function focus(n){document.activeElement=n;n.dispatch('focus');}
  function blur(n,next=b){document.activeElement=next;n.dispatch('blur');}
  function change(n,value){n.value=value;n.dispatch('input');}
  function reply(n=pending.shift(),items=[{id:1,code:'A',name:'Alpha',label:'Alpha'}],total){assert.ok(n,'expected real XHR request');n.reply(items,total);}
  return {a,b,document,window,pending,focus,blur,change,tick,reply,hidden,get menu(){return menu;},get timerCount(){return timers.size;}};
}
function closed(s){assert.equal(s.menu.style.display,'none');assert.ok(s.menu._ksInput == null);}
test('escape rejects pending success',()=>{const s=setup();s.focus(s.a);s.a.dispatch('keydown',{key:'Escape'});s.reply();closed(s);});
test('escape cancels input debounce',()=>{const s=setup();s.change(s.a,'new');s.a.dispatch('keydown',{key:'Escape'});s.tick();assert.equal(s.pending.length,0);closed(s);});
test('keyword changes invalidate before debounce',()=>{const s=setup();s.focus(s.a);s.change(s.a,'B');s.reply();closed(s);s.tick();s.reply(undefined,[{id:2,name:'Beta',code:'B'}]);assert.equal(s.menu._ksInput,s.a);assert.equal(s.menu._ksItems[0].name,'Beta');});
test('programmatic value change blocks old success',()=>{const s=setup();s.focus(s.a);s.a.value='B';s.reply();closed(s);});
test('change event cancels old pending',()=>{const s=setup();s.focus(s.a);s.a.dispatch('change');s.reply();closed(s);});
test('blur and refocus same input rejects old result',()=>{const s=setup();s.focus(s.a);const old=s.pending.shift();s.blur(s.a);s.focus(s.a);old.reply([{id:1,name:'old A'}]);closed(s);s.reply();assert.equal(s.menu._ksInput,s.a);});
test('old blur cannot close new owner',()=>{const s=setup();s.focus(s.a);const old=s.pending.shift();s.blur(s.a);s.focus(s.b);s.reply(undefined,[{id:2,name:'Beta'}]);s.tick();old.reply([{id:1,name:'Alpha'}]);assert.equal(s.menu._ksInput,s.b);assert.equal(s.menu._ksItems[0].name,'Beta');});
test('showAll cannot steal another owner',()=>{const s=setup();s.a.dispatch('keydown',{key:'ArrowDown'});const old=s.pending.shift();s.focus(s.b);s.reply(undefined,[{id:2,name:'Beta'}]);old.reply([{id:1,name:'Alpha'}]);assert.equal(s.menu._ksInput,s.b);});
test('showAll checks focus even without blur dispatch',()=>{const s=setup();s.a.dispatch('keydown',{key:'ArrowDown'});s.document.activeElement=s.b;s.reply();closed(s);});
for(const event of ['scroll','resize']) {
  test(event+' rejects pending callback',()=>{const s=setup();s.focus(s.a);(event==='scroll'?s.document:s.window).dispatch(event);s.reply();closed(s);});
  test(event+' cancels queued debounce',()=>{const s=setup();s.change(s.a,'next');(event==='scroll'?s.document:s.window).dispatch(event);s.tick();assert.equal(s.pending.length,0);closed(s);});
}
test('outside click rejects pending callback',()=>{const s=setup();s.focus(s.a);s.document.dispatch('click',{target:{getAttribute(){return null;}}});s.reply();closed(s);});
test('detached input never renders',()=>{const s=setup();s.focus(s.a);s.a.isConnected=false;s.reply();closed(s);});
test('composition start invalidates pre-composition result',()=>{const s=setup();s.focus(s.a);s.a.dispatch('compositionstart');s.reply();closed(s);});
test('composition does not search and final text searches once',()=>{const s=setup();s.a.dispatch('compositionstart');s.change(s.a,'pin');s.tick();assert.equal(s.pending.length,0);const key=s.a.dispatch('keydown',{key:'Enter',isComposing:true});assert.equal(key.prevented,false);s.a.value='拼音';s.a.dispatch('compositionend');s.tick();assert.equal(s.pending.length,1);s.reply(undefined,[{id:1,name:'拼音'}]);assert.equal(s.menu.style.display,'block');});
test('normal local pool and pure selection Enter preserve ID and change',()=>{const s=setup();let changes=0;s.a.addEventListener('change',()=>changes++);s.focus(s.a);s.reply();const key=s.a.dispatch('keydown',{key:'Enter'});assert.equal(key.prevented,true);assert.equal(s.a.value,'Alpha');assert.equal(s.hidden.value,1);assert.equal(changes,1);closed(s);s.focus(s.a);assert.equal(s.pending.length,0);assert.equal(s.menu._ksItems[0].name,'Alpha');});
test('highlight arrows wrap and Enter selects',()=>{const s=setup();s.focus(s.a);s.reply(undefined,[{id:1,name:'Alpha'},{id:2,name:'A Beta'}]);s.a.dispatch('keydown',{key:'ArrowUp'});assert.equal(s.menu._ksActive,1);s.a.dispatch('keydown',{key:'Enter'});assert.equal(s.a.value,'A Beta');closed(s);});
test('search Enter preserves keyword default submit',()=>{const s=setup();s.a.attrs['data-ks-submit']='1';s.focus(s.a);s.reply();const key=s.a.dispatch('keydown',{key:'Enter'});assert.equal(key.prevented,false);assert.equal(s.a.value,'A');assert.equal(s.a.form.submitted,0);closed(s);});
test('search highlighted selection submits once',()=>{const s=setup();s.a.attrs['data-ks-submit']='1';s.focus(s.a);s.reply();s.a.dispatch('keydown',{key:'ArrowDown'});s.a.dispatch('keydown',{key:'Enter'});assert.equal(s.a.form.submitted,1);assert.equal(s.a.value,'Alpha');closed(s);});
test('mouse selection commits then closes',()=>{const s=setup();s.focus(s.a);s.reply();const item={getAttribute:()=> '0'};s.menu.dispatch('mousedown',{target:{closest:selector=>selector==='.ks-item'?item:null}});assert.equal(s.a.value,'Alpha');closed(s);});
test('error does not reopen dismissed input',()=>{const s=setup();s.focus(s.a);const req=s.pending.shift();s.a.dispatch('keydown',{key:'Escape'});req.fail();closed(s);});
test('current empty result remains visible and retries',()=>{const s=setup();s.focus(s.a);s.reply(undefined,[]);assert.equal(s.menu.style.display,'block');assert.match(s.menu.innerHTML,/无匹配结果/);s.a.dispatch('keydown',{key:'Escape'});s.a.dispatch('click');assert.equal(s.pending.length,1);s.reply();assert.equal(s.menu.style.display,'block');});
test('remote mode preserves options envelope and keyword URL',()=>{const s=setup();s.focus(s.a);s.reply(undefined,[{id:1,name:'Alpha'}],201);assert.equal(s.pending.length,1);assert.match(s.pending[0].url,/kw=A&limit=50/);s.reply();assert.equal(s.menu.style.display,'block');s.change(s.a,'Bee');s.tick();assert.match(s.pending[0].url,/kw=Bee&limit=50/);s.reply(undefined,[{id:2,name:'Bee'}],201);assert.equal(s.menu._ksItems[0].name,'Bee');});
test('selected item invalidates hidden pending showAll',()=>{const s=setup();s.focus(s.a);const old=s.pending.shift();s.a.dispatch('keydown',{key:'ArrowDown'});s.reply();s.a.dispatch('keydown',{key:'Enter'});old.reply([{id:7,name:'A old'}]);closed(s);assert.equal(s.a.value,'Alpha');});
test('same entity different inputs reject old showAll',()=>{const s=setup('supplier');s.a.dispatch('keydown',{key:'ArrowDown'});const old=s.pending.shift();s.blur(s.a);s.focus(s.b);s.reply(undefined,[{id:2,name:'Beta'}]);old.reply([{id:1,name:'Alpha'}]);assert.equal(s.menu._ksInput,s.b);assert.equal(s.menu._ksItems[0].name,'Beta');});
test('showAll opens empty keyword options for active input',()=>{const s=setup();s.a.value='unmatched';s.a.dispatch('keydown',{key:'ArrowDown'});s.reply();assert.equal(s.menu.style.display,'block');assert.equal(s.menu._ksItems[0].name,'Alpha');});
test('pending search Enter closes and releases normal submit',()=>{const s=setup();s.a.attrs['data-ks-submit']='1';s.focus(s.a);const key=s.a.dispatch('keydown',{key:'Enter'});assert.equal(key.prevented,false);s.reply();closed(s);});
test('composition keyCode229 and arrows remain native',()=>{const s=setup();s.a.dispatch('compositionstart');for(const key of ['Enter','ArrowDown','ArrowUp']){assert.equal(s.a.dispatch('keydown',{key,keyCode:229}).prevented,false);}assert.equal(s.pending.length,0);});
test('compositionend followed by input debounces once',()=>{const s=setup();s.a.dispatch('compositionstart');s.a.value='中文';s.a.dispatch('compositionend');s.a.dispatch('input');s.tick();assert.equal(s.pending.length,1);s.reply(undefined,[{id:1,name:'中文'}]);assert.equal(s.menu.style.display,'block');});
test('closed first remote probe cannot render second-stage response',()=>{const s=setup();s.focus(s.a);s.a.dispatch('keydown',{key:'Escape'});s.reply(undefined,[{id:1,name:'Alpha'}],201);assert.equal(s.pending.length,1);s.reply();closed(s);});
test('blur cancels scheduled debounce immediately',()=>{const s=setup();s.change(s.a,'later');s.blur(s.a);s.tick();assert.equal(s.pending.length,0);closed(s);});
test('focus click can recover after Escape',()=>{const s=setup();s.focus(s.a);const old=s.pending.shift();s.a.dispatch('keydown',{key:'Escape'});s.a.dispatch('click');s.reply();old.reply([{id:9,name:'A stale'}]);assert.equal(s.menu.style.display,'block');assert.equal(s.menu._ksItems[0].name,'Alpha');});
function many(count,start=1){return Array.from({length:count},(_,i)=>({id:start+i,code:'A'+String(start+i).padStart(3,'0'),name:'Alpha '+(start+i),spec:'BV '+(start+i)}));}
function more(s){s.menu.dispatch('click',{target:{closest:selector=>selector==='.ks-more'?{}:null}});}
test('candidate scroll keeps the menu and current owner',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(30));s.document.dispatch('scroll',{target:s.menu});assert.equal(s.menu.style.display,'block');assert.equal(s.menu._ksInput,s.a);});
test('descendant scroll keeps candidates',()=>{const s=setup();s.focus(s.a);s.reply();s.document.dispatch('scroll',{target:{parent:s.menu}});assert.equal(s.menu.style.display,'block');});
test('local pool loads every candidate after fifty',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(125));assert.equal(s.menu._ksItems.length,50);more(s);assert.equal(s.menu._ksItems.length,100);more(s);assert.equal(s.menu._ksItems.length,125);assert.equal(new Set(s.menu._ksItems.map(x=>x.id)).size,125);assert.equal(s.pending.length,0);assert.match(s.menu.querySelector('.ks-footer').innerHTML,/125 \/ 125/);});
test('scroll bottom appends local candidates without closing',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(80));s.menu.scrollTop=710;s.document.dispatch('scroll',{target:s.menu});assert.equal(s.menu.style.display,'block');assert.equal(s.menu._ksItems.length,80);});
test('remote paging reaches the last candidate and preserves rich fields',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);for(let offset=50;offset<265;offset+=50){more(s);assert.match(s.pending[0].url,new RegExp('offset='+offset+'$'));s.reply(undefined,many(Math.min(50,265-offset),offset+1),265);}assert.equal(s.menu._ksItems.length,265);assert.equal(s.menu._ksItems.at(-1).spec,'BV 265');assert.equal(new Set(s.menu._ksItems.map(x=>x.id)).size,265);});
test('load more cannot overlap or append after Escape',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);more(s);assert.equal(s.pending.length,1);s.a.dispatch('keydown',{key:'Escape'});s.reply(undefined,many(50,51),265);closed(s);assert.equal(s.menu._ksItems.length,50);});
test('changed keyword rejects old page response',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);const old=s.pending.shift();s.change(s.a,'Bee');s.tick();s.reply(undefined,[{id:999,name:'Bee'}]);old.reply(many(50,51),265);assert.equal(s.menu._ksItems.length,1);assert.equal(s.menu._ksItems[0].name,'Bee');});
test('failed page keeps previous rows and retries the same offset',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);s.pending.shift().fail();assert.equal(s.menu._ksItems.length,50);assert.match(s.menu.querySelector('.ks-footer').innerHTML,/重试/);more(s);assert.match(s.pending[0].url,/offset=50$/);s.reply(undefined,many(50,51),265);assert.equal(s.menu._ksItems.length,100);});
test('blank remote pool can also load beyond first page',()=>{const s=setup();s.a.value='';s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);assert.match(s.pending[0].url,/kw=&limit=50&offset=50/);});
test('keyboard at last row loads next page without wrapping',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(70));s.menu._ksActive=49;s.a.dispatch('keydown',{key:'ArrowDown'});assert.equal(s.menu._ksItems.length,70);assert.equal(s.menu._ksActive,49);s.a.dispatch('keydown',{key:'ArrowDown'});assert.equal(s.menu._ksActive,50);s.a.dispatch('keydown',{key:'Enter'});assert.equal(s.hidden.value,51);closed(s);});
test('dragging scrollbar preserves owner through blur and restores focus',()=>{const s=setup();s.focus(s.a);s.reply();s.menu.dispatch('mousedown',{target:{closest:()=>null}});s.blur(s.a);assert.equal(s.menu.style.display,'block');s.document.dispatch('mouseup');assert.equal(s.document.activeElement,s.a);assert.equal(s.pending.length,0);});
test('short narrow viewport contains the entire menu',()=>{const s=setup();s.window.innerHeight=130;s.window.innerWidth=240;s.a.getBoundingClientRect=()=>({left:180,top:60,bottom:90,width:200});s.focus(s.a);s.reply();assert.equal(s.menu.style.bottom,'73px');assert.equal(s.menu.style.maxHeight,'49px');assert.equal(s.menu.style.width,'220px');assert.equal(s.menu.style.left,'12px');});
test('choosing a loaded material preserves exact ID and change event',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(75));more(s);let changed=0;s.a.addEventListener('change',()=>changed++);s.menu.dispatch('mousedown',{target:{closest:selector=>selector==='.ks-item'?{getAttribute:()=> '74'}:null}});assert.equal(s.hidden.value,75);assert.equal(s.a.value,'Alpha 75');assert.equal(changed,1);closed(s);});
test('outside page scroll still closes loaded candidates',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(75));more(s);s.document.dispatch('scroll',{target:s.document});closed(s);});
test('programmatic value change rejects old page without an input event',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);s.a.value='different';s.reply(undefined,many(50,51),265);assert.equal(s.menu._ksItems.length,50);});
test('server ignoring offset never appends duplicate first page',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);s.pending.shift().reply(many(50),265,0);assert.equal(s.menu._ksItems.length,50);assert.match(s.menu.querySelector('.ks-footer').innerHTML,/重试/);});
test('failed page does not start automatic scroll retry loop',()=>{const s=setup();s.focus(s.a);s.reply(undefined,many(200),265);s.reply(undefined,many(50),265);more(s);s.pending.shift().fail();s.menu.scrollTop=710;s.document.dispatch('scroll',{target:s.menu});assert.equal(s.pending.length,0);assert.equal(s.menu.style.display,'block');});
const results = scenarios.map(([name,fn])=>{try{fn();return {name,ok:true};}catch(e){return {name,ok:false,error:e.message,kind:e.name};}});
process.stdout.write(JSON.stringify({source:sourcePath,passed:results.filter(x=>x.ok).length,failed:results.filter(x=>!x.ok).length,results},null,2)+'\n');
process.exitCode=results.some(x=>!x.ok)?1:0;
