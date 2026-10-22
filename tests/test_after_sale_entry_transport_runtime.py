"""Rendered roles, actual validation/save callbacks and production API; no live data."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

from jinja2 import DictLoader, Environment, FileSystemLoader, ChoiceLoader
import pytest

ROOT = Path(__file__).resolve().parents[1]


def render_page(role='warehouse', location=True, edit=False):
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '<body class="{% block body_class %}{% endblock %}">{% block content %}{% endblock %}{% block extra_js %}{% endblock %}</body>'}),
        FileSystemLoader(str(ROOT / 'app/templates')),
    ]))
    order = SimpleNamespace(location='A-01', customer='fixture', source_sales_order_id=17,
                            source_out_order_id=18) if edit else None
    return env.get_template('after_sale_out_add.html').render(
        current_user=SimpleNamespace(role=role), location_management_enabled=location,
        csrf_token=lambda: 'fixture-csrf', url_for=lambda *a, **kw: '/static/' + kw.get('filename', ''), config={}, order=order, order_id=7 if edit else None,
        order_no='ASO-FIXTURE', order_date='2026-10-22', materials=[], units=[], customers=[],
        initial_items=[], warehouses=[{'id': 2, 'name': 'fixture warehouse'}],
        default_warehouse={'id': 2},
    )


def function(source, name):
    start = source.index('function ' + name + '(')
    if source[max(0, start - 6):start] == 'async ':
        start -= 6
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(name)


class Tags(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'sales', 'production', 'finance', 'viewer', 'user'])
@pytest.mark.parametrize('edit', [False, True])
def test_rendered_roles_protect_whole_form_and_embedded_toolbar(role, edit):
    tags = Tags(render_page(role=role, edit=edit)).tags
    writable = role in ('admin', 'warehouse')
    assert any(tag == 'button' and attr.get('onclick') == 'submitForm()' for tag, attr in tags) == writable
    fieldset = next(attr for tag, attr in tags if tag == 'fieldset' and attr.get('id') == 'afterSaleOutFields')
    assert ('disabled' in fieldset) == (not writable)
    assert any(tag == 'a' and attr.get('href') == '/after_sale_out' for tag, attr in tags)
    body = next(attr for tag, attr in tags if tag == 'body')
    assert ('wms-no-global-actionbar' in body['class'].split()) == (not writable)
    if not writable:
        run_callback('readonly', role=role, edit=edit)


@pytest.mark.parametrize('edit', [False, True])
@pytest.mark.parametrize('location', [False, True])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_json', 'html', 'invalid_json', 'null', '401', '419', 'network', 'validation'])
def test_actual_save_and_validation_payloads(edit, location, scenario):
    run_callback(scenario, location=location, edit=edit)


def run_callback(scenario, role='warehouse', location=True, edit=False):
    html = render_page(role, location, edit)
    names = ['clearAfterSaleOutValidation', 'collectAfterSaleOutRows', 'collectAfterSaleOutErrors',
             'showAfterSaleOutValidation', 'focusAfterSaleOutError', 'submitForm']
    prefix = '\n'.join(re.findall(r'(?:const canEditAfterSaleOut = [^;]+;|let afterSaleOutSaveBusy = false;)', html))
    script = prefix + '\n' + '\n'.join(function(html, name) for name in names)
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario,resolveRequest,href='original';const sent=[],messages=[],timers=[];
const fields={order_id:p.edit?'7':'',order_no:'ASO-FIXTURE',date:'2026-10-22',customer:'fixture customer',contact:'fixture contact',phone:'123',warehouse_id:'2',reason:'fixture reason',source_sales_order_id:'17',source_out_order_id:'18',responsibility:'fixture responsibility',remark:'fixture header remark'};
if(p.location)fields.location='A-01';
const classList={add(){},remove(){}},inputs={};
for(const [name,value] of Object.entries(fields))inputs[name]={value,tagName:'INPUT',type:'text',classList,getAttribute:k=>k==='name'?name:null,closest:()=>null};
const rowValues={'.material-code':'MAT-FIXTURE','.material-qty':'2','.material-price':'3.50','.material-remark':'fixture line remark'};
const row={classList,querySelector:s=>({value:rowValues[s]})};
const required=['date','customer','warehouse_id',...(p.location?['location']:[])].map(k=>inputs[k]);
if(mode==='validation')inputs.customer.value='';
const buttons=[{disabled:false},{disabled:true}];
const panel={classList,scrollIntoView(){}},list={innerHTML:'',children:[]};
const doc={getElementById:id=>id==='afterSaleOutValidationPanel'?panel:id==='afterSaleOutValidationList'?list:null,
 querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:inputs[s.match(/name="([^"]+)"/)?.[1]]||null,
 querySelectorAll:s=>s==='#materialTableBody tr'?[row]:s==='#addForm [required]'?required:s.includes('button[')?buttons:s.includes('name=')?[inputs[s.match(/name="([^"]+)"/)[1]]]:[]};
const ctx={Headers,FormData,document:doc,escapeHtml:s=>String(s).replace(/</g,'&lt;'),showToast:(m,t)=>messages.push({m,t}),confirm:()=>false,
location:{get href(){return href;},set href(value){href=value;}},setTimeout:(fn,delay)=>timers.push({fn,delay}),
fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>resolveRequest=()=>{
 if(mode==='network'){reject(Error('offline fixture'));return;}
 const status=mode==='http_json'?409:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
 const body=mode==='null'?null:{status:['business','http_json'].includes(mode)?'error':'success',msg:'specific server reason',id:9};
 resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});
})}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const first=ctx.submitForm();await flush();
 if(['readonly','validation'].includes(mode)){assert.equal(sent.length,0);assert.equal(href,'original');if(mode==='validation')assert(list.innerHTML.includes('customer'));return;}
 assert.equal(sent.length,1);assert(buttons.every(b=>b.disabled));await ctx.submitForm();assert.equal(sent.length,1,'repeat save cannot create duplicate');
 const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.u,'/after_sale_out/add');assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('Content-Type'),'application/json');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
 assert.deepEqual(JSON.parse(req.o.body),{...fields,location:p.location?'A-01':'',items:[{code:'MAT-FIXTURE',quantity:2,price:3.5,remark:'fixture line remark'}]});
 resolveRequest();await first;await flush();
 if(mode==='success'){
  assert.equal(messages.at(-1).t,'success');assert.equal(href,'original');assert.equal(timers.length,1);assert.equal(timers[0].delay,400);
  await ctx.submitForm();assert.equal(sent.length,1,'navigation delay remains locked');timers[0].fn();assert.equal(href,'/after_sale_out/9');
 }else{
  assert.equal(href,'original');assert.equal(messages.at(-1).t,'danger');assert.equal(timers.filter(t=>t.delay===400).length,0);assert.deepEqual(buttons.map(b=>b.disabled),[false,true]);
  if(['business','http_json'].includes(mode))assert(messages.at(-1).m.includes('specific server reason'));if(mode==='html')assert(messages.at(-1).m.includes('503'));
  mode='success';const retry=ctx.submitForm();await flush();resolveRequest();await retry;assert.equal(sent.length,2);assert.equal(messages.at(-1).t,'success');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    run_node(program, dict(script=script, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
                           scenario=scenario, role=role, location=location, edit=edit))


def test_actual_global_actionbar_honors_rendered_optout():
    html = render_page(role='finance')
    classes = next(attrs['class'] for tag, attrs in Tags(html).tags if tag == 'body').split()
    source = function((ROOT / 'app/static/js/app.js').read_text(encoding='utf-8'), 'insertGlobalActionBar')
    run_node(r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(fs.readFileSync(0,'utf8'));
const ctx={isWmsEmbeddedPage:()=>true,document:{getElementById:()=>null,body:{classList:{contains:s=>p.classes.includes(s)}}},getWmsActionModule:()=>{throw Error('must opt out before global writes are injected');}};
vm.createContext(ctx);vm.runInContext(p.source,ctx);ctx.insertGlobalActionBar();
''', dict(source=source, classes=classes))


def run_node(program, payload):
    node = shutil.which('node')
    assert node, 'Node required for actual DOM callback verification'
    completed = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True,
                               encoding='utf-8', timeout=15)
    assert completed.returncode == 0, completed.stderr
