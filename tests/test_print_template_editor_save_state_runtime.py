"""Whole editor script and actual API: acknowledge only the state sent to the server."""
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'app/static/js/pages/print-template-editor.js'


class Nodes(HTMLParser):
    def __init__(self,text):
        super().__init__();self.nodes=[];self.feed(text)
    def handle_starttag(self,tag,attrs):
        self.nodes.append((tag,dict(attrs)))


PROGRAM=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const calls=[],pending=[],events={};let document;
const encode=t=>String(t).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const decode=t=>String(t).replaceAll('&lt;','<').replaceAll('&gt;','>').replaceAll('&amp;','&');
class El{
 constructor(tag='div',attrs={}){this.tagName=tag.toUpperCase();this.id=attrs.id;this.attrs=attrs;this.dataset={};this.style={};this.children=[];this.events={};this._text='';this._html=null;this.className=attrs.class||'';this.value=attrs.value||'';this.disabled=false;for(const[k,v]of Object.entries(attrs))if(k.startsWith('data-'))this.dataset[k.slice(5)]=v;this.classList={add:c=>{if(!this.className.split(' ').includes(c))this.className+=' '+c;},remove:c=>this.className=this.className.split(' ').filter(n=>n!==c).join(' '),contains:c=>this.className.split(' ').includes(c),toggle:(c,on)=>on?this.classList.add(c):this.classList.remove(c)};}
 set innerHTML(html){this._html=String(html);this._text='';this.children=[];if(this.id==='gridTable')for(const match of this._html.matchAll(/<(td|th)([^>]*)>([\s\S]*?)<\/\1>/g)){const attrs={};for(const a of match[2].matchAll(/([\w-]+)="([^"]*)"/g))attrs[a[1]]=a[2];const child=new El(match[1],attrs);child.textContent=decode(match[3]);this.appendChild(child);}}
 get innerHTML(){return this._html===null?encode(this._text)+this.children.map(n=>n.innerHTML).join(''):this._html;}
 set textContent(text){this._text=String(text??'');this._html=null;this.children=[];}get textContent(){return this._text+(this._html||'').replace(/<[^>]*>/g,'')+this.children.map(n=>n.textContent).join('');}
 set innerText(text){this.textContent=text;}get innerText(){return this.textContent;}
 appendChild(n){n.parentNode=this;this.children.push(n);return n;}
 addEventListener(type,fn){(this.events[type]??=[]).push(fn);}fire(type,extra={}){for(const fn of this.events[type]||[])fn({target:this,button:0,preventDefault(){},...extra});}
 focus(){document.activeElement=this;}remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(n=>n!==this);}
 closest(selector){return this.matches(selector)?this:this.parentNode?.closest(selector)||null;}
 matches(selector){if(selector.startsWith('['))return Object.prototype.hasOwnProperty.call(this.attrs,selector.slice(1,-1));const tag=(selector.match(/^[a-z]+/)||[])[0];if(tag&&this.tagName!==tag.toUpperCase())return false;for(const cls of selector.matchAll(/\.([\w-]+)/g))if(!this.classList.contains(cls[1]))return false;for(const attr of selector.matchAll(/\[([\w-]+)="([^"]+)"\]/g))if(this.attrs[attr[1]]!==attr[2])return false;return true;}
 querySelectorAll(selector){return this.children.flatMap(n=>[...(n.matches(selector)?[n]:[]),...n.querySelectorAll(selector)]);}querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
 insertAdjacentHTML(position,html){assert.equal(position,'beforeend');const node=new El('span',{class:'dirty-dot'});node.textContent='●';this.appendChild(node);}
 setAttribute(k,v){this.attrs[k]=v;}getAttribute(k){return this.attrs[k]??null;}
}
const elements=new Map(p.nodes.filter(([,a])=>a.id).map(([tag,a])=>[a.id,new El(tag,a)]));
document={activeElement:null,getElementById:id=>{assert(elements.has(id),'real template node '+id);return elements.get(id);},createElement:tag=>new El(tag),querySelector:selector=>selector.startsWith('meta')?{content:'fixture-token'}:null,querySelectorAll:selector=>selector==='#sheetTabs .sheet-tab'?elements.get('sheetTabs').children:[],createRange:()=>({selectNodeContents(){},collapse(){}}),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),body:new El('body')};
const ctx={document,Headers,FormData,structuredClone,console,setTimeout(){},clearTimeout(){},confirm:()=>false,location:{href:'/original'},getSelection:()=>({removeAllRanges(){},addRange(){}}),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),print:()=>assert.fail('test never prints'),__PRINT_EDITOR_CONFIG__:{prefix:'out_order',templateId:7},fetch:(url,options)=>{calls.push({url,options,body:options.body?JSON.parse(options.body):undefined});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const el=id=>document.getElementById(id),click=id=>el(id).onclick(),settle=async()=>{for(let i=0;i<4;i++)await new Promise(r=>setImmediate(r));};
const grid={status:'success',sheets:[{name:'SheetA',max_row:1,max_col:1,col_widths:{'1':10},row_heights:{'1':20},cells:[{row:1,col:1,value:'old A'}]},{name:'SheetB',max_row:1,max_col:1,cells:[{row:1,col:1,value:'old B'}]}]};
const posts=()=>calls.filter(c=>c.options.method==='POST');
async function finish(index,scenario='success',body={status:'success',msg:'fixture saved'}){if(scenario==='network')pending[index].reject(Error('fixture offline'));else pending[index].resolve({ok:scenario!=='http_success',status:scenario==='http_success'?500:200,json:()=>Promise.resolve(scenario==='null'?null:scenario==='empty'?{}:scenario==='business'?{status:'error',msg:'fixture refusal'}:body)});await settle();}
function select(){const td=el('gridTable').querySelector('td[data-r="0"][data-c="0"]');assert(td,'real rendered first cell');el('gridTable').fire('mousedown',{target:td});return td;}
function edit(text){const td=select();el('gridTable').fire('dblclick',{target:td});td.innerText=text;td.fire('blur');}
function unloadDirty(){let prevented=false;const event={preventDefault(){prevented=true;},returnValue:undefined};for(const fn of events.beforeunload||[])fn(event);return prevented;}
(async()=>{
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/out_order_print_template/7/grid');
 if(p.mode==='unloaded'){click('btnSave');await settle();assert.equal(posts().length,0);return;}
 if(p.mode==='load_failure'){await finish(0,'network');click('btnSave');await settle();assert.equal(posts().length,0);return;}
 await finish(0,'success',grid);assert.equal(ctx.__tplEditor.getS().rows[0].cells[0].t,'old A');assert(el('gridTable').innerHTML.includes('old A'));assert(!unloadDirty());
 edit('submitted');click('btnSave');await settle();assert.equal(posts().length,1);const sent=posts()[0];assert.equal(sent.url,'/out_order_print_template/7/grid');assert.equal(sent.options.headers['X-CSRFToken'],'fixture-token');assert.deepEqual(sent.body.sheets[0].upserts,[[1,1,'submitted']]);assert.deepEqual(sent.body.sheets[0].del_rows,[]);
 if(p.mode==='duplicate'){click('btnSave');click('btnSave');await settle();assert.equal(posts().length,1,'saving is single-flight even when handler is called again');}
 if(p.mode==='text')edit('later text');
 if(p.mode==='undo')click('btnUndo');
 if(p.mode==='sheet'){el('sheetTabs').children[1].onclick();edit('later B');}
 if(p.mode==='style'){select();click('tbBold');}
 if(p.mode==='dimension'){select();el('tbColWidth').value='25';click('btnColW');}
 if(p.mode==='structure'){select();click('btnInsRowU');}
 await finish(1,p.mode==='failure'?p.scenario:'success');
 const sheets=ctx.__tplEditor.getSheets();
 if(p.mode==='failure'){
  assert.equal(sheets[0].orig.rows[0].cells[0].t,'old A','failed write never advances baseline');assert.equal(sheets[0].S.rows[0].cells[0].t,'submitted');assert(unloadDirty());assert(!el('btnSave').disabled);assert(el('toastSlot').children.some(n=>n.className.includes('alert-danger')));click('btnSave');await settle();assert.equal(posts().length,2,'failed save only retries on another manual click');assert.deepEqual(posts()[1].body,sent.body);await finish(2);assert(!unloadDirty());return;
 }
 assert.equal(sheets[0].orig.rows[0].cells[0].t,'submitted','success acknowledges submitted snapshot only');
 const dirty=['text','undo','sheet','style','dimension','structure'].includes(p.mode);
 assert.equal(unloadDirty(),dirty,'later unsaved state must keep unload warning');assert.equal(el('btnSave').innerHTML.includes('●'),dirty);
 if(!dirty){assert(!el('btnSave').disabled);return;}
 assert(el('statusInfo').textContent.includes('仍有未保存'),'successful snapshot must not claim all current edits were saved');
 if(p.mode==='sheet'){assert.equal(ctx.__tplEditor.getActiveIdx(),1);assert.equal(sheets[1].orig.rows[0].cells[0].t,'old B');}
 click('btnSave');await settle();assert.equal(posts().length,2,'later edits remain saveable');const next=posts()[1].body.sheets;
 if(p.mode==='text')assert.deepEqual(next[0].upserts,[[1,1,'later text']]);
 if(p.mode==='undo')assert.deepEqual(next[0].upserts,[[1,1,'old A']]);
 if(p.mode==='sheet'){assert.equal(next.length,1);assert.equal(next[0].name,'SheetB');assert.deepEqual(next[0].upserts,[[1,1,'later B']]);}
 if(p.mode==='style')assert.deepEqual(next[0].styles,[[1,1,{bold:true}]]);
 if(p.mode==='dimension')assert.deepEqual(next[0].col_widths,{'1':25});
 if(p.mode==='structure'){assert.deepEqual(next[0].del_rows,[]);assert(next[0].upserts.some(v=>v[0]===1&&v[1]===1&&v[2]===''));assert(next[0].upserts.some(v=>v[0]===2&&v[1]===1&&v[2]==='submitted'));}
 await finish(2);assert(!unloadDirty());
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def run(mode,scenario='success',source_override=None):
    node=shutil.which('node');assert node,'Node required for whole grid editor regression'
    payload=dict(mode=mode,scenario=scenario,source=source_override or SOURCE.read_text(encoding='utf-8'),nodes=Nodes((ROOT/'app/templates/print_template_editor.html').read_text(encoding='utf-8')).nodes,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('mode',['clean','text','undo','sheet','style','dimension','structure','duplicate'])
def test_deferred_save_acknowledges_only_submitted_snapshot_and_preserves_next_diff(mode):
    run(mode)


@pytest.mark.parametrize('scenario',['network','http_success','null','empty','business'])
def test_failed_save_keeps_original_baseline_dirty_state_and_manual_retry(scenario):
    run('failure',scenario)


@pytest.mark.parametrize('mode',['unloaded','load_failure'])
def test_unloaded_editor_never_saves_a_blank_template(mode):
    run(mode)
