'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const [root, scenario] = process.argv.slice(2);
const file = path.join(root, 'app/static/js/product-receipt-detail.js');
// The old page has no sort handler. Assert the observed row order in that case,
// rather than failing merely because a new file does not exist yet.
const source = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
const listeners = {};
const keys = ['seq','colBoxNo','colCode','colName','colQty','colAmount'];
function classes() {
    const value = new Set();
    return {add: (...args) => args.forEach(x => value.add(x)), remove: (...args) => args.forEach(x => value.delete(x)), contains: x => value.has(x)};
}
const headers = keys.map(key => ({dataset:{columnKey:key},attrs:{},style:{},classList:classes(),textContent:key,children:[],
    setAttribute(k,v) {this.attrs[k]=v;}, addEventListener(k,fn) {(this.events ||= {})[k]=fn;},
    appendChild(node) {this.children.push(node);}, querySelector(s) {return s === '.cb-sort-indicator' ? this.children[0] || null : null;}}));
function row(id, box, quantity) {
    const values = {seq:String(id),colBoxNo:box,colCode:'40000'+id,colName:'配电柜'+id,colQty:String(quantity),colAmount:'¥'+(quantity*10).toFixed(2)};
    const cells = keys.map(key => ({dataset:{columnKey:key},textContent:values[key],querySelector() {return this.input || null;}}));
    const number = {textContent:String(id)};
    return {dataset:{id:String(id)},classList:classes(),cells,querySelector(selector) {
        if (selector === '.row-num') return number;
        const match = /data-column-key="([^"]+)"/.exec(selector);
        return match ? cells.find(c => c.dataset.columnKey === match[1]) : null;
    }};
}
const original = [row(1,'PA03-LP10',10),row(2,'PA03-LP2',2),row(3,'PA03-LP1',1)];
const body = {rows:original.slice(),appendChild(item) {this.rows.splice(this.rows.indexOf(item),1);this.rows.push(item);},querySelectorAll() {return this.rows;}};
const footer = {textContent:'13.00',rows:[{cells:keys.map(k=>({dataset:{columnKey:k}}))}]};
const table = {dataset:{businessType:scenario === 'other-receipt' ? '采购入库' : '产品入库'},tBodies:[body],tHead:{rows:[{cells:headers}]},tFoot:footer,
    querySelector(selector) {return selector === 'tbody' ? body : null;},querySelectorAll() {return headers;}};
const document = {getElementById(id) {return id === 'itemTable' ? table : null;},
    addEventListener(event,fn) {listeners[event]=fn;},createElement() {return {setAttribute(){},className:'',textContent:''};}};
const context = vm.createContext({document,Intl,Number,Array,Map,Set,window:{}});
vm.runInContext(source,context);
listeners.DOMContentLoaded?.();
function click(key, target = {closest:()=>null}) {
    const header=headers.find(x=>x.dataset.columnKey===key);
    header.events?.click?.({target,preventDefault(){}});
}
const ids = () => body.rows.map(x=>x.dataset.id);
if (scenario === 'boxes') {
    click('colBoxNo');assert.deepEqual(ids(),['3','2','1']);
    assert.equal(headers[1].attrs['aria-sort'],'ascending');
    click('colBoxNo');assert.deepEqual(ids(),['1','2','3']);assert.equal(headers[1].attrs['aria-sort'],'descending');
} else if (scenario === 'quantities') {
    click('colQty');assert.deepEqual(ids(),['3','2','1']);
    click('colQty');assert.deepEqual(ids(),['1','2','3']);
    click('colAmount');assert.deepEqual(ids(),['3','2','1']);
} else if (scenario === 'reordered-columns') {
    headers.reverse();body.rows.forEach(x=>x.cells.reverse());
    click('colQty');assert.deepEqual(ids(),['3','2','1']);
    click('colBoxNo');assert.deepEqual(ids(),['3','2','1']);
} else if (scenario === 'live-input') {
    original[0].querySelector('[data-column-key="colQty"]').input={value:'0.50'};
    click('colQty');assert.deepEqual(ids(),['1','3','2']);
} else if (scenario === 'keyboard') {
    const h=headers.find(x=>x.dataset.columnKey==='colBoxNo');
    h.events?.keydown?.({key:'Enter',target:h,preventDefault(){}});
    assert.deepEqual(ids(),['3','2','1']);
    h.events?.keydown?.({key:' ',target:h,preventDefault(){}});
    assert.deepEqual(ids(),['1','2','3']);
} else if (scenario === 'resize') {
    const h=headers.find(x=>x.dataset.columnKey==='colBoxNo');
    assert.equal(typeof h.events?.click,'function');
    click('colBoxNo',{closest:()=>({className:'resize-handle'})});assert.deepEqual(ids(),['1','2','3']);
    click('colBoxNo');assert.deepEqual(ids(),['3','2','1']);
} else if (scenario === 'stable-and-new-row') {
    const added=row(4,'PA03-LP2',2);body.rows.push(added);
    click('colQty');assert.deepEqual(ids(),['3','2','4','1']);
    click('colQty');assert.deepEqual(ids(),['1','2','4','3']);
} else if (scenario === 'other-receipt') {
    assert.equal(headers.find(x=>x.dataset.columnKey==='colQty').events?.click,undefined);
    click('colQty');assert.deepEqual(ids(),['1','2','3']);
} else {throw Error('Unknown scenario '+scenario);}
assert.equal(footer.textContent,'13.00','sorting does not change totals');
for (const item of original) {
    assert(body.rows.includes(item),'keep the same row and its controls');
    assert.equal(item.querySelector('[data-column-key="colCode"]').textContent,'40000'+item.dataset.id);
    assert.equal(item.querySelector('[data-column-key="colName"]').textContent,'配电柜'+item.dataset.id);
}
