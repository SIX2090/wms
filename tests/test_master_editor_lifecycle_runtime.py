"""Exercise real master editors and api.js with delayed HTTP and modal events."""
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
KINDS = 'customer supplier unit contract employee warehouse department category material'.split()


class EditorControls(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.depth = 0
        self.inside = False
        self.controls = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            if attrs.get('id') == 'editModal':
                self.inside = True
                self.depth = 1
            elif self.inside:
                self.depth += 1
        if self.inside and tag in ('input', 'select', 'textarea', 'button'):
            self.controls.append({'tag': tag, **attrs})

    def handle_endtag(self, tag):
        if self.inside and tag == 'div':
            self.depth -= 1
            if not self.depth:
                self.inside = False


def take(text, token):
    start = text.index(token)
    opening = text.index('{', start)
    depth, quote, escaped = 0, None, False
    for end in range(opening, len(text)):
        char = text[end]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if not depth:
                return text[start:end + 1]
    raise AssertionError(token)


def shared_helpers():
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    return '\n'.join(take(shared, 'function ' + name + '(') for name in
                        ('isWmsMasterEditPending', 'loadWmsMasterEditor')
                        if 'function ' + name + '(' in shared)


def sources(kind):
    path = ROOT / f'app/templates/{kind}.html'
    html = path.read_text(encoding='utf-8')
    external = kind in ('employee', 'warehouse', 'department')
    page = (ROOT / f'app/static/js/pages/{kind}.js').read_text(encoding='utf-8') if external else html
    marker = (f'window.edit{kind.capitalize()} = function(id)' if kind in ('category', 'material')
              else f'function edit{kind.capitalize()}(id)')
    # Use the same brace-aware source extraction for local and external scripts.
    helpers = shared_helpers()
    save = (take(page, 'function submitEdit()') if external or kind == 'contract'
            else take(page[page.index("var editForm = document.getElementById('editForm');"):], 'function(e)'))
    images = ''
    if kind == 'material':
        for name in ('getEditMaterialContext', 'loadEditMaterialImages', 'deleteEditMaterialImage', 'uploadEditMaterialImage'):
            token = 'window.' + name + ' = function('
            if token in page:
                images += take(page, token) + ';\n'
    return dict(kind=kind, helper=helpers, edit=take(page, marker), save=save,
                controls=EditorControls(html).controls, images=images,
                api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))


PROGRAM = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes={},messages=[],requests=[],timers=[];let shows=0;
function node(attrs={}) {
 const listeners={},classes=new Set();let html='',text='';
 const value={...attrs,value:attrs.value||'',isConnected:true,disabled:Object.hasOwn(attrs,'disabled'),listeners,
  classList:{add(...v){v.forEach(x=>classes.add(x));},remove(...v){v.forEach(x=>classes.delete(x));},contains:v=>classes.has(v)},
  getAttribute:k=>Object.hasOwn(attrs,k)?attrs[k]:null,hasAttribute:k=>Object.hasOwn(attrs,k),setAttribute(k,v){attrs[k]=String(v);},removeAttribute(k){delete attrs[k];},
  addEventListener(type,fn,capture=false){(listeners[type]||=[]).push({fn,capture:!!capture});},
  dispatchEvent(event){event.target??=this;event.preventDefault??=function(){this.defaultPrevented=true;};event.stopImmediatePropagation??=function(){this.stopped=true;};
   for(const phase of [true,false])for(const h of listeners[event.type]||[])if(h.capture===phase&&!event.stopped)h.fn.call(this,event);
   if(!event.stopped&&this!==document)for(const h of document.listeners[event.type]||[])h.fn.call(document,event);return !event.defaultPrevented;},
  set innerHTML(v){html=String(v);text='';},get innerHTML(){return html;},set textContent(v){text=String(v);html='';},get textContent(){return text;}};
 return value;
}
const document={listeners:{},getElementById:id=>nodes[id]||null,querySelector:s=>s.includes('csrf-token')?{content:'fixture-token'}:null,
 addEventListener(type,fn){(this.listeners[type]||=[]).push({fn});}};
const form=nodes.editForm=node({id:'editForm'}),modal=nodes.editModal=node({id:'editModal'});
const controls=p.controls.map((a,i)=>{const n=node({...a,id:a.id||'control-'+i});if(a.id)nodes[a.id]=n;return n;});
form.elements=controls.filter(n=>n.name);
form.querySelector=s=>{const m=s.match(/name=["']([^"']+)["']/);return m?form.elements.find(n=>n.name===m[1]):null;};
form.querySelectorAll=()=>form.elements;
modal.querySelectorAll=()=>controls;modal.querySelector=s=>s==='form'?form:null;
for(const n of controls)if(n.tag==='select')n.options=[{value:'',disabled:false},{value:'1',disabled:false},{value:'2',disabled:false}];
for(const id of ['addModal','importModal','editMaterialImageGrid'])nodes[id]=node({id});
const nameField=form.elements.find(n=>n.name==='name')||form.elements.find(n=>n.name==='project_name');
const codeField=form.elements.find(n=>n.name==='code')||form.elements.find(n=>n.name==='contract_no');
const saveButton=controls.find(n=>n.tag==='button'&&n.getAttribute('data-bs-dismiss')!=='modal'&&n.getAttribute('type')!=='button')||controls.find(n=>n.tag==='button'&&n.getAttribute('data-bs-dismiss')!=='modal');
const cancelButton=controls.find(n=>n.getAttribute('data-bs-dismiss')==='modal');
class Modal{constructor(n){this.node=n;n.instance=this;}show(){this.node.dispatchEvent({type:'show.bs.modal'});this.node.classList.add('show');if(this.node===modal)shows++;}hide(){this.node.dispatchEvent({type:'hide.bs.modal'});this.node.classList.remove('show');this.node.dispatchEvent({type:'hidden.bs.modal'});}static getInstance(n){return n.instance;}}
class FormData{constructor(owner){this.owner=owner;this.rows=Array.from(owner?.elements||[]).filter(n=>n.name&&!n.disabled).map(n=>[n.name,n.value]);}get(k){return this.rows.find(([key])=>key===k)?.[1]??null;}append(k,v){this.rows.push([k,v]);}}
const ctx={document,FormData,Headers,Promise,setTimeout:fn=>timers.push(fn),clearTimeout(){},bootstrap:{Modal},showToast:(m,t)=>messages.push({m,t}),
 setQuickSelectValue:(id,v)=>{if(nodes[id])nodes[id].value=v;},setInputValueIfExists:(id,v)=>{if(nodes[id])nodes[id].value=v;},setWmsDateInputValue:(n,v)=>{if(n)n.value=v;},
 commitQuickSelects(){},notifyMasterDataChanged(){},confirm:()=>true,location:{reload(){}},loadEditMaterialImages(){},
 fetch:(url,options={})=>new Promise((resolve,reject)=>requests.push({url,options,resolve,reject}))};ctx.window=ctx;
vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.edit,ctx);vm.runInContext('var save = '+p.save+';',ctx);if(p.images)vm.runInContext(p.images,ctx);
const edit=ctx['edit'+p.kind[0].toUpperCase()+p.kind.slice(1)],tick=()=>new Promise(r=>setImmediate(r));
function record(id){return {id,code:'C'+id,name:'NAME'+id,contract_no:'CON'+id,project_name:'PROJECT'+id,contact:'CONTACT'+id,phone:'PHONE'+id,address:'ADDRESS'+id,position:'POSITION'+id,department_id:id,status:'active',type:'normal',location:'LOC'+id,remark:'REMARK'+id,category_id:id,unit_id:id,supplier_id:id,price:0};}
function response(req,body,status=200){req.resolve({ok:status>=200&&status<300,status,json:()=>Promise.resolve(body)});}
function detail(req,id,status=200){response(req,{status:'success',[p.kind]:record(id)},status);}
const requestFor=(path,method='GET')=>requests.findLast(r=>r.url===path&&(r.options.method||'GET')===method);
const readId=()=>p.kind==='material'?nodes.edit_id.value:p.kind==='category'?nodes.editId.value:form.querySelector('[name="id"]').value;
const runSave=()=>ctx.save.call(form,{preventDefault(){}});
async function open(id){edit(id);detail(requestFor('/'+p.kind+'/'+id),id);await tick();return requestFor('/mobile/api/material_archive/'+id+'/images');}
function images(req,id){response(req,{status:'success',data:{images:[{id,url:'/IMAGE'+id+'.jpg'}]}});}
(async()=>{
 if(p.scenario==='latest'||p.scenario==='stale_error'){
  edit(1);edit(2);detail(requests[1],2);await tick();assert.equal(String(readId()),'2');
  if(p.scenario==='latest')detail(requests[0],1);else requests[0].reject(Error('old offline'));await tick();
  assert.equal(String(readId()),'2','old detail must not replace the requested record');assert.equal(shows,1);assert.equal(messages.length,0);return;
 }
 if(p.scenario==='old_first'){
  edit(1);edit(2);detail(requests[0],1);await tick();assert.equal(shows,0);assert.equal(saveButton.disabled,true,'old finally must not unlock the newer read');
  runSave();await tick();assert.equal(requests.length,2,'newer read remains protected');detail(requests[1],2);await tick();assert.equal(String(readId()),'2');assert.equal(saveButton.disabled,false);return;
 }
 if(p.scenario==='close'||p.scenario==='close_reopen'){
  await open(1);edit(2);const old=requestFor('/'+p.kind+'/2');modal.dispatchEvent({type:'hide.bs.modal'});modal.classList.remove('show');
  if(p.scenario==='close_reopen')edit(3);
  modal.dispatchEvent({type:'hidden.bs.modal'});detail(old,2);await tick();
  assert.equal(shows,1,'closed editor must not reopen from an old response');
  if(p.scenario==='close_reopen'){detail(requestFor('/'+p.kind+'/3'),3);await tick();assert.equal(String(readId()),'3');assert.equal(shows,2,'old hidden event must not cancel the newly requested record');}return;
 }
 if(['add','import','detach','replace','form_replace'].includes(p.scenario)){
  edit(1);const old=requestFor('/'+p.kind+'/1');
  if(p.scenario==='detach')modal.isConnected=false;
  else if(p.scenario==='replace')nodes.editModal=node({id:'editModal'});
  else if(p.scenario==='form_replace')nodes.editForm=node({id:'editForm'});
  else new Modal(nodes[p.scenario+'Modal']).show();
  detail(old,1);await tick();assert.equal(shows,0,'superseded editor must not open');assert.equal(messages.length,0,'superseded read must not report a current failure');return;
 }
 if(p.scenario==='save_guard'||p.scenario==='controls'){
  nameField.disabled=true;modal.setAttribute('aria-busy','polite');edit(1);
  assert.equal(saveButton.disabled,true,'loading must disable saving');assert.equal(cancelButton.disabled,false,'cancel remains usable');
  assert.equal(codeField.disabled,true);assert.equal(modal.getAttribute('aria-busy'),'true');
  const event={type:'submit'};form.dispatchEvent(event);runSave();await tick();
  assert.equal(requests.length,1,'Enter and direct onclick save must not submit the previous ID');
  assert.equal(event.defaultPrevented,true,'capture submit must stop native submit while loading');
  detail(requests[0],1);await tick();assert.equal(nameField.disabled,true);assert.equal(codeField.disabled,false);assert.equal(saveButton.disabled,false);assert.equal(cancelButton.disabled,false);assert.equal(modal.getAttribute('aria-busy'),'polite');return;
 }
 if(p.scenario.startsWith('failure_')){
  const failure=p.scenario.slice(8);edit(1);const req=requests[0];
  if(failure==='network')req.reject(Error('offline'));
  else if(failure==='http')detail(req,1,500);
  else if(failure==='null')response(req,null);
  else if(failure==='array')response(req,{status:'success',[p.kind]:[]});
  else if(failure==='missing')response(req,{status:'success'});
  else if(failure==='wrong_id')detail(req,9);
  else response(req,{status:'error',msg:'fixture denial'});
  await tick();assert.equal(shows,0);assert(messages.some(m=>m.t==='danger'),'current failure is visible');assert.equal(saveButton.disabled,false);
  edit(2);detail(requestFor('/'+p.kind+'/2'),2);await tick();assert.equal(String(readId()),'2','failed read permits manual retry');assert.equal(shows,1);return;
 }
 if(p.scenario==='success'){
  await open(2);assert.equal(String(readId()),'2');assert.equal(codeField.value,p.kind==='contract'?'CON2':'C2');assert.equal(nameField.value,p.kind==='contract'?'PROJECT2':'NAME2');assert.equal(shows,1);assert.equal(messages.length,0);
  assert.equal(requests[0].options.method,'GET');assert.equal(new Headers(requests[0].options.headers).get('X-CSRFToken'),'fixture-token');
  if(p.kind==='category')assert.equal(nodes.editParentId.options.find(o=>o.value==='2').disabled,true);return;
 }
 if(p.scenario.startsWith('image_')){
  const first=await open(1);const grid=nodes.editMaterialImageGrid;
  if(p.scenario==='image_file_reset'){
   nodes.edit_image_upload.value='A.png';Modal.getInstance(modal).hide();await open(2);assert.equal(nodes.edit_image_upload.value,'','a newly opened record must not inherit the former file selection');return;
  }
  if(['image_upload','image_delete','image_upload_pending','image_delete_pending'].includes(p.scenario)){
   images(first,1);await tick();const input=nodes.edit_image_upload;input.files=[{name:'A.png'}];input.value='A.png';
   if(p.scenario.includes('upload'))ctx.uploadEditMaterialImage(input);else ctx.deleteEditMaterialImage(1);
   const write=requests.at(-1);assert.notEqual(write.options.method,'GET');
   if(p.scenario.endsWith('pending'))edit(2);else {const second=await open(2);images(second,2);await tick();assert.equal(input.value,'','new detail clears the former selected file');}
   input.value='B.png';const before=requests.length;response(write,{status:'success'});await tick();assert.equal(requests.length,before,'old write callback must not fetch the former record images');
   if(p.scenario.includes('upload'))assert.equal(input.value,'B.png','old upload callback must not clear a newer file selection');return;
  }
  if(p.scenario==='image_close'){Modal.getInstance(modal).hide();images(first,1);await tick();assert(!grid.innerHTML.includes('IMAGE1'),'closed editor ignores old images');return;}
  const second=await open(2);images(second,2);await tick();assert(grid.innerHTML.includes('IMAGE2'));
  if(p.scenario==='image_old_error')first.reject(Error('old offline'));else images(first,1);await tick();assert(grid.innerHTML.includes('IMAGE2'),'old image result must not replace the current record');assert(!grid.textContent.includes('old offline'));return;
 }
 throw Error('unknown scenario '+p.scenario);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


def run(kind, scenario):
    node = shutil.which('node')
    assert node, 'Node is required for lifecycle runtime verification'
    result = subprocess.run([node, '-e', PROGRAM], input=json.dumps({**sources(kind), 'scenario': scenario}),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('scenario', [
    'latest', 'stale_error', 'old_first', 'close', 'close_reopen', 'add', 'import', 'detach', 'replace', 'form_replace',
    'save_guard', 'controls', 'success', 'failure_network', 'failure_http', 'failure_null',
    'failure_array', 'failure_missing', 'failure_wrong_id', 'failure_business',
])
def test_master_editor_reads_and_saves_belong_to_current_record(kind, scenario):
    run(kind, scenario)


@pytest.mark.parametrize('scenario', [
    'image_latest', 'image_old_error', 'image_close', 'image_upload', 'image_delete',
    'image_upload_pending', 'image_delete_pending', 'image_file_reset',
])
def test_material_image_callbacks_belong_to_current_editor(scenario):
    run('material', scenario)
