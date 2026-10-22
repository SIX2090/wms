"""BUG-2026-10-22-006: load both page scripts and exercise their real initializers."""
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
ATTACK = '</script><img src=x onerror="globalThis.injected=1">中文&\'"'


def render_scripts(page, edit=False, location=False, value=ATTACK):
    source = (ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf-8')
    if page == 'opening_stock':
        source = source.split('{% block extra_js %}', 1)[1].split('{% endblock %}', 1)[0]
    row = SimpleNamespace(line_id=11, material_id=7, warehouse_id=2, warehouse_name=value,
                          material_code='M001', material_name=value, spec='', unit='pc',
                          quantity=3, price=2, remark=value, location='A01')
    context = dict(config={'STATIC_VERSION': 'test-v1'}, csrf_token=lambda: 'token',
                   url_for=lambda _endpoint, filename: '/static/' + filename,
                   prefix=value if page == 'print_template_editor' else 'in_order', template_id=42,
                   template_label=value, template_name=value, is_default=False,
                   editing_doc=SimpleNamespace(id=9, doc_no=value, date=datetime.date(2026, 10, 22), warehouse_id=2) if edit else None,
                   warehouses=[SimpleNamespace(id=2, code='WH02', name=value)],
                   location_management_enabled=location, edit_rows=[row] if edit else [])
    return Environment(autoescape=True).from_string(source).render(**context)


def node_run(payload, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(process.argv[1]),els=new Map(),events={},calls=[],messages=[];
function el(id='') {return {id,innerHTML:'',textContent:'',value:'',style:{},dataset:{},hidden:true,tagName:'INPUT',
 children:[],classList:{add(){},remove(){},toggle(){}},addEventListener(n,f){this[n]=f;},
 appendChild(c){this.children.push(c);},querySelectorAll(){return [];},querySelector(){return el();},
 focus(){},remove(){},contains(){return false;},getAttribute(){return null;}};}
const document={getElementById(id){if(!els.has(id))els.set(id,el(id));return els.get(id);},
 querySelectorAll(){return [];},createElement(){const n=el();let html;Object.defineProperty(n,'innerHTML',{get(){return html===undefined?n.textContent.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'):html;},set(v){html=v;}});return n;},addEventListener(n,f){events[n]=f;},body:el(),activeElement:null};
const api={get(url){calls.push({method:'GET',url});return Promise.resolve({sheets:[{name:'Sheet1',max_row:1,max_col:1,cells:[{row:1,col:1,value:'old'}]}],context:{}});},
 post(url,data){calls.push({method:'POST',url,data});return Promise.resolve({status:'error',msg:'test'});}};
const window={document,WMS:{api},addEventListener(n,f){events[n]=f;},location:{href:'',reload(){}},print(){calls.push({method:'PRINT'});}};
const storage=new Map();
const ctx={window,document,WMS:window.WMS,structuredClone,setTimeout:()=>1,clearTimeout(){},console,
 localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 showToast:(m,t)=>messages.push(m),confirm:()=>false,
 escapeHtml:v=>String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')};
vm.createContext(ctx);
for(const inline of p.inline)vm.runInContext(inline,ctx);
assert.equal(ctx.injected,undefined);
for(const filename of p.files)vm.runInContext(fs.readFileSync(filename,'utf8'),ctx,{filename});
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 if(p.page==='opening_stock'){
  document.getElementById('headerWarehouse').value='2';document.getElementById('headerDocDate').value='2026-10-22';
  events.DOMContentLoaded();
  assert.equal(vm.runInContext('DRAFT_SCOPE',ctx),p.edit?'9':'new');
  assert.equal(vm.runInContext('warehouseOptions[0].name',ctx),'WH02 - '+p.value);
  if(p.edit){
   assert(document.getElementById('openingGridBody').innerHTML.includes('&lt;/script&gt;'));
   assert.equal(vm.runInContext('amountOf(rows[0])',ctx),6);
   vm.runInContext("updateField(0,'quantity',4);saveDocument();",ctx);
   assert.equal(calls[0].url,'/opening_stock/save');assert.equal(calls[0].data.doc_id,9);
   assert.equal(calls[0].data.items[0].quantity,4);assert.equal(calls[0].data.items[0].location,'A01');
   assert.equal(calls[0].data.items[0].warehouse_id,2);
  } else {vm.runInContext('saveDocument()',ctx);assert.equal(calls.length,0);assert(messages.includes('请至少录入一行期初库存'));}
  assert.equal(vm.runInContext('GRID_COLSPAN',ctx),p.location?13:12);
 } else {
  await flush();await flush();
  assert.equal(window.__PRINT_EDITOR_CONFIG__.prefix,p.value);
  assert.equal(calls[0].url,'/'+p.value+'_print_template/42/grid');
  assert.equal(window.__tplEditor.getS().rows[0].cells[0].t,'old');
  assert(document.getElementById('gridTable').innerHTML.includes('old'));
  assert(document.getElementById('pageStyle').textContent.includes('@page{size:210mm 297mm'));
  window.__tplEditor.getS().rows[0].cells[0].t='新内容';document.getElementById('btnSave').onclick();
  await flush();assert.equal(calls[1].method,'POST');assert.equal(calls[1].url,calls[0].url);
  assert.equal(calls[1].data.sheets[0].upserts[0][2],'新内容');
  document.getElementById('btnDoPrint').onclick();assert.equal(calls.at(-1).method,'PRINT');
 }
 assert.equal(ctx.injected,undefined);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    env = dict(os.environ, NODE_OPTIONS='--max-old-space-size=64')
    result = subprocess.run([node, '-e', script, json.dumps(payload)], capture_output=True,
                            encoding='utf-8', timeout=20, env=env)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('edit', [False, True])
@pytest.mark.parametrize('location', [False, True])
def test_opening_real_script_bootstrap(edit, location):
    run_page('opening_stock', edit=edit, location=location)


@pytest.mark.parametrize('value', ['in_order', ATTACK])
def test_print_editor_real_load_edit_save_and_print(value):
    run_page('print_template_editor', value=value)


def run_page(page, edit=False, location=False, value=ATTACK):
    html = render_scripts(page, edit=edit, location=location, value=value)
    scripts = re.findall(r'<script\b([^>]*)>([\s\S]*?)</script>', html)
    inline = [body for attrs, body in scripts if not re.search(r'\bsrc=', attrs)]
    page_files = []
    config_index = None
    file_index = None
    for index, (attrs, body) in enumerate(scripts):
        if ('__OPENING_DOC__' in body or '__PRINT_EDITOR_CONFIG__' in body):
            config_index = index
        filename = re.search(r'/static/(js/pages/[^?"\']+)', attrs)
        if filename:
            file_index = index
            assert '?v=test-v1' in attrs
            assert 'async' not in attrs and 'type="module"' not in attrs
            page_files.append(str(ROOT / 'app/static' / filename.group(1)))
    assert len(page_files) == 1, 'Business code must be linked as a cacheable external script'
    assert config_index < file_index, 'Server data must exist before business script executes'
    assert all('function ' not in body for body in inline), 'Inline scripts may only inject configuration'
    assert value not in ''.join(inline) if '<' in value else True
    node_run(dict(page=page, edit=edit, location=location, value=value, inline=inline, files=page_files), page)
