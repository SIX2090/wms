"""Exercise the complete Excel component, actual modal events and production API."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let ctx,ids={},readers=[],requests=[],timers=[],messages=[],scripts=[],reloads=0,sessionPrompts=0,callbacks=[];
class Element {
 constructor(tag='div'){this.tagName=tag.toUpperCase();this.children=[];this.events={};this.disabled=false;this.files=[];this._value='';this._text='';this._html='';this._class='';this.style={};this.attrs={};this.classList={add:c=>this.className=[...new Set([...this.className.split(' ').filter(Boolean),c])].join(' '),remove:c=>this.className=this.className.split(' ').filter(x=>x!==c).join(' '),contains:c=>this.className.split(' ').includes(c)};}
 set className(v){this._class=v}get className(){return this._class}
 set textContent(v){this._text=String(v);this.children=[];this._html=''}get textContent(){return this._text+this.children.map(c=>c.textContent).join('')}
 set innerHTML(v){this._html=v;this.children=[];this._text=''}get innerHTML(){return this._html}
 set value(v){this._value=v;if(this.tagName==='INPUT'&&this.type==='file'&&v==='')this.files=[]}get value(){return this._value}
 appendChild(n){this.children.push(n);n.parentElement=this;return n}
 addEventListener(n,fn){(this.events[n] ||= []).push(fn)}
 dispatch(n){for(const fn of this.events[n]||[])fn({target:this,preventDefault(){}})}
 click(){if(this.disabled)return;if(this.onclick)this.onclick();this.dispatch('click')}
 querySelector(s){if(s==='.order-toolbar')return toolbar;if(s==='.btn-group')return buttons;return this.children.find(n=>n.tagName===s.toUpperCase())||null}
 remove(){}
 insertAdjacentHTML(_position,html){const stack=[this];for(const m of html.matchAll(/<\/?([a-z][\w-]*)([^>]*)>|([^<]+)/gi)){if(m[3]){stack.at(-1)._text+=m[3];continue}if(m[0].startsWith('</')){stack.pop();continue}const n=new Element(m[1]);for(const a of m[2].matchAll(/([\w-]+)="([^"]*)"/g)){n.attrs[a[1]]=a[2];if(a[1]==='id'){n.id=a[2];ids[n.id]=n}if(a[1]==='class')n.className=a[2];if(a[1]==='type')n.type=a[2]}n.disabled=/\bdisabled\b/.test(m[2]);stack.at(-1).appendChild(n);if(!['input','br','hr','img'].includes(m[1]))stack.push(n)}}
}
const toolbar=new Element(),buttons=new Element(),body=new Element(),container=new Element();
const document={currentScript:{src:'https://wms.test/static/js/excel-import-export.js?v=fixture'},baseURI:'https://wms.test/doc/7',body,head:{appendChild:n=>scripts.push(n)},createElement:tag=>new Element(tag),getElementById:id=>ids[id]||null,querySelector:s=>s==='.order-table-container'?container:s.startsWith('meta')?{content:'fixture-token'}:null};
const fileA={name:'A.xlsx',marker:1,size:10,lastModified:1},fileB={name:'B.xlsx',marker:2,size:10,lastModified:1};
class Reader {readAsArrayBuffer(file){this.file=file;readers.push(this)}}
class FD {constructor(){if(p.scenario==='formdata-failure')throw new Error('fixture FormData failed');this.entries=[]}append(k,v){this.entries.push([k,v])}}
let modalInstances=new Map();
class Modal {constructor(node){this.node=node;modalInstances.set(node,this)}show(){this.node.shown=true;this.node.dispatch('show.bs.modal')}hide(){this.node.dispatch('hide.bs.modal');this.node.shown=false;this.node.dispatch('hidden.bs.modal')}static getInstance(node){return modalInstances.get(node)}}
const rowsByMarker={1:[{code:'A',quantity:1,price:0}],2:[{code:'B',quantity:2,price:3}],3:[],4:Array.from({length:12},(_,i)=>({quantity:i,price:0})),5:[{quantity:0,price:0,missing:null,empty:'',flag:false}],6:[{code:'<img src=x onerror=bad()> & "零"',quantity:1}]};
const xlsx={read:bytes=>{if(bytes[0]===255)throw new Error('fixture invalid workbook');return {SheetNames:['first'],Sheets:{first:{marker:bytes[0]}}}},utils:{sheet_to_json:sheet=>rowsByMarker[sheet.marker]}};
ctx={document,URL,Headers,Promise,FormData:FD,FileReader:Reader,Uint8Array,ArrayBuffer,bootstrap:{Modal},console,location:{origin:'https://wms.test',href:'/doc/7',reload:()=>reloads++},setTimeout:(fn,ms)=>{timers.push({fn,ms});return timers.length},confirm:()=>{sessionPrompts++;return false},showToast:(message,type)=>messages.push({message,type}),wmsGlobalErrorToast:message=>messages.push({message,type:'danger',global:true}),fetch:(url,options)=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject})),getCsrfToken:()=> 'fixture-token'};
ctx.window=ctx;ctx.XLSX=xlsx;vm.createContext(ctx);vm.runInContext(p.interceptor,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.legacy,ctx);vm.runInContext(p.source+';this.Component=ExcelImportExport;',ctx);
const component=new ctx.Component({importUrl:p.importUrl,columns:[{label:'code',required:true}]});
const fileInput=ids.excelFileInput,submit=ids.confirmImportBtn,modal=ids.excelImportModal;
const result=()=>ids.excelImportResult;const previewRows=()=>ids.previewTable.querySelector('tbody').children;
const flush=async()=>{for(let n=0;n<5;n++)await new Promise(r=>setImmediate(r))};
async function select(file=fileA){fileInput.files=file?[file]:[];fileInput.value=file?'C:\\fakepath\\'+file.name:'';fileInput.dispatch('change');await flush()}
function finish(index=readers.length-1,marker=readers[index].file.marker){readers[index].onload({target:{result:Uint8Array.of(marker).buffer}})}
async function ready(file=fileA){component.showImportModal();await select(file);finish();assert.equal(submit.disabled,false)}
function response(kind='success',data={status:'success',count:1}){const status={http:500,http_error:400,html:502,expired401:401,expired419:419}[kind]||200;return {ok:status<400,status,json:()=>kind==='html'?Promise.reject(new SyntaxError('HTML gateway')):Promise.resolve(kind==='null'?null:kind==='business'?{status:'error',msg:'库存导入被拒绝'}:kind==='http_error'?{status:'error',msg:'错误 <物料>'}:data)}}
async function settle(index=0,kind='success',data){if(kind==='network')requests[index].reject(new Error('网络中断'));else requests[index].resolve(response(kind,data));await flush()}
const payload=index=>{const r=requests[index],headers=r.options.headers,header=name=>headers instanceof Headers?headers.get(name):headers[name];assert.equal(r.url,p.importUrl);assert.equal(r.options.method,'POST');assert.equal(header('X-CSRFToken'),'fixture-token');assert.equal(header('X-Requested-With'),'XMLHttpRequest');assert(!header('Content-Type'));assert(r.options.body instanceof FD);return r.options.body.entries[0][1]};
const noImport=()=>assert.equal(requests.length,0);
const readCase=p.scenario;
(async()=>{
 assert.equal(typeof ctx.WMS.api.postRaw,'function');
 if(['close-read','reopen-read','close-library','clear-selection','switch-read','old-read-error','old-read-malformed','old-library-error','same-object','same-metadata'].includes(readCase)){
  component.showImportModal();
  if(['close-library','old-library-error'].includes(readCase))delete ctx.XLSX;
  await select(fileA);
  if(readCase==='close-library'){Modal.getInstance(modal).hide();component.showImportModal();ctx.XLSX=xlsx;scripts[0].onload();await flush();assert.equal(readers.length,0);assert.equal(submit.disabled,true);noImport();return}
  if(readCase==='old-library-error'){ctx.XLSX=xlsx;await select(fileB);finish();scripts[0].onerror();await flush();assert.equal(messages.length,0);assert.equal(previewRows()[0].children[0].textContent,'B');return}
  if(readCase==='close-read'||readCase==='reopen-read'){Modal.getInstance(modal).hide();if(readCase==='reopen-read')component.showImportModal();finish(0);assert.equal(submit.disabled,true);assert(ids.importPreview.classList.contains('d-none'));submit.click();noImport();assert.equal(fileInput.value,'');return}
  if(readCase==='clear-selection'){await select(null);finish(0);assert.equal(submit.disabled,true);assert(ids.importPreview.classList.contains('d-none'));noImport();return}
  const next=readCase==='same-object'?fileA:readCase==='same-metadata'?{...fileA,marker:2}:fileB;
  await select(next);finish(1);const expected=next.marker===2?'B':'A';
  if(readCase==='old-read-error'||readCase==='same-object')readers[0].onerror();else finish(0,readCase==='old-read-malformed'?255:fileA.marker);
  assert.equal(messages.length,0);assert.equal(previewRows()[0].children[0].textContent,expected);assert.equal(submit.disabled,false);assert.equal(fileInput.value,'C:\\fakepath\\'+next.name);noImport();return;
 }
 if(['current-read-error','current-read-malformed','empty-workbook'].includes(readCase)){component.showImportModal();await select();if(readCase==='current-read-error')readers[0].onerror();else finish(0,readCase==='empty-workbook'?3:255);assert.equal(submit.disabled,true);assert.equal(messages.length,1);assert.equal(messages[0].type,readCase==='empty-workbook'?'warning':'danger');noImport();return}
 if(['preview-zero','preview-literal','preview-limit'].includes(readCase)){component.showImportModal();await select();finish(0,readCase==='preview-zero'?5:readCase==='preview-literal'?6:4);const rows=previewRows();if(readCase==='preview-zero')assert.deepEqual(rows[0].children.map(n=>n.textContent),['0','0','','','false']);if(readCase==='preview-literal'){assert.equal(rows[0].children[0].textContent,rowsByMarker[6][0].code);assert.equal(rows[0].children[0].children.length,0)}if(readCase==='preview-limit'){assert.equal(rows.length,10);assert.equal(ids.previewCount.textContent,'12')}noImport();return}
 if(readCase==='no-preview'){component.showImportModal();component.confirmImport();await flush();noImport();assert(messages.some(x=>x.type==='warning'));return}
 await ready();assert.equal(fileInput.value,'C:\\fakepath\\A.xlsx');
 if(readCase==='no-url'){component.options.importUrl=null;component.confirmImport();await flush();noImport();assert(messages.some(x=>x.message.includes('未配置')));return}
 if(readCase==='callback-error-sync')component.options.onImportSuccess=()=>{throw new Error('post-save UI failed')};
 if(readCase==='callback-error-async')component.options.onImportSuccess=()=>Promise.reject(new Error('post-save async UI failed'));
 let finishCallback;if(readCase==='callback-late-error')component.options.onImportSuccess=()=>new Promise((_resolve,reject)=>finishCallback=reject);if(readCase==='callback-wait')component.options.onImportSuccess=res=>{callbacks.push(res);return new Promise(r=>finishCallback=r)};
 if(readCase==='callback-success')component.options.onImportSuccess=res=>callbacks.push(res);
 if(readCase==='error-callback')component.options.onImportError=res=>{callbacks.push(res);throw new Error('UI failed')};
 if(readCase==='input-original-disabled')fileInput.disabled=true;
 submit.click();await flush();
 if(readCase==='formdata-failure'){noImport();assert.equal(submit.disabled,false);assert.equal(fileInput.disabled,false);assert(result().textContent.includes('FormData'));return}
 assert.equal(requests.length,1);assert.equal(payload(0),fileA);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,true);
 if(readCase==='double-confirm'){component.confirmImport();submit.click();await flush();assert.equal(requests.length,1)}
 if(['reopen-pending','choose-pending'].includes(readCase)){Modal.getInstance(modal).hide();component.showImportModal();if(readCase==='choose-pending')await select(fileB);component.confirmImport();await flush();assert.equal(requests.length,1);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,true)}
 if(['failure-http','failure-business','failure-null','failure-html','failure-network','failure-http-error','failure-401','failure-419','error-callback','input-original-disabled'].includes(readCase)){
  const kind={'failure-http':'http','failure-business':'business','failure-null':'null','failure-html':'html','failure-network':'network','failure-http-error':'http_error','failure-401':'expired401','failure-419':'expired419','error-callback':'business','input-original-disabled':'business'}[readCase];await settle(0,kind);assert(!messages.some(x=>x.type==='success'),'HTTP/business failure must never report import success');assert.equal(submit.disabled,false);assert.equal(fileInput.disabled,readCase==='input-original-disabled');assert(result().textContent.includes('导入失败'));assert.equal(timers.filter(t=>t.ms===800).length,0);assert.equal(sessionPrompts,['failure-401','failure-419'].includes(readCase)?1:0);if(readCase==='error-callback'){assert.equal(callbacks.length,1);assert.equal(callbacks[0].status,'error')};component.confirmImport();await flush();assert.equal(requests.length,2);assert.equal(payload(1),fileA);return;
 }
 let data={status:'success',count:1};
 if(readCase==='count-zero')data={status:'success',count:0};
 if(readCase==='count-zero-generic')data={status:'success',count:0,msg:'导入完成'};
 if(readCase==='count-zero-server')data={status:'success',count:0,msg:'入库单导入成功，共导入 0 张单据，跳过 1 条',warnings:'跳过详情：第2行：单据编号为空'};
 if(readCase==='warning-string')data={status:'success',count:1,msg:'成功 1 张',warnings:'第3行跳过：数量必须大于0'};
 if(readCase==='warning-array')data={status:'success',count:1,warnings:['第3行跳过','第4行跳过']};
 if(readCase==='warning-literal')data={status:'success',count:1,msg:'A <b> & "单据"',warnings:'<img src=x onerror=bad()> & 原因'};
 if(readCase==='server-count')data={status:'success',count:2,msg:'成功导入 2 张单据'};
 if(readCase==='legacy-no-count')data={status:'success'};
 await settle(0,'success',data);
 if(readCase==='callback-wait'){assert.equal(modal.shown,false);assert.equal(callbacks.length,1);component.confirmImport();await select(fileB);assert.equal(requests.length,1);assert.equal(fileInput.disabled,true);finishCallback();await flush();assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,false);assert.equal(timers.length,0);return}
 if(readCase==='callback-late-error'){assert.equal(modal.shown,false);component.showImportModal();Modal.getInstance(modal).hide();finishCallback(new Error('late callback failed'));await flush();assert.equal(modal.shown,false);assert.equal(submit.disabled,true);assert(result().textContent.includes('勿重复导入'));component.confirmImport();await flush();assert.equal(requests.length,1);return}
 if(readCase.startsWith('callback-error')){assert.equal(modal.shown,false);component.showImportModal();assert.equal(modal.shown,true);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,false);assert.equal(timers.length,0);assert(result().textContent.includes('导入已成功'));assert(result().textContent.includes('勿重复导入'));component.confirmImport();await flush();assert.equal(requests.length,1);await select(fileB);finish();submit.click();await flush();assert.equal(requests.length,2);assert.equal(payload(1),fileB);return}
 const review=readCase.startsWith('count-zero')||readCase.startsWith('warning-');
 if(review){assert.equal(modal.shown,true);assert.equal(timers.filter(t=>t.ms===800).length,0);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,false);assert(result().className.includes('warning'));assert.equal(result().children.length,0);if(readCase.startsWith('count-zero'))assert(/0\s*(条|张)/.test(result().textContent));if(data.msg)assert(result().textContent.includes(data.msg));for(const text of [].concat(data.warnings||[]))assert(result().textContent.includes(text));component.confirmImport();await flush();assert.equal(requests.length,1);if(readCase==='count-zero-server'){await select(fileA);finish();submit.click();await flush();assert.equal(requests.length,2);assert.equal(payload(1),fileA)}return}
 if(readCase==='callback-success'){assert.equal(modal.shown,false);assert.equal(callbacks.length,1);assert.equal(callbacks[0].count,1);assert.equal(timers.length,0);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,false);return}
 assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,true);assert.equal(modal.shown,false);assert.equal(timers.filter(t=>t.ms===800).length,1);assert.equal(reloads,0);if(readCase==='server-count')assert(messages.some(x=>x.message==='成功导入 2 张单据'));
 component.showImportModal();await select(fileB);component.confirmImport();await flush();assert.equal(requests.length,1);assert.equal(submit.disabled,true);assert.equal(fileInput.disabled,true);timers.find(t=>t.ms===800).fn();assert.equal(reloads,1);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1});
'''


SCENARIOS = [
    'close-read', 'reopen-read', 'close-library', 'clear-selection', 'switch-read',
    'old-read-error', 'old-read-malformed', 'old-library-error', 'same-object',
    'same-metadata', 'current-read-error', 'current-read-malformed', 'empty-workbook',
    'preview-zero', 'preview-literal', 'preview-limit', 'no-preview', 'no-url',
    'payload', 'double-confirm', 'reopen-pending', 'choose-pending',
    'failure-http', 'failure-business', 'failure-null', 'failure-html',
    'failure-network', 'failure-http-error', 'failure-401', 'failure-419',
    'formdata-failure', 'input-original-disabled', 'count-zero', 'count-zero-generic',
    'count-zero-server', 'warning-string', 'warning-array', 'warning-literal',
    'server-count', 'legacy-no-count', 'callback-success', 'callback-error-sync',
    'callback-error-async', 'callback-wait', 'callback-late-error', 'error-callback',
]


@pytest.mark.parametrize('page', ['in_order_detail', 'out_order_detail'])
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_actual_excel_import_modal_preserves_selection_and_result(page, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    page_source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    import_url = re.search(r"importUrl:\s*'([^']+)'", page_source).group(1)
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    legacy = base[base.index('    function csrfFetch('):base.index('    // Deprecated alias')]
    payload = dict(
        scenario=scenario, importUrl=import_url, legacy=legacy,
        interceptor=base[base.index('    (function() {'):base.index('    // F2.14 全局兜底')],
        source=(ROOT / 'app/static/js/excel-import-export.js').read_text(encoding='utf-8'),
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
    )
    result = subprocess.run([node, '-e', PROGRAM], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr
