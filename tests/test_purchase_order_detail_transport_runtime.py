"""BUG-2026-10-22-014: execute reachable purchase detail actions and role gates."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from jinja2 import DictLoader, Environment

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ['createInOrder', 'closePurchaseOrder', 'reopenPurchaseOrder', 'deletePurchaseOrder', 'copyPurchaseOrder']


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'http_success', 'html', 'expired401', 'expired419', 'network', 'null'])
def test_real_detail_actions(action, scenario):
    run(action, scenario)


@pytest.mark.parametrize('action', ACTIONS)
def test_confirmation_cancel_sends_nothing(action):
    run(action, 'cancel')


def test_close_prompt_cancel_is_distinct_from_blank_reason():
    run('closePurchaseOrder', 'prompt_cancel')


@pytest.mark.parametrize('reason', ['', '  ', '原值 中文 & = +'])
def test_close_preserves_prompt_value(reason):
    run('closePurchaseOrder', 'success', reason)


@pytest.mark.parametrize('scenario', ['empty', 'zero', 'over', 'nan'])
def test_invalid_receipt_selection_never_posts(scenario):
    run('createInOrder', scenario)


@pytest.mark.parametrize('action', ['createInOrder', 'copyPurchaseOrder'])
def test_redirect_fallback(action):
    run(action, 'fallback')


@pytest.mark.parametrize('embedded', [False, True])
@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'viewer', 'production', 'sales', 'finance'])
@pytest.mark.parametrize('status', ['pending', 'partial', 'closed', 'completed'])
def test_real_jinja_role_status_buttons(role, status, embedded):
    from html.parser import HTMLParser
    class Buttons(HTMLParser):
        def __init__(self):
            super().__init__(); self.actions = []; self.ids = []; self.body_classes = []
        def handle_starttag(self, tag, attrs):
            props = dict(attrs)
            if tag == 'body':
                self.body_classes = props.get('class', '').split()
            if tag == 'button' and 'onclick' in props:
                self.actions.append(props['onclick'].split('(')[0])
            if 'id' in props:
                self.ids.append(props['id'])
    source = (ROOT / 'app/templates/purchase_order_detail.html').read_text(encoding='utf-8')
    body_slot = next(line for line in (ROOT / 'app/templates/base.html').read_text(encoding='utf-8').splitlines() if line.startswith('<body class='))
    env = Environment(loader=DictLoader({'base.html': body_slot + '{% block content %}{% endblock %}</body>', '_list_macros.html': '{% macro operation_log_card(logs) %}{% endmacro %}', 'page': source}), autoescape=True)
    order = SimpleNamespace(id=7, status=status, order_no='PO-7', date=None, supplier=None, operator=None, expected_date=None, total_amount=0, purchase_request=None, contract_no='', project_name='', remark='', created_at=None, items=[])
    html = env.get_template('page').render(request=SimpleNamespace(args={'embedded': '1'} if embedded else {}), order=order, current_user=SimpleNamespace(role=role), related_in_orders=[], warehouses=[], item_execution={}, operation_logs=[], status_label=lambda s:s, url_for=lambda name, **kw: '/'+name)
    parsed = Buttons(); parsed.feed(html)
    purchase = role in ('admin', 'purchase')
    receiving = role in ('admin', 'purchase', 'warehouse') and status in ('pending', 'partial')
    for action, expected in [('copyPurchaseOrder', purchase), ('deletePurchaseOrder', purchase and status == 'pending'), ('closePurchaseOrder', purchase and status in ('pending', 'partial')), ('reopenPurchaseOrder', purchase and status == 'closed'), ('createInOrder', receiving)]:
        assert (action in parsed.actions) == expected, (role, status, action, parsed.actions)
    assert ('warehouse' in parsed.ids) == receiving
    assert ('embedded-page' in parsed.body_classes) == embedded
    assert ('wms-no-global-actionbar' in parsed.body_classes) == (not purchase)
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    assert "if (document.body.classList.contains('wms-no-global-actionbar')) return;" in shared
    assert ('href="/purchase_order_edit_page"' in html) == (purchase and status == 'pending')


def run(action, scenario, reason='  原值 中文&=+  '):
    source = (ROOT / 'app/templates/purchase_order_detail.html').read_text(encoding='utf-8')
    for name in ACTIONS:
        assert f'onclick="{name}(' in source, 'Only test actions reachable from actual markup'
    script = '\n'.join(re.findall(r'<script\b[^>]*>([\s\S]*?)</script>', source))
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
let requests=[],messages=[],timers=[],reloads=0,confirmations=0,scenario=p.scenario,focused=0;
const rows=[{checked:true,dataset:{itemId:'11'}},{checked:true,dataset:{itemId:'12'}}];
const quantities={11:{value:scenario==='zero'?'0':scenario==='over'?'6':scenario==='nan'?'NaN':'2',getAttribute:()=> '5',focus(){focused++;},addEventListener(){}},12:{value:'1',getAttribute:()=> '3',focus(){focused++;},addEventListener(){}}};
const fields={warehouse:{value:'仓库A'},inRemark:{value:'备注 中文 & +'},receiveSelectionSummary:{textContent:''},selectAllReceiveItems:{checked:false}};
const document={querySelector:s=>s.includes('csrf-token')?{content:'detail-csrf'}:quantities[(s.match(/data-item-id="(\d+)"/)||[])[1]],
querySelectorAll:s=>s==='.receive-qty'?Object.values(quantities):scenario==='empty'?[]:rows,getElementById:id=>fields[id],addEventListener(){}};
class FormData{}
const ctx={document,FormData,Headers,location:{href:'original',reload(){reloads++;}},prompt:()=>scenario==='prompt_cancel'?null:p.reason,
confirm:()=>true,showConfirm:()=>{confirmations++;return Promise.resolve(scenario!=='cancel');},showToast:(m,t)=>messages.push({m,t}),setTimeout:(f,ms)=>{timers.push({f,ms});},
fetch:(url,options)=>{requests.push({url,options});const status=['http','http_success'].includes(scenario)?400:scenario==='html'?503:scenario==='expired401'?401:scenario==='expired419'?419:200;
return scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({status,ok:status===200,json:()=>scenario==='html'?Promise.reject(SyntaxError('HTML')):Promise.resolve(scenario==='null'?null:['business','http'].includes(scenario)?{status:'error',msg:'server reason'}:{status:'success',msg:'ok',id:99,redirect_url:scenario==='fallback'?undefined:'/draft/99',data:{id:'wrong-unwrapped'}})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.script,ctx);
const flush=()=>new Promise(r=>setImmediate(r));
async function invoke(){await ctx[p.action](7);await flush();await flush();}
(async()=>{
 await invoke();
 if(['cancel','prompt_cancel','empty','zero','over','nan'].includes(scenario)){
  assert.equal(requests.length,0);assert.equal(timers.length,0);assert.equal(reloads,0);
  if(scenario==='prompt_cancel')assert.equal(confirmations,0,'prompt cancellation must not become a close confirmation');
  if(['zero','over','nan'].includes(scenario))assert.equal(focused,1);
  return;
 }
 assert.equal(requests.length,1);const first=requests[0],h=new Headers(first.options.headers);
 const names={createInOrder:'create_in_order',closePurchaseOrder:'close',reopenPurchaseOrder:'reopen',deletePurchaseOrder:'delete',copyPurchaseOrder:'copy'};
 assert.equal(first.url,'/purchase_order/7/'+names[p.action]);assert.equal(first.options.method,'POST');assert.equal(first.options.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'detail-csrf');
 if(p.action==='createInOrder')assert.deepEqual(JSON.parse(first.options.body),{warehouse:'仓库A',remark:'备注 中文 & +',items:[{item_id:'11',quantity:2},{item_id:'12',quantity:1}]});
 else if(p.action==='closePurchaseOrder')assert.deepEqual(JSON.parse(first.options.body),{reason:p.reason});
 else if(p.action!=='reopenPurchaseOrder')assert.deepEqual(JSON.parse(first.options.body),{});
 if(['success','fallback'].includes(scenario)){
  assert.equal(timers.length,1);assert.equal(timers[0].ms,500);assert.equal(ctx.location.href,'original');timers[0].f();
  if(['closePurchaseOrder','reopenPurchaseOrder'].includes(p.action))assert.equal(reloads,1);
  else if(p.action==='deletePurchaseOrder')assert.equal(ctx.location.href,'/purchase_order');
  else assert.equal(ctx.location.href,scenario==='fallback'?(p.action==='createInOrder'?'/in_order/99':'/purchase_order/99/edit'):'/draft/99');
 }else{
  assert.equal(timers.length,0);assert.equal(reloads,0);assert(messages.some(x=>x.t==='danger'));
  if(['business','http'].includes(scenario))assert(messages.some(x=>x.m.includes('server reason')));
  if(scenario==='html')assert(messages.some(x=>x.m.includes('503')));
  if(scenario.startsWith('expired'))assert.equal(ctx.location.href,'/login');
  scenario='success';await invoke();assert.equal(requests.length,2);assert.equal(timers.length,1,'failure allows retry');
 }
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node'); assert node, 'Node required'
    env = dict(os.environ, NODE_OPTIONS='--max-old-space-size=64')
    result = subprocess.run([node,'-e',program,json.dumps(dict(action=action,scenario=scenario,reason=reason,script=script,api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8')))],capture_output=True,encoding='utf-8',env=env,timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
