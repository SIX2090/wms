"""Run reachable contract/requisition actions, and exclude obsolete local bindings."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ['contract_import', 'contract_add', 'contract_edit', 'contract_delete', 'contract_batch', 'req_revert', 'req_delete', 'req_complete']
CASES = [(a, s) for a in ACTIONS for s in ['success', 'business', 'http', 'html', 'invalid_json', 'null', 'invalid_body', 'expired401', 'expired419', 'network']]
CASES += [(a, 'cancel') for a in ['contract_delete', 'contract_batch', 'req_revert', 'req_delete', 'req_complete']]
CASES += [('contract_batch', 'empty')]


def action_source(action):
    if action.startswith('contract_'):
        name = dict(contract_import='submitImport', contract_add='submitAdd', contract_edit='submitEdit', contract_delete='deleteContract', contract_batch='batchDelete')[action]
        return callback('contract', 'function ' + name + '('), name
    source = (ROOT / 'app/templates/requisition.html').read_text(encoding='utf-8')
    marker = "document.querySelectorAll('." + {'req_revert':'revert-btn', 'req_delete':'delete-btn', 'req_complete':'complete-btn'}[action] + "')"
    offset = source.index(".addEventListener('click'", source.index(marker))
    return 'var probe = ' + callback('requisition', 'function()', offset), 'probe'


@pytest.mark.parametrize('action,scenario', CASES)
def test_contract_requisition_actions_preserve_payload_notifications_and_continue(action, scenario):
    handler, name = action_source(action)
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    escape = re.search(r'function escapeHtml\(value\) \{.*?\n\}', app, re.S).group()
    helpers = callback('contract', 'function notifyMasterDataChanged(') + '\n' + callback('requisition', 'function urlWithId(') + '\n' + callback('requisition', 'function buildRequisitionContinueUrl(')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let sent=[],messages=[],timers=[],reloads=0,channels=[],closed=0,confirms=0;let scenario=p.scenario;
const fields={id:'7',contract_no:'C-7',project_name:'项目 & + 中文',status:'active',remark:'备注\n中 &+'};
class FormData{constructor(form){this.owner=form.id;this.fields=new Map(Object.entries(fields));}get(k){return this.fields.get(k);}}
class BroadcastChannel{constructor(name){assert.equal(name,'wms_master_data_update');}postMessage(m){channels.push(m);}close(){closed++;}}
const result={innerHTML:''};const ctx={FormData,Headers,URLSearchParams,BroadcastChannel,document:{querySelector:s=>s.includes('csrf-token')?{content:'fixture-csrf'}:result,querySelectorAll:()=>p.scenario==='empty'?[]:[{value:'7'},{value:'8'}],getElementById:id=>({id})},
showToast:(m,t)=>messages.push({m,t}),showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},confirm:m=>{if(m.includes('登录'))return false;confirms++;return p.scenario!=='cancel';},setTimeout:fn=>timers.push(fn),location:{href:'original',reload(){reloads++;}},
requisitionUrls:{add:'/requisition/add',complete:'/requisition/0/complete',revert:'/requisition/0/revert',delete:'/requisition/0/delete'},
fetch:(u,o)=>{sent.push({u,o});const status=scenario==='http'?400:scenario==='html'?503:scenario==='expired401'?401:scenario==='expired419'?419:200;
const body=scenario==='null'?null:scenario==='invalid_body'?'unexpected response':{status:['business','http'].includes(scenario)?'error':'success',msg:'<img src=x onerror=attack()> fixture explanation',id:17};
return scenario==='network'?Promise.reject(Error('offline')):Promise.resolve({ok:status===200,status,json:()=>['html','invalid_json'].includes(scenario)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(body)});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.escape+'\n'+p.helpers+'\n'+p.handler,ctx);
const button={dataset:{id:'7',warehouse:'A & B',bomId:'9',productionOrder:'工单 +1',picker:'张三',purpose:'组装'}};
async function invoke(){ctx[p.name].call(button,7);await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();
if(['cancel','empty'].includes(p.scenario)){assert.equal(sent.length,0);assert.equal(reloads,0);assert.equal(channels.length,0);return;}
assert.equal(sent.length,1);const req=sent[0],h=new Headers(req.o.headers);assert.equal(req.o.method,'POST');assert.equal(req.o.credentials,'same-origin');assert.equal(h.get('X-CSRFToken'),'fixture-csrf');assert.equal(h.get('X-Requested-With'),'XMLHttpRequest');
const urls={contract_import:'/contract/import',contract_add:'/contract/add',contract_edit:'/contract/7/edit',contract_delete:'/contract/7/delete',contract_batch:'/contract/delete',req_revert:'/requisition/7/revert',req_delete:'/requisition/7/delete',req_complete:'/requisition/7/complete'};assert.equal(req.u,urls[p.action]);
if(['contract_import','contract_add','contract_edit'].includes(p.action)){assert(req.o.body instanceof FormData);assert.equal(req.o.body.owner,{contract_import:'importForm',contract_add:'addForm',contract_edit:'editForm'}[p.action]);assert(!h.has('Content-Type'));assert.deepEqual(Object.fromEntries(req.o.body.fields),fields);}
if(p.action==='contract_batch')assert.deepEqual(JSON.parse(req.o.body),{ids:[7,8]},'retain numeric contract IDs');
if(['contract_delete','contract_batch','req_revert','req_delete','req_complete'].includes(p.action))assert.equal(confirms,1);
const notify=['contract_add','contract_edit','contract_delete','contract_batch'].includes(p.action);
if(p.scenario==='success'){
 assert.equal(channels.length,notify?1:0);assert.equal(closed,notify?1:0);if(notify){assert.equal(channels[0].type,'contract_updated');assert.equal(typeof channels[0].timestamp,'number');}
 if(p.action==='contract_import'){assert(result.innerHTML.includes('alert-success'));assert(result.innerHTML.includes('&lt;img'));assert(!result.innerHTML.includes('<img'));}else assert(messages.some(m=>m.t==='success'));
 timers.forEach(fn=>fn());if(p.action==='req_complete'){assert.equal(reloads,0);const u=new URL(ctx.location.href,'http://fixture');assert.equal(u.pathname,'/requisition/add');assert.deepEqual(Object.fromEntries(u.searchParams),{warehouse:'A & B',bom_id:'9',production_order:'工单 +1',picker:'张三',purpose:'组装'});}else assert.equal(reloads,1);
}else{
 assert.equal(reloads,0);assert.equal(ctx.location.href,'original');assert.equal(channels.length,0,'failed changes must not broadcast');
 if(p.action==='contract_import'){assert(result.innerHTML.includes('alert-danger'));assert(!result.innerHTML.includes('<img'));}else assert(messages.some(m=>m.t==='danger'));
 if(['business','http'].includes(p.scenario)){if(p.action==='contract_import')assert(result.innerHTML.includes('fixture explanation'));else assert(messages.some(m=>m.m.includes('fixture explanation')));}
 if(p.scenario==='html'){if(p.action==='contract_import')assert(result.innerHTML.includes('503'));else assert(messages.some(m=>m.m.includes('503')));}
 scenario='success';await invoke();assert.equal(sent.length,2);assert.equal(channels.length,notify?1:0);
 if(p.action==='contract_import')assert(result.innerHTML.includes('alert-success'));else assert.equal(messages.at(-1).t,'success');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for actual callback verification'
    payload = dict(action=action, scenario=scenario, handler=handler, name=name, helpers=helpers, escape=escape, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


class Entries(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.ids, self.classes = set(), set()
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.ids.add(attrs.get('id'))
        self.classes.update(attrs.get('class', '').split())


def test_requisition_keeps_real_routes_and_removes_unreachable_request_bindings():
    source = (ROOT / 'app/templates/requisition.html').read_text(encoding='utf-8')
    entries = Entries(source)
    assert {'complete-btn', 'revert-btn', 'delete-btn'} <= entries.classes
    assert 'openAddModal' not in entries.ids and 'edit-order-btn' not in entries.classes
    assert 'batchDeleteBtn' not in entries.ids
    assert "orderForm?.addEventListener('submit'" not in source
    assert "getElementById('batchDeleteBtn')?.addEventListener" not in source
    assert "url_for('requisition_detail', id=requisition.id)" in source
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    assert "addUrl: '/requisition/add'" in app
    assert "deleteUrl: '/requisition/batch_delete'" in app
    assert not re.search(r'(?<![\w.])(?:fetch|csrfFetch)\s*\(', source)
