"""Execute real completion handlers against deferred responses and fake buttons."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
HANDLERS = [('in_order_detail', 'completeOrder'), ('out_order_detail', 'completeOrder'),
    ('after_sale_out', 'completeOrder'), ('after_sale_out_detail', 'completeOrder'),
    ('purchase_request', 'completeOrder'), ('purchase_request_detail', 'completeOrder'),
    ('subcontract_issue', 'completeIssue'), ('subcontract_receive', 'completeReceive'),
    ('adjustment_add', 'completeAdjustment')]


def _function(source, name):
    start = re.search(r'(?:async )?function '+name+r'\(', source).start()
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError('function does not close')


@pytest.mark.parametrize('page,name', HANDLERS)
@pytest.mark.parametrize('scenario', ['pending', 'cancel', 'failure', 'warning'])
def test_completion_busy_state(page, name, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / ('app/templates/'+page+'.html')).read_text(encoding='utf-8')
    helper = ROOT / 'app/static/js/document-action.js'
    payload = dict(function=re.sub(r'\{\{.*?\}\}', '0', _function(source, name)),
        submit=_function(source, 'submitForm') if page == 'adjustment_add' else '',
        helper=helper.read_text(encoding='utf-8') if helper.exists() else '',
        bound='data-document-action="'+name+'"' in source, name=name, scenario=scenario,
        supports_force=page in ['in_order_detail', 'out_order_detail'], adjustment=page == 'adjustment_add')
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(process.argv[1]);let requests=[],releases=[],confirms=0,errors=[];
const button=(disabled=false)=>({disabled,attrs:{},getAttribute(k){return this.attrs[k]??null;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}});
const buttons=[button(),button(),button(true)];
const fields={date:{value:'2026-10-21'},warehouse_id:{value:'2'},order_id:{value:''},
  adjustment_no:{value:'AD-7'},adjustment_type:{value:'increase'},remark:{value:''}};
const document={querySelectorAll:selector=>!p.bound?[]:(p.adjustment?(selector.includes('submitAdjustment')?[buttons[1]]:[buttons[0],buttons[2]]):buttons),
 querySelector:selector=>{const name=selector.match(/\[name="([^"]+)"\]/);return name?fields[name[1]]:buttons[1];}};
function confirm(){confirms++;return p.scenario!=='cancel';}
function request(url,raw){const data={status:p.scenario==='warning'?'warning':'success',anomalies:[],id:7};requests.push(url);
 if(p.adjustment && /\/complete$/.test(url))return Promise.resolve(raw?data:{json:()=>Promise.resolve(data)});
 return new Promise((resolve,reject)=>releases.push(()=>p.scenario==='failure'?reject(new Error('offline')):resolve(raw?data:{json:()=>Promise.resolve(data)})));}
const ctx={document,Promise,confirm,showConfirm:()=>Promise.resolve(confirm()),_showConfirm:()=>Promise.resolve(confirm()),
  showToast:(msg)=>errors.push(msg),_showToast:(msg)=>errors.push(msg),alert:()=>{},
  csrfFetch:url=>request(url,false),fetch:url=>request(url,false),
  $:{post:(url,callback)=>request(url,true).then(callback)},
  setTimeout:()=>{},location:{reload:()=>{}},showAnomalyWarning:()=>{},readonly:false,
  collectItems:()=>({invalidRows:[],items:[{material_id:1,quantity:2}]})};
ctx.window=ctx;ctx.WMS={api:{postRaw:url=>request(url,true)}};
vm.createContext(ctx);if(p.helper)vm.runInContext(p.helper,ctx);if(p.submit)vm.runInContext(p.submit,ctx);vm.runInContext(p.function,ctx);
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
  const first=ctx[p.name](7,false);const second=ctx[p.name](7,false);await flush();
  if(p.scenario==='cancel') {await Promise.all([first,second]);assert.equal(requests.length,0);}
  else {
    assert.equal(requests.length,1,'a second click must not send another completion request');
    assert.equal(confirms,1,'do not queue another confirmation');
    assert.equal(buttons[0].disabled,true);assert.equal(buttons[0].getAttribute('aria-busy'),'true');
    releases[0]();await Promise.all([first,second]);await flush();
  }
  assert.equal(buttons[0].disabled,false);assert.equal(buttons[1].disabled,false);
  assert.equal(buttons[2].disabled,true,'keep pre-existing disabled state');
  assert.equal(buttons[0].getAttribute('aria-busy'),null);
  if(p.scenario==='failure') assert(errors.some(msg=>msg.includes('offline')));
  const before=requests.length;const force=p.supports_force && p.scenario==='warning';
  const retry=ctx[p.name](7,force);await flush();
  if(p.scenario!=='cancel'){assert.equal(requests.length,before+1);releases.at(-1)();}
  if(force)assert(requests.at(-1).endsWith('?force=true'));
  await retry;await flush();
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', script, json.dumps(payload)], capture_output=True,
                            text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
