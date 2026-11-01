// Execute the real page script against a small DOM fixture, with no browser/network.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const script = process.argv[2], mode = process.argv[3], nodes = new Map(), calls = [], pending = [];
function element() {
  return {checked:false, value:'', disabled:false, hidden:false, dataset:{}, children:[], events:{},
    addEventListener(name, fn){this.events[name]=fn;}, replaceChildren(){this.children=[];},
    appendChild(child){this.children.push(child);}, querySelectorAll(){return [];}, focus(){}};
}
const document = {getElementById(id){if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);},createElement:element};
const source = {id:2,code:'QA-S',name:'same',spec:'',brand:'',unit:'piece',stock:0,status:'active'};
const target = {id:1,code:'QA-T',name:'same',spec:'',brand:'',unit:'piece',stock:0,status:'active'};
function plan(t, token){return {source,target:t,stock_after:0,tables:{},total_rows:0,...(token?{preview_token:token}:{})};}
const WMS = {api:{getRaw:async()=>({status:'success',data:[],page:1,total_pages:0,total:0}),
  postRaw(url,payload){
    if(url==='/material/merge_preview') {
      if(mode==='late-preview')return new Promise(resolve=>pending.push(resolve));
      return Promise.resolve({status:'success',data:plan(target,mode==='no-receipt'?null:'SIGNED-QA-RECEIPT')});
    }
    calls.push({url,payload});return Promise.resolve({status:'error',msg:'QA_STOP_WITHOUT_MERGE'});
  }}};
vm.runInNewContext(fs.readFileSync(script,'utf8'),{document,WMS,bootstrap:{Modal:{getOrCreateInstance(){return {show(){}};}}},
    URLSearchParams,showToast(){},window:{location:{reload(){throw new Error('No successful merge is allowed in this fixture');}}}});
(async()=>{
  WMS.MaterialMerge.open(source,target);
  if(mode==='late-preview'){
    const second={...target,id:3,code:'QA-T2'};
    WMS.MaterialMerge.open(source,second);
    pending[1]({status:'success',data:plan(second,'SIGNED-NEW-RECEIPT')});
    await new Promise(setImmediate);
    pending[0]({status:'success',data:plan(target,'SIGNED-STALE-RECEIPT')});
  }
  await new Promise(setImmediate);
  const checkbox=document.getElementById('mergeHumanConfirmed');checkbox.checked=true;checkbox.events.change();
  const button=document.getElementById('mergeExecuteBtn');
  assert.equal(button.disabled,mode==='no-receipt');
  button.events.click();await new Promise(setImmediate);
  if(mode==='no-receipt')assert.equal(calls.length,0);
  else {
    assert.equal(calls.length,1);
    assert.equal(calls[0].payload.preview_token,mode==='late-preview'?'SIGNED-NEW-RECEIPT':'SIGNED-QA-RECEIPT');
    assert.equal(calls[0].payload.target_code,mode==='late-preview'?'QA-T2':'QA-T');
    assert.equal(document.getElementById('mergeHumanConfirmed').checked,false);
  }
  process.stdout.write(JSON.stringify({mode,passed:true,actual_merges:0,network_requests:0}));
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
