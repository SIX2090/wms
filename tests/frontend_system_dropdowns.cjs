'use strict';
const fs=require('fs'),vm=require('vm'),path=require('path'),assert=require('assert/strict');
const root=process.env.WMS_DROPDOWN_ROOT||path.resolve(__dirname,'..');
const source=n=>fs.readFileSync(path.join(root,'app/templates',n+'.html'),'utf8').replaceAll("{{ (order.warehouse or '')|tojson }}",JSON.stringify('fixture-warehouse'));
function fn(s,name){let start=s.indexOf('function '+name+'(');assert(start>=0,name);let open=s.indexOf(') {',start)+2,depth=0;for(let end=open;end<s.length;end++){depth+=(s[end]==='{')-(s[end]==='}');if(!depth)return s.slice(start,end+1);}throw Error(name);}
const cases=[];function test(name,body){cases.push([name,body]);}
const matches=Array.from({length:125},(_,i)=>({id:i+1,code:'WIRE-'+String(i+1).padStart(3,'0'),name:'电线',spec:'BV '+i,brand:'QA',stock:1,unit:'米',label:'电线'}));
const rows=matches.concat([{id:900,code:'OTHER',name:'其他',spec:'',brand:'',stock:0}]);
function node(){return {style:{},dataset:{},value:'电线',isConnected:true,innerHTML:'',listeners:{},children:[],classList:{add(){},remove(){},contains(){return false;}},
 querySelectorAll(){return [];},querySelector(){return null;},contains(target){return target===this;},getBoundingClientRect(){return {left:890,top:400,bottom:430,width:200};},
 addEventListener(n,f){this.listeners[n]=f;},setAttribute(){},appendChild(n){this.children.push(n);},insertAdjacentHTML(_,html){this.innerHTML+=html;},focus(){},select(){},closest(){return null;}};}
function context(){const input=node(),menu=node(),row=node();row.querySelector=s=>s.includes('dropdown')?menu:input;
 const c={materials:rows,customers:rows,suppliers:rows,subcontractMaterials:rows,readonly:false,activeDropdown:null,activeSupplierDropdown:null,
  document:{activeElement:input,querySelectorAll:()=>[row],getElementById:id=>/Dropdown|dropdown/.test(id)?menu:input,body:{appendChild(){}},createElement:()=>node()},
  WMS:{positionDropdown(i,m){assert.equal(i,input);assert.equal(m,menu);m.positioned=true;}},
  escapeHtml:v=>String(v??''),escapeAttr:v=>String(v??''),getMaterialUnit:m=>m.unit||'',formatQty:v=>String(v),formatStock:v=>String(v),
  materialSearchText:m=>[m.code,m.name,m.spec,m.brand].join(' ').toLowerCase(),supplierSearchText:s=>[s.code,s.name].join(' ').toLowerCase(),
  normalizeSearchValue:v=>String(v||'').trim().toLowerCase(),normalizeQuickText:v=>String(v||'').trim().toLowerCase(),
  quickSelectData:{supplier:rows},setTimeout(){return 1;},clearTimeout(){},console};
 c.window=c;vm.createContext(c);return {c,input,menu,row};}
for(const [page,name,attr] of [['adjustment_add','showDropdown','data-code'],['document_table_form','showDropdown','data-code'],['purchase_order_add','showMaterialDropdown','data-code'],['purchase_order_add','showSupplierDropdown','data-id'],['purchase_request_add','showSupplierDropdown','data-id'],['out_order_add','showDropdown','data-code'],['after_sale_out_add','showDropdown','data-code']]){
 for(const all of [false,true])test(page+'/'+name+'/'+all,()=>{const {c,menu,row}=context();vm.runInContext(fn(source(page),name),c);if(name==='showSupplierDropdown'&&page==='purchase_order_add'){c.findSupplierByName=()=>null;c.hideSupplierDropdown=()=>{};c[name](all);}else c[name](row,all);assert.equal((menu.innerHTML.match(new RegExp(attr+'=','g'))||[]).length,all?126:125);assert(menu.innerHTML.includes('WIRE-125'));assert.equal(menu.innerHTML.includes('OTHER'),all);});
}
for(const [page,name,args] of [['after_sale_out_add','filterCustomers',['电线']],['out_order_add','filterCustomers',['电线']],['subcontract_detail','filterSubcontractMaterials',['电线']],['material','filterQuickSelectItems',['supplier','电线']],['purchase_request_add','getMaterialMatches',['电线']]]){
 test(page+'/'+name+'/all matches',()=>{const {c}=context();vm.runInContext(fn(source(page),name),c);const result=c[name](...args);assert.equal(result.length,125);assert.equal(result.at(-1).code,'WIRE-125');assert.equal(new Set(result.map(x=>x.id)).size,125);});
}
test('material empty keyword keeps entire cached list',()=>{const {c}=context();vm.runInContext(fn(source('material'),'filterQuickSelectItems'),c);assert.equal(c.filterQuickSelectItems('supplier','').length,126);});
test('purchase request show all keeps ranking and last item',()=>{const {c}=context();vm.runInContext(fn(source('purchase_request_add'),'getMaterialMatches'),c);assert.equal(c.getMaterialMatches('',true).length,126);const hit=c.getMaterialMatches('WIRE-125');assert.equal(hit[0].code,'WIRE-125');});
test('purchase order choosing a late same-name candidate writes exact code',()=>{const {c,input,row}=context();let selected;Object.assign(c,{findMaterial:code=>rows.find(x=>x.code===code),fillMaterial:(_,m)=>selected=m.id,hideMaterialDropdown(){}});vm.runInContext(fn(source('purchase_order_add'),'selectMaterial'),c);c.selectMaterial(row,'WIRE-125');assert.equal(input.value,'WIRE-125');assert.equal(selected,125);});
for(const page of ['in_order_detail','out_order_detail'])test(page+' lookup renders all 100 returned candidates',async()=>{
 const {c,input,menu}=context();input.value='电线';Object.assign(c,{activeMaterialInput:input,materialLookupToken:0,materialLookupTimer:null,materialQuickResults:[],materialQuickActiveIndex:-1,
  getMaterialQuickDropdown:()=>menu,hideMaterialQuickDropdown(){menu.style.display='none';},setMaterialQuickActive(){},
  clearAddMaterialInfo(){},clearInlineMaterialInfo(){},fillAddMaterialInfo(){},fillInlineMaterialInfo(){}});
 c.WMS.api={getRaw:()=>Promise.resolve({status:'success',data:matches.slice(0,100),total:125,truncated:true})};
 vm.runInContext(fn(source(page),'renderMaterialQuickDropdown')+'\n'+fn(source(page),'lookupAddMaterial'),c);c.lookupAddMaterial();for(let i=0;i<4;i++)await new Promise(setImmediate);
 assert.equal((menu.innerHTML.match(/data-index=/g)||[]).length,100);assert(menu.innerHTML.includes('WIRE-100'));assert(menu.innerHTML.includes('100条'));assert.equal(menu.positioned,true);
});
test('AI recommendation local search reaches last material safely',()=>{
 const {c,input,menu}=context();c.allMaterials=rows;let search;
 const box={removeClass(){},empty(){menu.children=[];},html(s){menu.innerHTML=s;},append(n){menu.children.push(n);},addClass(){}};
 c.$=o=>o===input?{val:()=>input.value}:o==='#materialSearch'?{on:(_,f)=>search=f}:o==='#materialDropdown'?box:null;
 c.document.getElementById=()=>menu;c.selectMaterial=()=>{};
 const s=source('ai_location_recommendation');const start=s.indexOf("$('#materialSearch').on('input', function() {");const end=s.indexOf('// 点击外部关闭下拉',start);
 vm.runInContext(s.slice(start,end),c);search.call(input);assert.equal(menu.children.length,125);assert.equal(menu.children.at(-1).children[0].textContent,'WIRE-125');assert.equal(menu.positioned,true);
});
test('AI confirmation blank filter preserves all initial options',()=>{
 const {c}=context();const s=source('ai_document_confirm');const start=s.indexOf('    function searchMaterials(keyword, callback, seq) {');const end=s.indexOf('\n    function applyFilter()',start);
 c.filterSeq=0;c.filter={value:'',isConnected:true};c.initialOptions=new Map(rows.map(x=>[x.id,x]));vm.runInContext(s.slice(start,end),c);let data;c.searchMaterials('',x=>data=x);assert.equal(data.length,126);assert.equal(data.at(-1).id,900);
});
for(const [page,name,kind] of [['material_add','showUnitDropdown','unit'],['material_add','showSupplierDropdown','supplier'],['after_sale_out_add','showCustomerDropdown','customer']])test(page+'/'+kind+' viewport wiring',()=>{
 const {c,input,menu}=context();Object.assign(c,{unitSearch:input,unitDropdown:menu,supplierSearch:input,supplierDropdown:menu});vm.runInContext(fn(source(page),name),c);c[name](matches);assert.equal(menu.positioned,true);
});
test('subcontract modal empty keyword exposes entire pool inside viewport',()=>{
 const {c,input,menu}=context();input.value='';const s=source('subcontract_detail');
 vm.runInContext(['findSubcontractMaterial','filterSubcontractMaterials','bindScMaterialInput'].map(n=>fn(s,n)).join('\n'),c);
 c.bindScMaterialInput('input','dropdown',()=>{}).show();assert.equal((menu.innerHTML.match(/data-index=/g)||[]).length,126);assert.equal(menu.positioned,true);
});
test('shared contract picker stays inside a scrolled narrow window',async()=>{
 const {c,input}=context();let popup;
 Object.assign(c,{innerWidth:800,innerHeight:550,scrollY:300,addEventListener(){},getComputedStyle:()=>({minWidth:'320px'}),showToast(){}});
 c.document.listeners={};c.document.addEventListener=(n,f)=>c.document.listeners[n]=f;
 c.document.createElement=()=>{const n=node();n.querySelector=()=>node();n.remove=()=>{};return n;};
 c.document.head={appendChild(){}};c.document.body.appendChild=n=>popup=n;
 c.WMS.api={getContracts:()=>Promise.resolve({contracts:matches.map(m=>({contract_no:m.code,project_name:m.name}))})};
 vm.runInContext(fs.readFileSync(path.join(root,'app/static/js/dropdown-position.js'),'utf8'),c);
 const s=fs.readFileSync(path.join(root,'app/static/js/app.js'),'utf8');let start=s.indexOf('(function(global)',s.indexOf('// ==================== 合同编号 / 工程名称'));
 vm.runInContext(s.slice(start,s.indexOf('})(window);',start)+11),c);
 c.WMS.ContractAutocomplete.bind(input);input.listeners.focus();for(let i=0;i<4;i++)await new Promise(setImmediate);
 assert(popup);assert(parseFloat(popup.style.left)+parseFloat(popup.style.width)<=792);assert(parseFloat(popup.style.maxHeight)<=260);
 assert.equal(popup.style.top,'auto');assert.equal(popup.style.overscrollBehavior,'contain');
 const top=popup.style.top;c.document.listeners?.scroll?.({type:'scroll',target:popup});assert.equal(popup.style.top,top);
});
(async()=>{const results=[];for(const [name,body] of cases){try{await body();results.push({name,ok:true});}catch(e){results.push({name,ok:false,error:e.message,kind:e.name});}}process.stdout.write(JSON.stringify({passed:results.filter(x=>x.ok).length,failed:results.filter(x=>!x.ok).length,results},null,2));process.exitCode=results.some(x=>!x.ok)?1:0;})();
