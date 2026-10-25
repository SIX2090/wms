"""Execute page error guards and preserve manual acknowledgement before reload."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function(page, name):
    source = (ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf-8')
    start = source.index('function ' + name + '(')
    if source[max(0, start - 6):start] == 'async ':
        start -= 6
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return re.sub(r'{{.*?}}', '/fixture/0/action', source[start:end + 1])
    raise AssertionError(name)


CASES = [
    ('in_order_add', 'showInOrderValidation', 'guard'),
    ('subcontract_issue', 'removeItemRow', 'guard'),
    ('subcontract_receive', 'removeItemRow', 'guard'),
    ('print_routing', 'addWs', 'guard'),
    ('print_routing', 'saveRule', 'guard'),
    ('print_routing', 'addWs', 'token'),
    ('print_routing', 'resetToken', 'token'),
    ('print_routing', 'resetToken', 'cancel'),
    ('approval', 'approveItem', 'business'),
    ('approval', 'rejectItem', 'business'),
] + [(page, name, mode) for page, name in [
    ('ai_business_quality', 'loadSnapshot'),
    ('ai_demand_forecast', 'generateForecast'),
    ('ai_location_recommendation', 'generateRecommendation'),
    ('label_template', 'deleteTemplate'),
    ('label_template', 'setDefault'),
] for mode in ['business', 'network']] + [
    ('wechat_share', name, 'network') for name in [
        'saveWechatShareConfig', 'runWechatShareNow',
        'resendWechatShareLog', 'clearWechatShareLogs',
    ]
] + [(page, 'showToast', 'literal') for page in [
    'in_order_print_template', 'out_order_print_template',
]]


@pytest.mark.parametrize('page,name,mode', CASES)
def test_page_feedback_behavior(page, name, mode):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    payload = dict(page=page, name=name, mode=mode, source=function(page, name),
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    if page == 'ai_demand_forecast':
        template = (ROOT / 'app/templates/ai_demand_forecast.html').read_text(encoding='utf-8')
        payload['source'] = '\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', template, re.S))
        shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
        start = shared.index('function escapeHtml(')
        payload['escape'] = shared[start:shared.index('\n}', start) + 2]
    if page == 'wechat_share':
        payload['source'] = 'let wechatShareWriteBusy = false;\n' + function(page, 'writeWechatShare') + '\n' + payload['source']
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const messages=[],events=[],calls=[],timers=[],elements=[];
const marker='<img src=x onerror="throw 1"> & fixture';
const fields=new Proxy({}, {get:(o,k)=>o[k]||(o[k]={value:p.mode==='guard'?'':'1',checked:true,style:{},classList:{add(){},remove(){}}})});
const doc={getElementById:id=>p.name==='showInOrderValidation'?null:fields[id],createElement:()=>{const e={style:{},remove(){events.push('remove');}};Object.defineProperty(e,'innerHTML',{set(){throw Error('unsafe HTML');}});return e;},body:{appendChild:e=>elements.push(e)}};
const response={ok:true,status:200,json:()=>Promise.resolve({status:'error',msg:marker})};
function transport(url,opts){calls.push({url,opts});return p.mode==='network'?Promise.reject(Error(marker)):Promise.resolve(response);}
const ctx={document:doc,JSON,parseInt,selectedMaterialId:7,getFilters:()=>({}),FormData:class {append(){}},
  showToast:(m,t)=>messages.push({m,t}),alert:m=>events.push(['alert',m]),confirm:()=>p.mode!=='cancel',prompt:()=> 'manual reason',
  navigator:{clipboard:{writeText:()=>Promise.resolve()}},location:{reload:()=>events.push('reload')},
  fetch:transport,csrfFetch:transport,setTimeout:(fn,ms)=>timers.push(fn),
  WMS:{api:{post:(url,data)=>{calls.push({url,data});return Promise.resolve({token:'fixture-token',msg:'ok'});}}},
  $:()=>({length:1,val:()=> '7',show(){},hide(){},closest(){throw Error('must not delete last row');}})};
ctx.window=ctx;vm.createContext(ctx);
if(p.page==='ai_demand_forecast'){
  fields.forecastDays.value='7';fields.categoryFilter.value='';
  ctx.$=target=>{
    if(target===doc)return {ready(fn){fn();}};
    const element=fields[String(target).replace(/^#/,'')];
    const query={length:1,val:()=>element.value,on(){return query;},prop(name,value){element[name]=value;return query;},
      show(){element.style.display='block';return query;},hide(){element.style.display='none';return query;}};
    return query;
  };
  vm.runInContext(p.escape,ctx);
}
if(p.page==='label_template'||p.page==='approval'||p.page==='wechat_share'||p.page==='ai_demand_forecast'){
  ctx.WMS={};doc.querySelector=()=>({content:'fixture-csrf'});
  if(p.page==='wechat_share')doc.querySelectorAll=()=>[];
  vm.runInContext(p.api,ctx);
}
vm.runInContext(p.source,ctx);
(async()=>{
  let args=[1];if(p.name==='showInOrderValidation')args=[[{message:marker}]];
  if(p.mode==='literal')args=[marker,'danger'];
  await ctx[p.name](...args);await new Promise(r=>setImmediate(r));
  if(p.mode==='literal'){
    assert.equal(elements.length,1);assert.equal(elements[0].textContent,marker);assert.match(elements[0].style.cssText,/dc3545/);
    timers.forEach(fn=>fn());assert.deepEqual(events,['remove']);return;
  }
  if(p.mode==='token'){
    const index=events.findIndex(e=>Array.isArray(e)&&e[0]==='alert');assert.ok(index>=0);assert.ok(events[index][1].includes('fixture-token'));
    assert.equal(events[index+1],'reload','token must be acknowledged before reload');assert.equal(calls.length,1);return;
  }
  if(p.mode==='cancel'){assert.equal(calls.length,0);assert.deepEqual(events,[]);return;}
  assert.equal(events.length,0,'errors must neither block with alert nor reload');
  assert.equal(messages.length,1);assert.ok(['danger','warning'].includes(messages[0].t),'errors cannot be styled as success');
  if(p.page==='ai_demand_forecast'){
    assert.equal(calls.length,1,'forecast error handling must execute the real request');
    assert.equal(calls[0].url,'/api/ai/demand_forecast');assert.equal(calls[0].opts.method,'POST');
    assert.equal(calls[0].opts.headers['X-CSRFToken'],'fixture-csrf');
    assert.deepEqual(JSON.parse(calls[0].opts.body),{forecast_days:7,category:''});
    assert.equal(fields.generateForecastBtn.disabled,false);assert.equal(fields.loadingArea.style.display,'none');
    assert.equal(fields.resultArea.style.display,'none','failed predictions stay hidden');
  }
  if(p.mode==='guard'){assert.equal(calls.length,0);return;}
  if(!['deleteTemplate','setDefault'].includes(p.name)||p.mode==='network')assert.ok(messages[0].m.includes(marker),'preserve original error text');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
