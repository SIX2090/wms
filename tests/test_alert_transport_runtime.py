"""Actual alert DOM callbacks and production HTTP client, with isolated role rendering."""
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader
import pytest
from utils import format_quantity

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'app/templates/alert.html'


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'sales', 'production', 'finance', 'viewer', 'user'])
def test_alert_write_buttons_follow_backend_roles(role):
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}',
                    '_list_macros.html': '{% macro sort_th(a,b,c,d) %}<th>{{ a }}</th>{% endmacro %}'}),
        FileSystemLoader(str(ROOT / 'app/templates')),
    ]))
    env.filters['quantity'] = format_quantity
    html = env.get_template('alert.html').render(
        current_user=SimpleNamespace(role=role), csrf_token=lambda: 'isolated-token',
        request=SimpleNamespace(args={}),
        filters=SimpleNamespace(search='', status='', category_id=0, supplier_id=0, warehouse_id=0),
        warehouses=[], categories=[], suppliers=[], alert_materials=[], current_warehouse=None,
    )
    for button in ('batchUpdateAlertBtn', 'disableAlertBtn', 'batchMinStock', 'batchSafetyStock'):
        assert (f'id="{button}"' in html) == (role in ('admin', 'warehouse'))
    assert 'id="clearAlertSelectionBtn"' in html
    assert 'id="alertTable"' in html


@pytest.mark.parametrize('action', ['set', 'disable'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http_json', 'html', 'invalid_json', 'null', 'primitive', '401', '419', 'network', 'cancel', 'empty'])
def test_alert_actual_callbacks(action, scenario):
    script = re.search(r'<script>(.*?)</script>', PAGE.read_text(encoding='utf-8'), re.S)[1]
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8'));
let mode=p.scenario, confirms=0,reloads=0,resolveRequest,resolveConfirm;
const sent=[],messages=[],timers=[],handlers={};
const nodes={batchUpdateAlertBtn:{disabled:false,innerHTML:'set original'},disableAlertBtn:{disabled:false,innerHTML:'disable original'},
 batchMinStock:{value:'2.50'},batchSafetyStock:{value:'5'},selectedAlertCount:{},clearAlertSelectionBtn:{}};
for(const [id,node] of Object.entries(nodes))node.addEventListener=(event,fn)=>handlers[id+':'+event]=fn;
const rows=[{value:'7',addEventListener(){}},{value:'8',addEventListener(){}}];
const ctx={Headers,FormData,Event,document:{addEventListener:(event,fn)=>fn(),
 getElementById:id=>nodes[id],querySelector:s=>s.includes('meta')?{content:'fixture-csrf'}:null,
 querySelectorAll:s=>s.includes(':checked')?(mode==='empty'?[]:rows):rows},initCheckAll(){},
 showToast:(m,t)=>messages.push({m,t}),showConfirm:()=>{confirms++;return new Promise(r=>resolveConfirm=r);},
 confirm:()=>false,location:{href:'original',reload(){reloads++;}},setTimeout:(fn,delay)=>timers.push({fn,delay}),
 fetch:(u,o)=>{sent.push({u,o});return new Promise((resolve,reject)=>resolveRequest=()=>{
  if(mode==='network'){reject(Error('offline'));return;}
  const status=mode==='http_json'?400:mode==='html'?503:['401','419'].includes(mode)?Number(mode):200;
  const body=mode==='null'?null:mode==='primitive'?'invalid':{status:['business','http_json'].includes(mode)?'error':'success',msg:'fixture explanation'};
  resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(mode)?Promise.reject(SyntaxError('bad JSON')):Promise.resolve(body)});
 })}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const key=p.action==='set'?'batchUpdateAlertBtn':'disableAlertBtn',node=nodes[key],original=node.innerHTML;
const click=()=>handlers[key+':click'].call(node),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const first=click();await flush();
 if(mode==='empty'){assert.equal(confirms,0);assert.equal(sent.length,0);assert.equal(messages.at(-1).t,'warning');return;}
 assert.equal(confirms,1);assert(node.disabled,'confirmation must lock button');
 await click();await flush();assert.equal(confirms,1,'repeat during confirmation must be ignored');
 resolveConfirm(mode!=='cancel');await flush();
 if(mode==='cancel'){await first;assert.equal(sent.length,0);assert.equal(node.disabled,false);assert.equal(node.innerHTML,original);return;}
 assert.equal(sent.length,1);await click();assert.equal(sent.length,1,'repeat pending write must be ignored');
 const req=sent[0],headers=new Headers(req.o.headers);
 assert.equal(req.u,'/alert/batch_update_thresholds');assert.equal(req.o.method,'POST');
 assert.equal(req.o.credentials,'same-origin');assert.equal(headers.get('X-CSRFToken'),'fixture-csrf');
 assert.equal(headers.get('X-Requested-With'),'XMLHttpRequest');assert.equal(headers.get('Content-Type'),'application/json');
 assert.deepEqual(JSON.parse(req.o.body),p.action==='set'?{ids:['7','8'],min_stock:'2.50',safety_stock:'5'}:{ids:['7','8'],action:'disable'});
 resolveRequest();await first;await flush();
 if(mode==='success'){
  assert.equal(messages.at(-1).t,'success');assert.equal(reloads,0);assert.equal(timers.length,1);assert.equal(timers[0].delay,700);
  await click();assert.equal(sent.length,1,'success refresh window must remain locked');
  timers[0].fn();assert.equal(reloads,1);
 }else{
  assert.equal(messages.at(-1).t,'danger');assert.equal(timers.filter(t=>t.delay===700).length,0);assert.equal(reloads,0);assert.equal(ctx.location.href,'original');
  assert.equal(node.disabled,false);assert.equal(node.innerHTML,original);
  if(['business','http_json'].includes(mode))assert(messages.at(-1).m.includes('fixture explanation'));
  if(mode==='html')assert(messages.at(-1).m.includes('503'));
  mode='success';const retry=click();await flush();resolveConfirm(true);await flush();resolveRequest();await retry;
  assert.equal(sent.length,2);assert.equal(messages.at(-1).t,'success');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for real alert callback checks'
    completed = subprocess.run([node, '-e', program], input=json.dumps({
        'script': script, 'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
        'action': action, 'scenario': scenario,
    }), encoding='utf-8', capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr
