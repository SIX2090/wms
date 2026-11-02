"""Execute both actual detail handlers: anomaly consent is the final consent."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from tests.test_document_action_busy import _function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('direction', ['in', 'out'])
@pytest.mark.parametrize('scenario', ['success', 'cancel', 'network', 'hidden'])
def test_anomaly_consent_does_not_repeat_the_completion_confirmation(direction, scenario):
    source = (ROOT / f'app/templates/{direction}_order_detail.html').read_text(encoding='utf-8')
    handlers = '\n'.join(_function(source, name) for name in
                         ('completeOrder', 'forceCompleteOrder', 'closeAnomalyModal'))
    handlers = re.sub(r'\{\{.*?\}\}', '0', handlers)
    payload = dict(direction=direction, scenario=scenario, handlers=handlers,
                   lock=(ROOT / 'app/static/js/document-action.js').read_text(encoding='utf-8'))
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
let confirmations=0,requests=[],pending=[],errors=[],warnings=0;
const modal={style:{display:'none'},dataset:{}};
const btn={disabled:false,attrs:{},getAttribute(k){return this.attrs[k]??null;},
 setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}};
const confirm=()=>{confirmations++;return Promise.resolve(p.scenario!=='cancel');};
const ctx={document:{querySelectorAll:()=>[btn],getElementById:()=>modal},
 showConfirm:confirm,_showConfirm:confirm,showToast:m=>errors.push(m),_showToast:m=>errors.push(m),
 setTimeout(){},location:{reload(){}},showAnomalyWarning:(a,id)=>{warnings++;modal.dataset.orderId=id;modal.style.display='flex';}};
ctx.window=ctx;ctx.WMS={api:{postRaw:url=>{requests.push(url);return new Promise((resolve,reject)=>pending.push({resolve,reject}));}}};
vm.createContext(ctx);vm.runInContext(p.lock+'\n'+p.handlers,ctx);
const flush=async()=>{for(let n=0;n<4;n++)await new Promise(r=>setImmediate(r));};
(async()=>{
 if(p.scenario==='hidden'){await ctx.forceCompleteOrder();await flush();assert.equal(requests.length,0);assert.equal(confirmations,0);return;}
 const initial=ctx.completeOrder(7,false);ctx.completeOrder(7,false);await flush();
 assert.equal(confirmations,1);
 if(p.scenario==='cancel'){await initial;assert.equal(requests.length,0);assert.equal(btn.disabled,false);return;}
 assert.equal(requests.length,1);assert(!requests[0].includes('force'));
 pending.shift().resolve({status:'warning',anomalies:[{msg:'same complete content'}]});await initial;await flush();
 assert.equal(warnings,1);assert.equal(btn.disabled,false);
 const forced=ctx.forceCompleteOrder();ctx.forceCompleteOrder();await flush();
 assert.equal(confirmations,1,'the anomaly confirmation is already explicit completion consent');
 assert.equal(requests.length,2,'double consent click must send only one forced request');
 assert.equal(requests[1],'/'+p.direction+'_order/7/complete?force=true');
 assert.equal(btn.disabled,true);
 if(p.scenario==='network')pending.shift().reject(Error('offline'));else pending.shift().resolve({status:'success'});
 await forced;await flush();assert.equal(btn.disabled,false);
 if(p.scenario==='network')assert(errors.some(m=>m.includes('offline')));
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for real detail-handler regression'
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True,
                            text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
