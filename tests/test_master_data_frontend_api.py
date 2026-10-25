"""Run real master-data page listeners through the production API transport."""
import json
import hashlib
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest
from tests.test_master_editor_lifecycle_runtime import shared_helpers

ROOT = Path(__file__).resolve().parents[1]
PAGES = "category customer department employee unit warehouse supplier".split()


def page_source(page):
    return (ROOT / f"app/templates/{page}.html").read_text(encoding="utf-8")


def page_scripts(page):
    chunks = []
    for match in re.finditer(r'<script([^>]*)>(.*?)</script>', page_source(page), re.S):
        asset = re.search(r"filename=['\"]([^'\"]+)", match.group(1))
        chunks.append((ROOT / 'app/static' / asset.group(1)).read_text(encoding='utf-8') if asset else match.group(2))
    return '\n'.join(chunks)


@pytest.mark.parametrize('page,digest', [
    ('department', '0e31466263ac1d8813e41c65c3f35d8fc73c7727fb88f69ef45b2568150b9c10'),
    ('employee', 'fa7cd09d3bfc7ccd264a3889d3f533cb7631f55f00eff1b98fa48320e54f7b9d'),
    ('warehouse', '61e97a7e5d65bf8918f015aae9a67dfb5d034b6fd345d1843d1126531efb9655')])
def test_page_assets_preserve_script_and_load_once(page, digest):
    source = page_source(page)
    assert source.count(f"filename='js/pages/{page}.js'") == 1
    assert "?v={{ config.get('STATIC_VERSION', '1.0.0') }}" in source
    assert not any(body.strip() for body in re.findall(r'<script[^>]*>(.*?)</script>', source, re.S))
    asset = (ROOT / f'app/static/js/pages/{page}.js').read_text(encoding='utf-8')
    assert '{{' not in asset and '{%' not in asset
    assert hashlib.sha256(asset.strip().encode()).hexdigest() == digest


class Controls(HTMLParser):
    def __init__(self, text):
        super().__init__(); self.nodes = {}; self.forms = {}; self.current = None
        self.feed(text)
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.nodes[a["id"]] = {"tag": tag, **a}
        if tag == "form":
            self.current = a.get("id")
            if self.current:
                self.forms[self.current] = []
        if self.current and tag in ["input", "select", "textarea"]:
            self.forms[self.current].append(a)
    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


@pytest.mark.parametrize("page", PAGES)
def test_master_data_has_one_transport_and_prompt_style(page):
    text = page_source(page)
    scripts = page_scripts(page)
    assert not re.search(r"(?<![\w.])fetch\s*\(", scripts)
    assert not re.search(r"(?<![\w.])(?:alert|confirm)\s*\(", scripts)
    assert "WMS.api.postRaw(" in scripts


CASES = [(page, action) for page in PAGES for action in ["add", "edit", "import"]]
CASES += [("department", "deleteDepartment"), ("employee", "deleteEmployee"), ("employee", "batchDelete"), ("warehouse", "deleteWarehouse"), ("warehouse", "setDefaultWarehouse")]


@pytest.mark.parametrize("page,action", CASES)
@pytest.mark.parametrize("scenario", ["success", "failure", "cancel"])
def test_master_data_transport_runtime(page, action, scenario):
    if scenario == "cancel" and action in ["add", "edit", "import"]:
        pytest.skip("forms have no extra confirmation")
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required")
    text = page_source(page); controls = Controls(text)
    scripts = page_scripts(page)
    app_source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    helper_start = app_source.index('function escapeHtml(')
    helper = app_source[helper_start:app_source.index('\n}', helper_start) + 2]
    helper += '\n' + shared_helpers()
    payload = {"helper": helper, "page": page, "action": action, "scenario": scenario, "nodes": controls.nodes, "forms": controls.forms, "source": scripts, "api": (ROOT / "app/static/js/api.js").read_text(encoding="utf-8")}
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);
let ready=[],requests=[],messages=[],nativeAlerts=0,nativeConfirms=0,reloads=0,confirmCalls=0;
function field(a={}){return Object.assign({value:'7',checked:true,files:[{name:'audit.xlsx'}],dataset:{id:'7'},style:{},innerHTML:'',disabled:false,handlers:{},options:[{value:'',disabled:false}],classList:{add(){},remove(){}},addEventListener(t,fn){this.handlers[t]=fn;},checkValidity:()=>true,reportValidity(){},reset(){},getAttribute(k){return this[k]||'';},focus(){},select(){}},a);}
const nodes={};Object.entries(p.nodes).forEach(([id,a])=>nodes[id]=field({...a,value:'7'}));
Object.entries(p.forms).forEach(([id,fields])=>{if(!nodes[id])return;const items=fields.map(a=>{const f=a.id&&nodes[a.id]||field(a);if(a.type==='file')f.files=[{name:'audit.xlsx'}];return f;});items.forEach(f=>{if(f.name)items[f.name]=f;});nodes[id].elements=items;nodes[id].querySelector=s=>{const m=s.match(/name=["']?([^"'\]]+)/);return m&&items[m[1]]||items.find(x=>s.includes('file')&&x.type==='file')||field();};nodes[id].action=nodes[id].action||'/audit-import';});
const importResult=field();
const meta={content:'fixture-token',getAttribute:()=> 'fixture-token'};
const document={getElementById:id=>nodes[id]||null,addEventListener:(t,fn)=>{if(t==='DOMContentLoaded')ready.push(fn);},querySelector:s=>s.startsWith('meta')?meta:s.includes('.import-result')?importResult:field(),querySelectorAll:()=>[field({value:'7'}),field({value:'8'})]};
class FormData{constructor(form){this.owner=form&&form.id;this.rows=Array.from(form&&form.elements||[]).filter(f=>f.name).map(f=>[f.name,f.value]);}append(k,v){this.rows.push([k,v]);}get(k){const row=this.rows.find(r=>r[0]===k);return row?row[1]:null;}}
const ctx={document,FormData,Headers,URLSearchParams,Promise,console,location:{search:'',origin:'http://test',reload(){reloads++;}},
 setTimeout(){},initCheckAll(){},initTableActions(){},getSelectedIds:()=>[7,8],showToast:(m,t)=>messages.push({m,t}),showConfirm:()=>{confirmCalls++;return Promise.resolve(p.scenario!=='cancel');},
 alert(){nativeAlerts++;},confirm(){nativeConfirms++;return p.scenario!=='cancel';},CustomEvent:class{},dispatchEvent(){},addEventListener(){},localStorage:{setItem(){}},
 bootstrap:{Modal:class{show(){} hide(){} static getInstance(){return {hide(){}};}}},
 fetch:(url,options={})=>{requests.push({url,options});const failed=p.scenario==='failure';return Promise.resolve({ok:!failed,status:failed?400:200,json:()=>Promise.resolve({status:failed?'error':'success',msg:failed?'fixture failure':'fixture success',category:{id:7,code:'C',name:'cat'},supplier:{id:7},customer:{id:7},unit:{id:7},employee:{id:7},department:{id:7},warehouse:{id:7}})});}};
ctx.window=ctx;ctx.parent=ctx;vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);ready.forEach(fn=>fn());
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const id=p.action==='import'?(p.page==='customer'?'importCustomerForm':p.page==='supplier'?'importSupplierForm':'importForm'):p.action==='add'?'addForm':'editForm';
 if(['add','edit','import'].includes(p.action)){
  const form=nodes[id];assert(form,'missing fixture form '+id);
  if(form.handlers.submit)form.handlers.submit.call(form,{preventDefault(){}});
  else {const name={add:'submitAdd',edit:'submitEdit',import:'submitImport'}[p.action];assert.equal(typeof ctx[name],'function',name);ctx[name]();}
 } else {assert.equal(typeof ctx[p.action],'function');await ctx[p.action](7);}
 await flush();await flush();
 assert.equal(nativeAlerts,0,'use the common toast');assert.equal(nativeConfirms,0,'use the common asynchronous confirmation');
 if(p.scenario==='cancel'){assert.equal(confirmCalls,1);assert.equal(requests.length,0);return;}
 assert.equal(requests.length,1,'one user action must send one request');
 const req=requests[0];assert.equal(req.options.method,'POST');assert.equal(new Headers(req.options.headers).get('X-CSRFToken'),'fixture-token');
 if(['add','edit','import'].includes(p.action)){assert(req.options.body instanceof FormData,'preserve multipart payload');assert.equal(req.options.body.owner,id);}
 else if(p.page==='employee'){const body=JSON.parse(req.options.body);assert.deepEqual(body.ids,p.action==='batchDelete'?['7','8']:[7]);}
 if(p.scenario==='success')assert(!messages.some(x=>x.t==='danger'),'successful operations must not show an error toast');
 if(p.scenario==='failure'){assert.equal(reloads,0);assert(messages.some(x=>x.m.includes('fixture failure'))||importResult.innerHTML.includes('fixture failure'),'show structured API error');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, "-e", program, json.dumps(payload)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
