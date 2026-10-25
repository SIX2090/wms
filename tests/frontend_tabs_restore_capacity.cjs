const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const source = fs.readFileSync(require('path').join(__dirname,'..','app','static','js','app.js'),'utf8');
const start = source.indexOf('window.WmsTabs = (function()');
const end = source.indexOf('// 下拉框刷新',start);
assert(start >= 0 && end > start);
const script = source.slice(start,end);
const urls = ['/purchase_request/add','/purchase_order/add','/in_order/add','/out_order/add?type=purchase_return','/purchase_request','/purchase_order?view=list','/in_order?type=purchase_in','/supplier','/purchase_report','/report/view/purchase_order_execution','/report/view/supplier_purchase_summary','/report/view/material_purchase_summary','/report/view/purchase_price_analysis','/report/view/in_detail','/ai/replenishment'];
function makeRuntime(storage) {
 class Element {
   constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.classList={toggle(){},remove(){},add(){}};this.listeners={};this.style={};}
   setAttribute(k,v){this[k]=v;}
   addEventListener(k,fn){this.listeners[k]=fn;}
   appendChild(e){e.parentNode=this;this.children.push(e);}
   remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this);}
   querySelector(sel){if(sel==='.tab-close')return this.close||(this.close=new Element('button'));return null;}
 }
 const nodes={tabBar:new Element('div'),tabFrameWrap:new Element('div')};
 const window={location:{origin:'https://wms.fixture',pathname:urls[0],search:'',hash:''}};
 const ctx={window,URL,URLSearchParams,Map,Array,JSON,setTimeout(){},localStorage:{getItem:k=>storage[k]||null,setItem:(k,v)=>storage[k]=v,removeItem:k=>delete storage[k]},document:{getElementById:k=>nodes[k]||null,querySelectorAll:()=>[],createElement:t=>new Element(t)}};
 vm.runInNewContext(script,ctx);
 return {tabs:window.WmsTabs,nodes};
}
function run(count){
 const storage={};const first=makeRuntime(storage);
 urls.slice(0,count).forEach((u,i)=>first.tabs.open(u,'页面'+i));
 const before=JSON.parse(storage.wms_open_tabs);
 const second=makeRuntime(storage);second.tabs.restore();
 const after=JSON.parse(storage.wms_open_tabs);
 return {requested:count,before:before.tabs.length,after:after.tabs.length,lost:before.tabs.map(t=>t.url).filter(u=>!after.tabs.some(t=>t.url===u)),persistedAfterReload:after};
}
const count=Number(process.argv[2]);const result=run(count);assert.equal(result.before,count);assert.equal(result.after,count);assert.equal(result.lost.length,0);console.log(JSON.stringify(result));
