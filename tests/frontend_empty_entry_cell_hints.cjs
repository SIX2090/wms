'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const [root,scenario]=process.argv.slice(2);
const app=fs.readFileSync(path.join(root,'app/static/js/app.js'),'utf8');
const inbound=fs.readFileSync(path.join(root,'app/templates/in_order_add.html'),'utf8');
function extract(source,name){const start=source.indexOf('function '+name+'(');return start<0?'':source.slice(start,source.indexOf('\n}',start)+2);}
const classList=()=>{const values=new Set();return{add:x=>values.add(x),contains:x=>values.has(x),toggle(x,on){on?values.add(x):values.delete(x);}};};
let watched,observations=0;
const context=vm.createContext({Array,MutationObserver:class{constructor(fn){watched=fn;}observe(target,options){observations++;assert.equal(target,table);assert.equal(options.childList,true);assert.equal(options.subtree,true);assert.equal(options.attributes,undefined);}},calcTotal(){}});
for(const name of ['refreshWmsEntryCellHints','setupWmsEntryCellHints'])vm.runInContext(extract(app,name),context);
assert.equal(typeof context.refreshWmsEntryCellHints,'function','Missing shared empty-cell behavior');
assert.equal(typeof context.setupWmsEntryCellHints,'function');
assert(extract(app,'initDocumentEntryMode').includes('setupWmsEntryCellHints(table)'),'Existing entry-grid initializer must wire hints');
const table={classList:classList(),events:{},querySelectorAll(){return row.querySelectorAll();},addEventListener(n,fn){(this.events[n]??=[]).push(fn);}};
table.classList.add('wms-entry-grid');
const row={nodeType:1,controls:[],querySelectorAll(){return this.controls.filter(x=>x.type==='date'||x.tagName==='SELECT');},querySelector(sel){return this.fields?.[sel]||null;},matches:()=>false};
function input(type,value='',inside=true){const control={nodeType:1,tagName:type==='select'?'SELECT':'INPUT',type,value,required:false,validity:{badInput:false},classList:classList(),style:{},
    querySelectorAll:()=>[],matches:()=>type==='date'||type==='select',closest(sel){if(!inside)return null;if(sel==='table.wms-entry-grid')return table;if(sel==='tbody td')return {};if(sel==='tr')return row;return null;}};row.controls.push(control);return control;}
const date=input('date'),select=input('select'),text=input('text','LOT-001');
const empty=x=>x.classList.contains('wms-entry-cell-empty');
context.setupWmsEntryCellHints(table);
if(scenario==='empty'){assert(empty(date));assert(empty(select));assert(!empty(text));}
else if(scenario==='filled'){date.value='2026-11-07';select.value='0';context.refreshWmsEntryCellHints(row);assert(!empty(date));assert(!empty(select));assert.equal(select.value,'0');}
else if(scenario==='events'){for(const name of ['input','change','focusin','focusout']){date.value='2026-11-07';table.events[name][0]({target:date});assert(!empty(date));date.value='';table.events[name][0]({target:date});assert(empty(date));}}
else if(scenario==='invalid'){date.validity.badInput=true;context.refreshWmsEntryCellHints(date);assert(!empty(date),'Keep a partially entered invalid date visible');assert.equal(date.type,'date');date.validity.badInput=false;context.refreshWmsEntryCellHints(date);assert(empty(date));}
else if(scenario==='outside'){const header=input('date','',false);context.refreshWmsEntryCellHints(header);assert(!empty(header));}
else if(scenario==='dynamic'){const added=input('date');watched([{target:row,addedNodes:[added]}]);assert(empty(added));select.value='WH-1';watched([{target:select,addedNodes:[]}]);assert(!empty(select));}
else if(scenario==='idempotent'){context.setupWmsEntryCellHints(table);assert.equal(observations,1);for(const handlers of Object.values(table.events))assert.equal(handlers.length,1);}
else if(scenario==='consumer'){
    row.fields={'.material-expiry':date,'.material-batch-no':text,'.material-box-no':null};
    for(const key of ['qty','price','amount','brand','name','spec','unit','stock'])row.fields['.material-'+key]={value:key==='qty'?'2':key==='price'?'3':''};
    vm.runInContext(extract(inbound,'calcAmount')+'\n'+extract(inbound,'clearMaterialFields'),context);
    date.value='2026-11-07';context.calcAmount(row);assert(!empty(date),'Paste/edit/batch amount refresh must preserve the filled date');
    assert.equal(row.fields['.material-amount'].value,'6.00');
    context.clearMaterialFields(row);assert(empty(date),'Clearing an existing row must restore its blank appearance');
}
else throw Error('Unknown scenario '+scenario);
assert.equal(date.type,'date');assert.equal(date.required,false);assert.equal(text.value,scenario==='consumer'?'':'LOT-001');
assert.deepEqual(date.style,{});assert.equal(select.style.display,undefined);
