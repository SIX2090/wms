"""Whole opening-stock page and real HTTP unwrapping; all writes stay mocked in Node."""
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'app/static/js/pages/opening-stock.js'


class Nodes(HTMLParser):
    def __init__(self,text):
        super().__init__();self.nodes=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],timers=[],messages=[],events={};let ctx;
const decode=v=>String(v).replaceAll('&quot;','"').replaceAll('&#39;',"'").replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');
const attrs=text=>Object.fromEntries([...text.matchAll(/([\w-]+)="([^"]*)"/g)].map(m=>[m[1],decode(m[2])]));
class El{
 constructor(tag='div',a={}){this.tagName=tag.toUpperCase();this.attrs=a;this.id=a.id;this.value=a.value||'';this.style={};this.dataset={};this.children=[];this.events={};this.hidden=false;this.disabled=false;this.checked=false;this._html='';this._text='';this.isConnected=true;this.className=a.class||'';this.classList={add(){},remove(){},contains:()=>false};for(const[k,v]of Object.entries(a))if(k.startsWith('data-'))this.dataset[k.slice(5)]=v;}
 set innerHTML(html){this.children.forEach(n=>n.disconnect());this.children=[];this._html=String(html);this._text='';if(this.id==='openingGridBody')for(const match of this._html.matchAll(/<tr([^>]*)>([\s\S]*?)<\/tr>/g)){const row=new El('tr',attrs(match[1]));for(const input of match[2].matchAll(/<input([^>]*)>/g))row.appendChild(new El('input',attrs(input[1])));this.appendChild(row);}if(this.id==='materialMenu')for(const match of this._html.matchAll(/<div([^>]*)>([\s\S]*?)<\/div>/g)){const item=new El('div',attrs(match[1]));item._html=match[2];this.appendChild(item);}}
 get innerHTML(){return this._html;}set textContent(v){this._text=String(v??'');this._html='';this.children=[];}get textContent(){return this._text+this._html.replace(/<[^>]*>/g,'');}
 disconnect(){this.isConnected=false;this.children.forEach(n=>n.disconnect());}appendChild(n){this.children.push(n);n.parentNode=this;return n;}
 matches(s){const tag=(s.match(/^[a-z]+/)||[])[0];if(tag&&this.tagName!==tag.toUpperCase())return false;if(s.startsWith('.'))return this.className.split(' ').includes(s.slice(1));for(const attr of s.matchAll(/\[([\w-]+)="([^"]+)"\]/g))if(this.attrs[attr[1]]!==attr[2])return false;return true;}
 querySelectorAll(s){return this.children.flatMap(n=>[...(n.matches(s)?[n]:[]),...n.querySelectorAll(s)]);}querySelector(s){return this.querySelectorAll(s)[0]||null;}
 closest(s){if(s==='#materialMenu')return this.id==='materialMenu'?this:this.parentNode?.closest(s)||null;if(s==='.code-cell')return this.attrs['data-field']==='material_code'?this:null;return this.matches(s)?this:this.parentNode?.closest(s)||null;}
 addEventListener(type,fn){(this.events[type]??=[]).push(fn);}fire(type){if(this.attrs['on'+type]){ctx.__input=this;vm.runInContext('(function(){'+this.attrs['on'+type]+'}).call(__input)',ctx);}for(const fn of this.events[type]||[])fn({target:this,preventDefault(){}});}focus(){}getAttribute(k){return this.attrs[k]??null;}
}
const elements=new Map(p.nodes.filter(([,a])=>a.id).map(([tag,a])=>[a.id,new El(tag,a)]));
const el=id=>{assert(elements.has(id),'actual page node '+id);return elements.get(id);};
const document={getElementById:el,querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null,querySelectorAll:s=>s.includes('opening-row-check')?el('openingGridBody').querySelectorAll('.opening-row-check'):[],addEventListener:(type,fn)=>(events[type]??=[]).push(fn)};
const escape=s=>String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;');
ctx={document,Headers,FormData,console,showConfirm:async()=>true,escapeHtml:escape,location:{href:'/original',reload:()=>assert.fail('no real navigation')},__OPENING_DOC__:null,WMS:{positionDropdown(){}},setTimeout:(fn,delay)=>{const timer={fn,delay,done:false};timers.push(timer);return timers.length;},clearTimeout:id=>{if(timers[id-1])timers[id-1].done=true;},showToast:(message,type)=>messages.push({message,type}),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),localStorage:{getItem:()=>null,setItem(){},removeItem(){}},bootstrap:{Modal:{getInstance:()=>({hide(){}}),getOrCreateInstance:()=>({show(){}})}},fetch:(url,options)=>{calls.push({url,options,body:options.body?JSON.parse(options.body):undefined});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);
vm.runInContext('const LOCATION_ENABLED=false,GRID_COLSPAN=12,warehouseOptions=[{id:1,name:"WA"}],existingRows=[{material_id:"",material_code:"",material_name:"",quantity:"",price:"",warehouse_id:1},{material_id:"",material_code:"",material_name:"",quantity:"",price:"",warehouse_id:1}];',ctx);
vm.runInContext(p.source,ctx);el('headerWarehouse').value='1';el('headerDocDate').value='2026-10-23';el('pasteDocDate').value='2026-10-23';el('headerRemark').value='fixture head';for(const fn of events.DOMContentLoaded||[])fn();
const settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const material=(code='M001',id=1)=>({id,code,name:'material '+code,spec:'spec',unit:'件',stock:3,price:2.5});
const codeInput=index=>el('openingGridBody').children[index].querySelector('input[data-field="material_code"]');
const type=(index,value)=>{const input=codeInput(index);input.value=value;input.fire('input');return input;};
function searchTick(){const timer=timers.find(t=>!t.done&&t.delay===200);assert(timer,'search debounce');timer.done=true;timer.fn();}
function body(kind){if(kind==='search')return{status:'success',data:[material()],total:1,truncated:false};return{status:'success',data:{items:[material()],missing:[]}};}
async function finish(index,kind='search',scenario='success',custom){if(scenario==='network')pending[index].reject(Error('fixture offline'));else pending[index].resolve({ok:scenario!=='http_success',status:scenario==='http_success'?500:200,json:()=>Promise.resolve(scenario==='null'?null:scenario==='business'?{status:'error',msg:'fixture refusal'}:custom||body(kind))});await settle();}
const saves=()=>calls.filter(c=>c.url==='/opening_stock/save');
function paste(text='WA,M001,2,0,fixture row,2026-10-23'){el('pasteImportText').value=text;ctx.confirmPasteImport();}
(async()=>{
 if(p.action==='search'){
  type(0,'M001');searchTick();await settle();assert.equal(calls.length,1);assert(calls[0].url.includes('/api/material/search?keyword=M001'));
  if(p.scenario==='clear'){type(0,'');const before=el('materialMenu').innerHTML;await finish(0);assert.equal(el('materialMenu').innerHTML,before,'cleared input cannot be repopulated by old results');return;}
  if(p.scenario==='row'){type(1,'M002');searchTick();await settle();await finish(1,'search','success',{status:'success',data:[material('M002',2)]});const before=el('materialMenu').innerHTML;await finish(0);assert.equal(el('materialMenu').innerHTML,before,'old row response cannot replace active row menu');return;}
  if(p.scenario==='close'){for(const fn of events.click||[])fn({target:new El('div')});await finish(0);assert(el('materialMenu').hidden,'outside click stays closed');assert(!el('materialMenu').innerHTML.includes('onclick="selectMaterial'),'closed search must discard obsolete menu rows');return;}
  if(p.scenario==='render'){ctx.renderRows();await finish(0);assert(el('materialMenu').hidden,'re-rendered row detaches old search');assert(!el('materialMenu').innerHTML.includes('onclick="selectMaterial'));return;}
  await finish(0,'search',p.scenario);
  if(p.scenario!=='success'){assert(el('materialMenu').textContent.includes('失败'),'search failure is visible');return;}
  assert(el('materialMenu').innerHTML.includes('material M001'),'unwrapped search array must render actual results');const item=el('materialMenu').children.find(n=>n.attrs.onclick);assert(item);ctx.__item=item;vm.runInContext(item.attrs.onclick,ctx);const rows=vm.runInContext('rows',ctx);assert.equal(rows[0].material_id,1);assert.equal(rows[0].material_name,'material M001');assert.equal(rows[0].price,2.5);assert(el('openingGridBody').innerHTML.includes('material M001'));assert(el('materialMenu').hidden);return;
 }
 if(p.action==='clear_debounce'){type(0,'M001');type(0,'');for(const timer of timers.filter(t=>!t.done&&t.delay===200)){timer.done=true;timer.fn();}await settle();assert.equal(calls.length,0,'clearing keyword cancels pending debounce');return;}
 if(p.action==='cached'){type(0,'M001');searchTick();await finish(0);paste();await settle();assert.equal(calls.filter(c=>c.url==='/opening_stock/materials/lookup').length,0);assert.equal(saves().length,1,'search cache supplies paste parsing');return;}
 if(p.action==='large'){const text=Array.from({length:501},(_,i)=>'WA,C'+i+',1,0').join('\n');paste(text);await settle();assert.equal(calls[0].body.codes.length,500);await finish(0,'lookup','success',{status:'success',data:{items:calls[0].body.codes.map((code,i)=>material(code,i+1)),missing:[]}});assert.equal(saves().length,0,'500 is a chunk limit, not all matches');assert.equal(calls[1].body.codes.length,1);await finish(1,'lookup',p.scenario,{status:'success',data:{items:[material('C500',501)],missing:[]}});if(p.scenario==='success'){assert.equal(saves().length,1);assert.equal(saves()[0].body.items.length,501,'every requested code is resolved before save');}else{assert.equal(saves().length,0,'a later chunk failure cannot save a partial false-success result');assert(el('pasteImportFeedback').textContent.includes('失败'));}return;}
 if(p.action==='replacement_cancel'){
  vm.runInContext('rows=[{material_id:7,material_code:"OLD",warehouse_id:1,quantity:3,price:1}]',ctx);
  let prompted=0;ctx.showConfirm=async (message,options)=>{prompted++;assert.equal(options.okText,'替换明细并保存');assert(message.includes('替换'));assert(message.includes('回冲'));return false;};
  paste();await settle();await finish(0,'lookup');assert.equal(prompted,1);assert.equal(saves().length,0);assert(el('pasteImportFeedback').textContent.includes('已取消'));return;
 }
 if(p.action==='dedupe'){paste('WA, m001 ,2,0\nWA,M001,3,0');await settle();assert.equal(calls[0].body.codes.length,1,'normalized duplicate codes are looked up once');assert.equal(calls[0].body.codes[0].trim().toLowerCase(),'m001');await finish(0,'lookup');assert.equal(saves().length,1);assert.equal(saves()[0].body.items.length,2);return;}
 if(p.action==='missing'){paste('WA,M001,2,0\nWA,NOPE,3,0');await settle();await finish(0,'lookup','success',{status:'success',data:{items:[material()],missing:['NOPE']}});assert.equal(saves().length,1,'known rows remain eligible under the existing partial-import policy');assert.equal(saves()[0].body.items.length,1);await finish(1,'save','success',{status:'success',doc_id:77,msg:'fixture save'});assert(messages.some(m=>m.message.includes('1 行被跳过')),'partial success explicitly reports skipped rows');return;}
 if(p.action==='bad_shape'){paste();await settle();await finish(0,'lookup','success',{status:'success',data:{items:{unexpected:true},missing:[]}});assert.equal(saves().length,0,'malformed items must not become a false empty lookup success');assert(el('pasteImportFeedback').textContent.includes('失败'));return;}
 paste();await settle();assert.equal(calls.length,1);assert.equal(calls[0].url,'/opening_stock/materials/lookup');assert.deepEqual(calls[0].body,{codes:['M001']});assert.equal(calls[0].options.headers['X-CSRFToken'],'fixture-token');
 if(p.action==='changed'){
  if(p.scenario==='text'){el('pasteImportText').value='WA,M002,3,1';el('pasteImportText').fire('input');}
  if(p.scenario==='date'){el('pasteDocDate').value='2026-10-24';el('pasteDocDate').fire('input');el('pasteDocDate').fire('change');}
  if(p.scenario==='header_date'){el('headerDocDate').value='2026-10-25';el('headerDocDate').fire('input');el('headerDocDate').fire('change');}
  if(p.scenario==='warehouse'){el('headerWarehouse').value='2';el('headerWarehouse').fire('change');}
  if(p.scenario==='remark'){el('headerRemark').value='changed';el('headerRemark').fire('input');}
  if(p.scenario==='hide'){el('pasteImportModal').fire('hide.bs.modal');el('pasteImportModal').fire('hidden.bs.modal');}
  await finish(0,'lookup');assert.equal(saves().length,0,'changed paste context invalidates prior lookup');assert(el('pasteImportFeedback').textContent.includes('重新')||el('pasteImportFeedback').textContent.includes('变化'));return;
 }
 await finish(0,'lookup',p.scenario);
 if(p.scenario==='success'){assert.equal(saves().length,1,'unwrapped lookup items must reach the actual paste/save chain');const payload=saves()[0].body;assert.deepEqual(payload.items,[{material_id:1,warehouse_id:1,quantity:2,price:0,remark:'fixture row',date:'2026-10-23'}]);assert.equal(payload.warehouse_id,'1');assert.equal(payload.remark,'fixture head');}
 else{assert.equal(saves().length,0);assert(el('pasteImportFeedback').textContent.includes('失败'));}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(action,scenario='success',source_override=None):
    node=shutil.which('node');assert node,'Node required for real lookup consumers'
    payload=dict(action=action,scenario=scenario,source=source_override or SOURCE.read_text(encoding='utf-8'),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),nodes=Nodes((ROOT/'app/templates/opening_stock.html').read_text(encoding='utf-8')).nodes)
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('scenario',['success','clear','row','close','render','network','http_success','null'])
def test_real_search_results_select_cache_and_ignore_obsolete_row_context(scenario):
    run('search',scenario)


def test_empty_keyword_cancels_pending_search_debounce():
    run('clear_debounce')


def test_selected_search_cache_preheats_paste_without_another_lookup():
    run('cached')


@pytest.mark.parametrize('scenario',['success','network','null'])
def test_real_lookup_unwraps_items_before_paste_and_keeps_failure_visible(scenario):
    run('paste',scenario)


@pytest.mark.parametrize('scenario',['success','network'])
def test_501_material_codes_are_fully_resolved_in_bounded_chunks_before_save(scenario):
    run('large',scenario)


@pytest.mark.parametrize('scenario',['text','date','header_date','warehouse','remark','hide'])
def test_waiting_lookup_never_saves_old_text_with_changed_header_or_closed_modal(scenario):
    run('changed',scenario)


def test_lookup_normalizes_and_deduplicates_codes_before_chunking():
    run('dedupe')


def test_explicit_missing_codes_keep_existing_partial_import_and_skip_feedback():
    run('missing')


def test_success_envelope_with_invalid_items_never_saves():
    run('bad_shape')


def test_existing_opening_rows_require_confirmation_and_cancel_keeps_inventory_untouched():
    run('replacement_cancel')
