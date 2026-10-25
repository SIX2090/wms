const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const source = fs.readFileSync(path.join(__dirname, '../app/templates/subcontract_detail.html'), 'utf8');
const cases = ['readonly', 'initial', 'zero', 'switch', 'input', 'clear', 'unknown', 'blur', 'change', 'enter', 'copy', 'copy_existing', 'empty_new', 'save'];
function execute(scenario) {
  const materials = [{code:'A', name:'Alpha', unit:'piece', price:12}, {code:'B', name:'Beta', unit:'box', price:5}, {code:'Z', name:'Zero', unit:'piece', price:0}];
  function field(value='') {
    let current = String(value);
    return {get value(){return current;}, set value(v){current=String(v);}, handlers:{}, focus(){}, select(){},
      addEventListener(type, fn){this.handlers[type]=fn;}, fire(type, extra={}){this.handlers[type]?.call(this, {key:'', preventDefault(){}, ...extra});}};
  }
  function makeRow() {
    const cells={};
    return {dataset:{}, cells, nextElementSibling:null, remove(){},
      set innerHTML(html){
        for (const match of html.matchAll(/<input\b([^>]*)>/g)) {
          const attrs=match[1], classes=/class="([^"]*)"/.exec(attrs)?.[1] || '';
          const item=field(/value="([^"]*)"/.exec(attrs)?.[1] || '');
          item.readOnly=/\breadonly\b/.test(attrs); item.title=/title="([^"]*)"/.exec(attrs)?.[1] || '';
          classes.split(/\s+/).forEach(cls=>cells['.'+cls]=item);
        }
      }, querySelector(sel){return cells[sel] || (cells[sel]=field());}};
  }
  const body={rows:[], appendChild(row){this.rows.push(row);},insertBefore(row){this.rows.push(row);}};
  let payload;
  const context={document:{getElementById(){return body;},createElement:makeRow}, clearProductEmptyRow(){},renumberProductRows(){},
    escapeHtml(v){return v == null ? '' : String(v);}, FormData,showToast(){},setTimeout(){},
    WMS:{api:{postRaw(url,data){payload=Object.fromEntries(data);return Promise.resolve({status:'success'});}}}};
  vm.createContext(context);
  vm.runInContext('const subcontractMaterials = '+JSON.stringify(materials)+';', context);
  for (const name of ['getMaterialUnit','findSubcontractMaterial','calcInlineProductAmount','fillInlineProductMaterial','addInlineProductRow','bindInlineProductRow','readProductRowData','saveInlineProductRow']) {
    const start=source.indexOf('function '+name+'('), next=source.indexOf('\nfunction ',start+1);
    let fn=source.slice(start,next<0?source.length:next);
    // The template has lifecycle registration between these declarations.
    const end=fn.indexOf('\n}\n'); if(end>=0) fn=fn.slice(0,end+3);
    fn=fn.replace(/{{\s*\(order.status == 'pending'\)\|tojson\s*}}/g,'true');
    vm.runInContext(fn,context);
  }
  const row=context.addInlineProductRow(null,{code:'A', name:'stale', quantity:2, price:99});
  const get=name=>row.querySelector('.inline-product-'+name);
  if(scenario==='readonly'){assert(get('price').readOnly);assert(get('price').title.includes('物料档案'));}
  if(scenario==='initial'){assert.equal(get('price').value,'12');assert.equal(get('amount').value,'24.00');}
  if(scenario==='zero'){context.fillInlineProductMaterial(row,materials[2]);assert.equal(get('price').value,'0');assert.equal(get('amount').value,'0.00');}
  if(scenario==='switch'){context.fillInlineProductMaterial(row,materials[1]);assert.equal(get('price').value,'5');assert.equal(get('amount').value,'10.00');}
  if(['input','clear','unknown','blur','change','enter'].includes(scenario)) {
    get('code').value=scenario==='clear'?'':scenario==='unknown'?'NO-SUCH-MATERIAL':'B';
    get('code').fire(scenario==='enter'?'keydown':scenario==='blur'?'blur':scenario==='change'?'change':'input',{key:'Enter'});
    const empty=scenario==='clear'||scenario==='unknown';
    assert.equal(get('price').value,empty?'':'5');assert.equal(get('name').value,empty?'':'Beta');
    assert.equal(get('amount').value,empty?'':'10.00');
  }
  if(scenario==='copy'){
    const copy=context.addInlineProductRow(null,context.readProductRowData(row));
    context.fillInlineProductMaterial(copy,materials[2]);
    assert.equal(copy.querySelector('.inline-product-price').value,'0');assert.equal(get('price').value,'12');
  }
  if(scenario==='copy_existing'){
    const cells={'.product-code-cell':'A','.product-name-cell':'Alpha','.product-unit-cell':'piece','.product-qty-cell':'2.00','.product-price-cell':'¥99.00'};
    const existing={querySelector(sel){return Object.hasOwn(cells,sel)?{textContent:cells[sel]}:null;}};
    const copy=context.addInlineProductRow(null,context.readProductRowData(existing));
    assert.equal(copy.querySelector('.inline-product-price').value,'12');
    assert.equal(copy.querySelector('.inline-product-amount').value,'24.00');
    assert.equal(cells['.product-price-cell'],'¥99.00');
  }
  if(scenario==='empty_new'){
    const empty=context.addInlineProductRow();
    assert.equal(empty.querySelector('.inline-product-price').value,'');
    assert.equal(empty.querySelector('.inline-product-amount').value,'');
  }
  if(scenario==='save'){
    context.saveInlineProductRow(row);assert.equal(payload.material_code,'A');assert.equal(payload.quantity,'2');
    assert(!Object.hasOwn(payload,'price'));assert.equal(get('amount').value,(2*materials[0].price).toFixed(2));
  }
}
let failed=0;
for(const scenario of process.argv[2]?[process.argv[2]]:cases){try{execute(scenario);console.log('PASS '+scenario);}catch(error){failed++;console.error('FAIL '+scenario+': '+error.message);}}
process.exitCode=failed?1:0;
