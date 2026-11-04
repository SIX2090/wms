'use strict';
// Execute both actual page scripts and api.js. DOM, network and FormData are isolated.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = process.argv[2];
const units = [{id:1,name:'个',code:'PCS'},{id:2,name:'千克',code:'KG'},{id:3,name:'同名',code:'X'},{id:4,name:'同名',code:'Y'}];
const suppliers = [{id:11,name:'供应商A',code:'SA'},{id:22,name:'供应商B',code:'SB'},{id:33,name:'同名供应商',code:'SC'},{id:44,name:'同名供应商',code:'SD'}];
const materials = [{id:101,code:'A001',name:'轴承A',spec:'A型',unit:{id:1,name:'个'},stock:42,price:8},{id:202,code:'B002',name:'轴承B',spec:'B型',unit:{id:2,name:'千克'},stock:99,price:6},{id:303,code:'C003',name:'重名',unit:'个'},{id:404,code:'D004',name:'重名',unit:'个'}];
function fixture(page) {
    const nodes = new Map(), calls = [], notices = [], timers = new Map(), rows = [];
    let counter = 0;
    class Element {
        constructor(id='') { this.id=id; this.value=''; this.dataset={}; this.style={display:'none'}; this.listeners={}; this.children=[]; this.textContent=''; this.isConnected=true; this.classList={toggle(){}}; }
        addEventListener(type,fn) { (this.listeners[type] ||= []).push(fn); }
        dispatch(type,extra={}) { const e={type,target:this,preventDefault(){this.defaultPrevented=true;},...extra}; for(const fn of this.listeners[type] || []) fn.call(this,e); return e; }
        dispatchEvent(event) { return this.dispatch(event.type,event); }
        focus() { document.activeElement=this; }
        select() {}
        click() { this.dispatch('click'); }
        remove() { this.isConnected=false; nodes.delete(this.id); }
        appendChild(child) { this.children.push(child); }
        querySelector(selector) { if(selector==='span:first-child') return {textContent:this.label}; return this.fields?.[selector] || null; }
        querySelectorAll(selector) { return selector.includes('dropdown-item') ? this.children : []; }
        getAttribute() { return null; }
        setAttribute() {}
        removeAttribute() {}
        scrollIntoView() {}
        set innerHTML(html) {
            this.html=html; this.children=[];
            for(const match of html.matchAll(/<div class="dropdown-item" data-id="([^"]+)"[^>]*>\s*<span[^>]*>([^<]*)<\/span>/g)) {
                const item=new Element(); item.dataset.id=match[1]; item.label=match[2]; this.children.push(item);
            }
            for(const match of html.matchAll(/\bid="([^"]+)"/g)) if(!nodes.has(match[1])) nodes.set(match[1],new Element(match[1]));
        }
        get innerHTML() { return this.html || ''; }
    }
    const document={activeElement:null,body:new Element('body'),getElementById(id){if(!nodes.has(id)) nodes.set(id,new Element(id));return nodes.get(id);},querySelector(){return null;},querySelectorAll(selector){return selector==='#materialTableBody tr'?rows:[];},createElement(){return new Element();},addEventListener(){}};
    class FD {
        constructor(form) { this.values=form.id==='addMaterialForm'?{unit_id:String(document.getElementById('unitIdHidden').value),supplier_id:String(document.getElementById('supplierIdHidden').value)}:form.values||{}; }
        get(name) { return this.values[name] ?? null; }
    }
    const context={document,FormData:FD,Event:class{constructor(type){this.type=type;}},showToast(...args){notices.push(args);},escapeHtml(value){return String(value??'');},alert(){},console,Promise,setTimeout(fn){const id=++counter;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);},fetch(url,options){calls.push({url,options}); return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(url==='/unit/add'?{status:'success',id:55,name:'箱'}:{status:'error',msg:'fixture stopped after payload'})});},location:{href:''},getComputedStyle(){return {};}};
    context.window=context; context.WMS={positionDropdown(){}};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(root+'/app/static/js/api.js','utf8'),context);
    const source=fs.readFileSync(root+'/app/templates/'+page+'.html','utf8');
    const script=source.slice(source.indexOf('<script>')+8,source.lastIndexOf('</script>'))
        .replace('const units = {{ units|tojson }};','const units = '+JSON.stringify(units)+';')
        .replace('const suppliers = {{ suppliers|tojson }};','const suppliers = '+JSON.stringify(suppliers)+';')
        .replace('const materials = {{ materials|tojson }};','const materials = '+JSON.stringify(materials)+';')
        .replace('const initialItems = {{ initial_items|default([])|tojson }};','const initialItems = [];');
    vm.runInContext(script,context);
    function row() { const r=new Element(); r.fields={}; for(const key of ['material-code','material-dropdown','material-name','spec','unit-name','material-stock','quantity','estimated-price','estimated-amount','supplier-id','supplier-name','supplier-dropdown','supplier-select-btn']) r.fields['.'+key]=new Element(); rows.push(r);context.bindMaterialInput(r);return r; }
    function type(id,value) { const el=document.getElementById(id);el.value=value;el.dispatch('input'); }
    async function settle(){for(let i=0;i<18;i++) await Promise.resolve();}
    return {context,document,calls,notices,row,type,settle,get:id=>document.getElementById(id)};
}
const cases=[];
function test(name,run){cases.push({name,run});}
function seedPurchase(f) { const r=f.row();f.context.fillRowData(r,{material_id:101,material_code:'A001',material_name:'轴承A',spec:'A型',unit_id:1,unit:'个',quantity:3,estimated_price:8,supplier_id:11,supplier_name:'供应商A'});return r; }
for(const value of ['UNKNOWN','']) test('purchase-input-invalidates-'+(value||'empty'),()=>{
    const f=fixture('purchase_request_add'),r=seedPurchase(f),code=r.querySelector('.material-code');code.value=value;code.dispatch('input');
    assert.equal(code.dataset.materialId,'','old material identity cleared');
    for(const selector of ['.material-name','.spec','.unit-name','.material-stock']) assert.equal(r.querySelector(selector).value,'','derived display cleared '+selector);
    assert.equal(r.querySelector('.unit-name').dataset.unitId,'');assert.equal(r.querySelector('.quantity').value,3);assert.equal(r.querySelector('.estimated-price').value,8);assert.equal(r.querySelector('.supplier-name').value,'供应商A');
});
test('purchase-submit-rejects-unmatched-text',()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f);r.querySelector('.material-code').value='UNKNOWN';r.querySelector('.material-code').dispatch('input');f.context.submitForm();assert.equal(f.calls.length,0);assert.match(f.notices.at(-1)[0],/物料|选择/);});
test('purchase-submit-rejects-programmatic-stale-id',()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f);r.querySelector('.material-code').value='B002';f.context.submitForm();assert.equal(f.calls.length,0);assert.match(f.notices.at(-1)[0],/物料|选择/);});
test('purchase-exact-code-selects-correct-material',()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f),code=r.querySelector('.material-code');code.value='B002';code.dispatch('input');const item=f.context.collectItems()[0];assert.equal(item.material_id,202);assert.equal(item.material_code,'B002');assert.equal(item.material_name,'轴承B');assert.equal(item.quantity,3);});
test('purchase-duplicate-name-does-not-auto-bind',()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f),code=r.querySelector('.material-code');code.value='重名';code.dispatch('input');assert.equal(code.dataset.materialId,'');f.context.submitForm();assert.equal(f.calls.length,0);assert.match(f.notices.at(-1)[0],/选择|多|物料/);});
test('purchase-manual-name-only-line-remains-supported',()=>{const f=fixture('purchase_request_add'),r=f.row();f.context.fillRowData(r,{material_name:'手工申请',spec:'待定',quantity:2,supplier_name:'手工供应商'});const item=f.context.collectItems()[0];assert.equal(item.material_id,null);assert.equal(item.material_name,'手工申请');assert.equal(item.supplier_name,'手工供应商');});
test('purchase-untouched-prefill-id-outside-cache-remains-supported',()=>{const f=fixture('purchase_request_add'),r=f.row();f.context.fillRowData(r,{material_id:909,material_code:'Z909',material_name:'缓存外物料',quantity:2});assert.equal(f.context.collectItems()[0].material_id,909);});
test('purchase-explicit-duplicate-selection-remains-supported',()=>{const f=fixture('purchase_request_add'),r=f.row();f.context.selectMaterial(r,materials[3]);assert.equal(f.context.collectItems()[0].material_id,404);});
test('purchase-save-sends-canonical-identity-and-keeps-manual-information',async()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f);f.context.submitForm();await f.settle();assert.equal(f.calls.length,1);const item=JSON.parse(f.calls[0].options.body).items[0];assert.equal(item.material_id,101);assert.equal(item.material_code,'A001');assert.equal(item.quantity,3);assert.equal(item.supplier_name,'供应商A');});
test('purchase-copy-retains-selected-identity-for-save',()=>{const f=fixture('purchase_request_add'),r=seedPurchase(f);let copied;f.context.addNewRow=()=>copied=f.row();f.context.copyRowAfter(r);const items=f.context.collectItems();assert.equal(items.length,2);assert.equal(items[1].material_id,101);assert.equal(items[1].material_code,'A001');assert.equal(items[1].quantity,3);assert.equal(copied.querySelector('.material-code').dataset.selectedMaterialCode,'A001');});
for(const field of ['unit','supplier']) {
    const input=field+'Search',hidden=field+'IdHidden',other=field==='unit'?'千克':'供应商B',expected=field==='unit'?'2':'22',old=field==='unit'?'1':'11';
    test('material-'+field+'-change-clears-old-id',()=>{const f=fixture('material_add');f.get(hidden).value=old;f.type(input,other);assert.equal(f.get(hidden).value,'');});
    test('material-'+field+'-save-resolves-unique-name',async()=>{const f=fixture('material_add');f.get(hidden).value=old;f.type(input,other);f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.body.values[field+'_id'],expected);});
    test('material-'+field+'-save-resolves-unique-code',async()=>{const f=fixture('material_add');f.type(input,field==='unit'?'kg':'sb');f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.body.values[field+'_id'],expected);});
    for(const value of ['不存在',field==='unit'?'千':'供应商',field==='unit'?'同名':'同名供应商']) test('material-'+field+'-rejects-'+value,()=>{const f=fixture('material_add');f.get(hidden).value=old;f.type(input,value);f.get('addMaterialForm').dispatch('submit');assert.equal(f.calls.length,0);assert.match(f.notices.at(-1)[0],/单位|供应商/);});
    test('material-'+field+'-blank-is-optional',async()=>{const f=fixture('material_add');f.get(hidden).value=old;f.type(input,'');f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.body.values[field+'_id'],'');});
    test('material-'+field+'-keyboard-selects-visible-choice',async()=>{const f=fixture('material_add');f.type(input,other);f.get(input).dispatch('keydown',{key:'ArrowDown'});const items=f.get(field+'Dropdown').children;assert.equal(items.length,1);items[0].style.backgroundColor='rgb(230, 247, 255)';f.get(input).dispatch('keydown',{key:'Enter'});assert.equal(f.get(hidden).value,expected);f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls[0].options.body.values[field+'_id'],expected);});
    test('material-'+field+'-explicit-ambiguous-selection-kept-on-focus',async()=>{const f=fixture('material_add');f.type(input,field==='unit'?'同名':'同名供应商');const dropdown=f.get(field+'Dropdown');dropdown.children[1].click();const chosen=f.get(hidden).value;f.get(input).dispatch('focus');assert.equal(f.get(hidden).value,chosen);f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.body.values[field+'_id'],chosen);});
    test('material-'+field+'-hidden-dropdown-enter-cannot-choose-old-result',()=>{const f=fixture('material_add');f.type(input,other);f.get(field+'Dropdown').children[0].style.backgroundColor='rgb(230, 247, 255)';f.type(input,'不存在');f.get(input).dispatch('keydown',{key:'Enter'});assert.equal(f.get(hidden).value,'');});
    test('material-'+field+'-save-checks-programmatic-text-change',async()=>{const f=fixture('material_add');f.get(hidden).value=old;f.get(input).value=other;f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.length,1);assert.equal(f.calls[0].options.body.values[field+'_id'],expected);});
    test('material-'+field+'-ime-enter-does-not-select',()=>{const f=fixture('material_add');f.type(input,other);f.get(field+'Dropdown').children[0].style.backgroundColor='rgb(230, 247, 255)';f.get(input).dispatch('keydown',{key:'Enter',isComposing:true});assert.equal(f.get(hidden).value,'');});
}
test('material-new-unit-selected-and-saved',async()=>{const f=fixture('material_add');f.context.showAddUnitModal();const modal=f.get('addUnitModal'),form=f.get('addUnitForm');form.values={code:'BOX',name:'箱'};form.dispatch('submit');await f.settle();assert.equal(modal.isConnected,false);assert.equal(f.get('unitSearch').value,'箱');assert.equal(f.get('unitIdHidden').value,55);f.get('addMaterialForm').dispatch('submit');await f.settle();assert.equal(f.calls.at(-1).options.body.values.unit_id,'55');});
(async()=>{const selected=process.argv[3]?cases.filter(c=>c.name===process.argv[3]||c.name.startsWith(process.argv[3])):cases;assert(selected.length);const results=[];for(const c of selected){try{await c.run();results.push({name:c.name,status:'passed'});}catch(error){results.push({name:c.name,status:'failed',message:error.message,stack:error.stack});}}console.log(JSON.stringify({total:results.length,passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').length,results},null,2));process.exitCode=results.some(r=>r.status==='failed')?1:0;})().catch(e=>{console.error(e);process.exitCode=2;});
