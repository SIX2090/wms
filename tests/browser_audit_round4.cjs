const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const root=path.resolve(__dirname,'..');
const read=p=>fs.readFileSync(path.join(root,p),'utf8');
const scenario=process.argv[2];
const mobile=read('app/templates/mobile_scan.html');
const element=()=>({value:'',dataset:{},hidden:false,events:{},addEventListener(k,f){this.events[k]=f;},focus(){},select(){}});
(async()=>{
 if(scenario==='mobile-input'){
  const fields={scanCode:element(),lookupBtn:element(),materialCard:element(),matchList:element(),printLabelBtn:element()};
  const ctx={...fields,selectedMaterial:{code:'OLD'},lookupVersion:1,lookupMaterial(){}};
  const start=mobile.indexOf("    scanCode.addEventListener('input'");
  assert(start>=0,'typing must invalidate the selected material');
  vm.createContext(ctx);vm.runInContext(mobile.slice(start,mobile.indexOf("    if (printLabelBtn) printLabelBtn.addEventListener",start)),ctx);
  fields.scanCode.value='NEW';fields.scanCode.events.input();
  assert.equal(ctx.selectedMaterial,null);assert(ctx.materialCard.hidden);assert.equal(ctx.lookupVersion,2);return;
 }
 if(scenario==='check-initial'){
  const start=mobile.indexOf("    if (mode === 'check' && warehouseInput)");let requests=[];
  const ctx={mode:'check',warehouseInput:{value:'WH-A',addEventListener(){}},checkOrderSelect:element(),loadCheckOrders:wh=>requests.push(wh)};
  vm.runInNewContext(mobile.slice(start,mobile.indexOf("    scanForm.addEventListener",start)),ctx);
  assert.deepEqual(requests,['WH-A']);return;
 }
 if(scenario.startsWith('batch-')){
  const contract=scenario==='batch-contract';
  const src=read(contract?'app/templates/contract.html':'app/static/js/pages/employee.js');
  const template=read(contract?'app/templates/contract.html':'app/templates/employee.html');
  const name=(template.match(/onclick="(\w+)\(\)"[^>]*>\s*<i class="bi bi-trash/)||[])[1];
  assert(name,'batch delete button');
  const begin=src.indexOf((contract?'function ':'async function ')+name+'(');
  const end=src.indexOf('\nfunction ',begin+1);
  const calls=[];
  const ctx={document:{querySelectorAll:()=>[{value:'7'},{value:'9'}]},showToast(){},confirm:()=>true,showConfirm:async()=>true,
   notifyMasterDataChanged(){},location:{reload(){}},setTimeout(){},WMS:{api:{postRaw:(url,body)=>{calls.push({url,body});return Promise.resolve({status:'success'});}}}};
  vm.createContext(ctx);vm.runInContext(src.slice(begin,end<0?undefined:end),ctx);
  // Simulate the later shared script definition exactly as on the real page.
  ctx.batchDelete=()=>{throw Error('generic helper replaced page handler');};
  await ctx[name]();await Promise.resolve();assert.equal(calls.length,1);assert.deepEqual(Array.from(calls[0].body.ids,Number),[7,9]);return;
 }
 if(scenario==='frozen-stock'){
  const src=read('app/templates/document_table_form.html');
  const a=src.indexOf('function rowCells('),b=src.indexOf('function createRow(',a);
  const ctx={readonly:false,docType:'check',unitOptions:()=>'',checkLocationRequired:false,hasCountedByCol:false};
  vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);
  const html=ctx.rowCells({system_stock:90});
  const stock=html.match(/<input[^>]*class="system-stock"[^>]*>/)[0];
  assert(/\breadonly\b/.test(stock));assert(!/readonly/.test(html.match(/<input[^>]*class="actual-stock"[^>]*>/)[0]));return;
 }
 if(scenario==='unknown-stock'){
  const src=read('app/templates/purchase_request_add.html');
  const a=src.indexOf('function selectMaterial('),b=src.indexOf('function bindSupplierInput(',a);
  const fields={};const row={querySelector:s=>fields[s]||(fields[s]=element())};
  const ctx={cancelMaterialSearch(){},getMaterialUnitName:()=>'',getMaterialUnitId:()=>'',updateRowAmount(){}};
  vm.createContext(ctx);vm.runInContext(src.slice(a,b),ctx);ctx.selectMaterial(row,{code:'M'});
  assert.equal(fields['.material-stock'].value,'未查询');ctx.selectMaterial(row,{code:'M',stock:0});assert.equal(fields['.material-stock'].value,'0.00');return;
 }
 throw Error(scenario);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
