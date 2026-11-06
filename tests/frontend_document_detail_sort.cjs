'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const [root, scenario] = process.argv.slice(2);
const source = fs.readFileSync(path.join(root,'app/static/js/app.js'),'utf8');
const start = source.indexOf('function setupDetailRowSorting(');
const code = start < 0 ? '' : source.slice(start,source.indexOf('\n}',start)+2);
const keys=['row_no','selection','material_code','quantity','amount','actions'];
const labels=['序号','选择','物料编码','数量','金额','操作'];
const classes=()=>({add(){},contains:()=>false});
const headers=keys.map((key,i)=>({dataset:scenario==='unkeyed'?{}:{columnKey:key},style:{},classList:classes(),textContent:labels[i],attrs:{},children:[],events:{},
    querySelector(sel){return sel==='.cb-sort-indicator'?this.children[0]:sel==='input,button'&&key==='selection'?{}:null;},
    appendChild(node){this.children.push(node);},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,fn){(this.events[k]||=[]).push(fn);}}));
const head={cells:headers};headers.forEach(h=>h.parentNode=head);
function row(id,code,qty){
    const number={textContent:String(id),querySelector:()=>null},control={value:String(qty)},checkbox={checked:id===2,value:'item-'+id};
    const values=[String(id),'',code,String(qty),'￥'+(qty*10).toLocaleString('en-US'),''];
    const cells=keys.map((key,i)=>({dataset:scenario==='unkeyed'?{}:{columnKey:key},textContent:values[i],colSpan:1,
        querySelector(sel){return key==='quantity'&&sel.startsWith('input:not')?this.input||null:null;}}));
    const item={dataset:{id:String(id),index:String(10+id)},cells,number,control,checkbox,classList:classes(),querySelector(sel){
        if(sel==='.row-num,.row-no')return number;
        return null;
    }};
    Object.defineProperty(item,'nextSibling',{get(){return body.rows[body.rows.indexOf(item)+1]||null;}});
    return item;
}
const original=[row(1,'BOX10',10),row(2,'BOX2',2),row(3,'BOX1',1)];
const summary={dataset:{},classList:classes(),cells:[{colSpan:6}],textContent:'TOTAL 13'};
const body={rows:[...original,summary],insertBefore(item,anchor){this.rows.splice(this.rows.indexOf(item),1);const idx=anchor?this.rows.indexOf(anchor):this.rows.length;this.rows.splice(idx,0,item);}};
const table={dataset:{},tHead:{rows:[head]},tBodies:[body],events:{},addEventListener(k,fn){this.events[k]=fn;}};
let observed;
const context=vm.createContext({Intl,Number,Array,Map,Set,String,document:{createElement:()=>({setAttribute(){}})},
    MutationObserver:class{constructor(fn){observed=fn;}observe(target,options){assert.equal(target,body);assert.equal(options.childList,true);assert.equal(options.subtree,undefined);}},setTimeout:fn=>fn()});
vm.runInContext(code,context);context.setupDetailRowSorting?.(table);
const trigger=(index,event='click',target)=>{const h=headers.find(x=>x.textContent===labels[index]);(h.events[event]||[]).forEach(fn=>fn({target:target|| (event==='keydown'?h:{closest:()=>null}),key:event==='keydown'?'Enter':undefined,preventDefault(){}}));};
const ids=()=>body.rows.filter(x=>x!==summary).map(x=>x.dataset.id);
const expected=['3','2','1'];
if(scenario==='natural'||scenario==='identity'||scenario==='unkeyed'){trigger(2);assert.deepEqual(ids(),expected);trigger(2);assert.deepEqual(ids(),['1','2','3']);}
else if(scenario==='numbers'){trigger(3);assert.deepEqual(ids(),expected);trigger(4);assert.deepEqual(ids(),expected);}
else if(scenario==='decimals'){original[0].cells[3].textContent='1.20';original[1].cells[3].textContent='1.03';original[2].cells[3].textContent='-0.05';trigger(3);assert.deepEqual(ids(),expected);original[0].cells[4].textContent='￥1,200.00';original[1].cells[4].textContent='￥20.50';original[2].cells[4].textContent='￥20.05';trigger(4);assert.deepEqual(ids(),expected);}
else if(scenario==='keyboard'){trigger(2,'keydown');assert.deepEqual(ids(),expected);}
else if(scenario==='reordered'){headers.reverse();body.rows.filter(x=>x!==summary).forEach(x=>x.cells.reverse());trigger(3);assert.deepEqual(ids(),expected);}
else if(scenario==='live-input'){original[0].cells[3].input={value:'0.25'};trigger(3);assert.deepEqual(ids(),['1','3','2']);}
else if(scenario==='blank-last'){original[0].cells[3].textContent='-';trigger(3);assert.deepEqual(ids(),expected);trigger(3);assert.deepEqual(ids(),['2','3','1']);}
else if(scenario==='stable'){original[0].cells[3].textContent='2';trigger(3);assert.deepEqual(ids(),['3','1','2']);}
else if(scenario==='summary'){trigger(2);assert.deepEqual(ids(),expected);assert.equal(body.rows.at(-1),summary);assert.equal(summary.textContent,'TOTAL 13');}
else if(scenario==='dynamic'){trigger(2);const added=row(4,'BOX0',0);body.rows.splice(body.rows.length-1,0,added);observed?.();assert.deepEqual(ids(),['4','3','2','1']);observed?.();assert.deepEqual(ids(),['4','3','2','1']);}
else if(scenario==='resize'){trigger(2,'click',{closest:()=>({})});assert.deepEqual(ids(),['1','2','3']);trigger(2);assert.deepEqual(ids(),expected);}
else if(scenario==='idempotent'){context.setupDetailRowSorting?.(table);trigger(2);assert.deepEqual(ids(),expected);}
else throw Error('Unknown scenario '+scenario);
for(const item of original){assert(body.rows.includes(item));assert.equal(item.dataset.index,String(10+Number(item.dataset.id)));assert.equal(item.checkbox.value,'item-'+item.dataset.id);assert.equal(item.checkbox.checked,item.dataset.id==='2');}
assert.equal(body.rows.at(-1),summary);
assert.equal(headers.find(h=>h.textContent==='序号').events.click,undefined);
assert.equal(headers.find(h=>h.textContent==='操作').events.click,undefined);
