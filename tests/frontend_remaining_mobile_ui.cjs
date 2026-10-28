const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app/templates/mobile_scan.html'),'utf8').replace(/\r\n/g,'\n');
const scenario=process.argv[2],flush=()=>new Promise(r=>setImmediate(r));
function element(){return {value:'',hidden:false,disabled:false,textContent:'',children:[],dataset:{},events:{},
 classList:{contains:()=>false,add(){},remove(){},toggle(){}},focus(){},select(){},closest(){return null;},
 addEventListener(name,fn){this.events[name]=fn;},querySelectorAll(){return [];},
 appendChild(el){this.children.push(el);el.parentNode=this;},removeChild(el){this.children=this.children.filter(x=>x!==el);el.parentNode=null;},
 insertAdjacentHTML(pos,html){this.html+=html;},set innerHTML(html){this.html=html;this.children=[];},get innerHTML(){return this.html||'';}};}
const scripts=Array.from(source.matchAll(/<script>([\s\S]*?)<\/script>/g),m=>m[1]);
(async()=>{
 if(scenario==='confirm-init'){
  const context={document:{querySelector:()=>({dataset:{mode:'confirm'}}),getElementById:()=>null},window:{addEventListener(){},setTimeout(){}},navigator:{},WMS:{api:{}}};
  vm.runInNewContext(scripts[0],context); return;
 }
 if(['confirm-loading','confirm-switch','more-switch'].includes(scenario)){
  const list=element(),refresh=element(),wh=element(),panel=element();wh.value='A';
  const fields={confirmPanel:panel,confirmList:list,confirmRefreshBtn:refresh,confirmWarehouseSelect:wh};
  let requests=[];
  const context={document:{getElementById:id=>fields[id]||null,createElement:element},window:{},WMS:{api:{getRaw:url=>new Promise(resolve=>requests.push({url,resolve}))}}};
  const answer=(start,name,pages=1)=>requests.slice(start,start+2).forEach(r=>r.resolve({status:'success',data:{items:[{id:1,order_no:name}],total:pages,total_pages:pages}}));
  vm.runInNewContext(scripts[1],context);
  if(scenario==='confirm-switch'){
   wh.value='B';wh.events.change();answer(2,'WB');await flush();await flush();answer(0,'WA');await flush();await flush();
   assert(list.innerHTML.includes('WB'));assert(!list.innerHTML.includes('WA'));return;
  }
  answer(0,'QA',scenario==='more-switch'?2:1);await flush();await flush();
  assert(!list.innerHTML.includes('加载中'),'loaded cards must replace the initial loading message');
  assert(list.innerHTML.includes('QA'));
  if(scenario==='more-switch'){
   list.children[0].children[0].events.click();
   wh.value='B';wh.events.change();answer(4,'WB');await flush();await flush();answer(2,'OLD-PAGE');await flush();await flush();
   assert(list.innerHTML.includes('WB'));assert(!list.innerHTML.includes('OLD-PAGE'));
  }
  return;
 }
 if(scenario==='recognize-match'){
  const a=source.indexOf('            if (data.matches &&'),b=source.indexOf('\n        })\n        .catch',a);
  let lookups=0;const context={scanCode:{value:''},setStatus(){},renderMaterial(){throw Error('AI metadata must not render global stock');},lookupMaterial(){lookups++;}};
  vm.runInNewContext('function consume(data){'+source.slice(a,b)+'}\nconsume({matches:[{code:"M",stock:999}]});',context);
  assert.equal(lookups,1);assert.equal(context.scanCode.value,'M');return;
 }
 if(scenario==='query-submit-switch'){
  const fields={scanCode:element(),scanForm:element(),submitBtn:element(),warehouseInput:element(),quantityInput:element()};fields.warehouseInput.value='A';
  let resolve,rendered=[];
  const context={shell:{dataset:{mode:'query',canWrite:'1'}},document:{getElementById:id=>fields[id]||null},Promise,
   setStatus(){},lookupMaterial:()=>Promise.resolve(null),newRequestId:()=> 'QA',renderMaterial:m=>rendered.push(m),addHistory(){},resetForNextScan(){},
   WMS:{api:{postRaw:()=>new Promise(r=>resolve=r)}}};
  const a=source.indexOf('    var mode = shell.dataset.mode'),b=source.indexOf('    function newRequestId');
  const c=source.indexOf("    scanForm.addEventListener('submit'"),d=source.indexOf('    var cameraBtn =',c);
  vm.createContext(context);vm.runInContext(source.slice(a,b),context);context.selectedMaterial={code:'M'};
  vm.runInContext(source.slice(c,d),context);fields.scanForm.events.submit({preventDefault(){}});await flush();
  fields.warehouseInput.value='B';resolve({status:'success',data:{material:{code:'M',stock:7}}});await flush();await flush();
  assert.equal(rendered.length,0,'query submit result from the old warehouse must not render');assert.equal(fields.submitBtn.disabled,false);return;
 }
 const a=source.indexOf('    function lookupMaterial()'),b=source.indexOf('    function stopBarcodeScanner()',a);
 const fields={warehouseInput:element(),scanCode:element(),matchList:element(),materialCard:element(),printLabelBtn:element()};
 fields.warehouseInput.value='A';fields.scanCode.value='M';
 let rendered=[],pending=[],status=[];
 const context={...fields,lookupVersion:0,selectedMaterial:null,mode:'query',quantityInput:element(),
  setStatus:(m)=>status.push(m),renderMaterial:m=>rendered.push(m),renderMatches(){},
  WMS:{api:{getRaw:url=>new Promise((resolve,reject)=>pending.push({url,resolve,reject}))}},Promise,encodeURIComponent};
 vm.createContext(context);vm.runInContext(source.slice(a,b),context);
 const first=context.lookupMaterial();
 if(scenario==='warehouse-change'){
  fields.warehouseInput.value='B';pending[0].resolve({status:'success',data:{code:'M',stock:7}});await first;
  assert.equal(rendered.length,0,'old warehouse response must not render after warehouse change');
 }else{
  const second=context.lookupMaterial();pending[1].resolve({status:'success',data:{code:'M',stock:9}});await second;
  pending[0].resolve({status:'success',data:{code:'M',stock:7}});await first;
  assert.deepEqual(rendered.map(m=>m.stock),[9],'older response must not overwrite latest lookup');
 }
 assert(pending[0].url.startsWith('/mobile/api/stock_lookup?'));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
