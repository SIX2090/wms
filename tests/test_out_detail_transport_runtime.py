"""Run outbound-detail callbacks with production transport; no business endpoints are mocked as implemented."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_frontend_remaining_page_transport import callback

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ['inline', 'deleteDetail', 'batch', 'revert', 'deleteOrder', 'copyOrder', 'header', 'paste', 'add', 'deleteToolbar', 'cell']
CONFIRMED = ['deleteDetail', 'batch', 'revert', 'deleteOrder', 'copyOrder', 'deleteToolbar']


def handler_for(action):
    source = (ROOT / 'app/templates/out_order_detail.html').read_text(encoding='utf-8')
    names = dict(inline='saveInlineMaterialRow', deleteDetail='deleteDetailMaterialRow', revert='revertOrder', deleteOrder='deleteOrder', copyOrder='copyOrder', header='saveHeader', paste='processBatchPaste', add='addItem')
    if action in names:
        return callback('out_order_detail', 'function ' + names[action] + '(')
    if action == 'cell':
        return callback('out_order_detail', 'function(itemId, field, newValue, formData)')
    if action == 'batch':
        offset = source.index("getElementById('batchDeleteBtn')")
    else:
        offset = source.index("btn.addEventListener('click'", source.index("querySelectorAll('.toolbar-btn-danger[data-id]')"))
    return callback('out_order_detail', 'function()', offset)


CASES = [(a,s) for a in ACTIONS for s in ['success','business','http','html','malformed','expired401','expired419','network']]
CASES += [('batch','null'), ('batch','mixed_null')]
CASES += [(a,'cancel') for a in CONFIRMED]
CASES += [(a,'empty') for a in ['inline','batch','header','paste','add']]
CASES += [('copyOrder','success_fallback'), ('copyOrder','success_parent'), ('deleteOrder','success_parent')]


@pytest.mark.parametrize('action,scenario', CASES)
def test_out_detail_payload_feedback_recovery(action, scenario):
    node = shutil.which('node')
    assert node, 'Node required for the real outbound detail HTTP runtime regression'
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let requests=[],messages=[],reloads=0,confirms=0,sessionPrompts=0,opened=[],responseScenario=p.scenario,cellResult,cellError;
const field=v=>({value:v,disabled:false,dataset:{id:'7'},focus(){},classList:{contains:()=>false}});
const nodes={code:field('中文&M/1'),qty:field('2.5'),price:field('3.2'),batchPasteContent:field('中文&M/1\t2.5\t备注'),editHeaderForm:{id:'editHeaderForm'}};
const inlineFields={'.material-code-field':field('中文&M/1'),'.material-qty-field':field('2.5'),'.material-price-field':field('3.2'),'.material-remark-field':field('备注&A/东')};
const row={dataset:{id:'7'},classList:{contains:()=>false},querySelector:q=>inlineFields[q]};const button={disabled:false,dataset:{id:'7'},closest:()=>row};
const header={date:p.scenario==='empty'?'':'2026-10-22',warehouse_id:'2',location:'东&A/位',picker:'领料人',purpose:'用途',remark:'单头备注'};
class FormData {constructor(form){this.rows=form?Object.entries(header):[];}append(k,v){this.rows.push([k,String(v)]);}entries(){return this.rows.values();}get(k){return this.rows.find(x=>x[0]===k)?.[1]??null;}}
const cellForm=new FormData();cellForm.append('id','7');cellForm.append('field','remark');cellForm.append('value','新备注&A');
const document={getElementById:id=>nodes[id],querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null,querySelectorAll:()=>p.scenario==='empty'?[]:[{value:'7'},{value:'8'}]};
const ctx={document,FormData,Headers,Promise,console,parseFloat,encodeURIComponent,Object,
_showToast:(m,t)=>messages.push({m,t}),_showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>{sessionPrompts++;return false;},setTimeout:(fn,ms)=>{if(ms!==5000)fn();},location:{href:'original',reload(){reloads++;}},
fetch:(url,options)=>{requests.push({url,options});const nullResponse=responseScenario==='null'||(responseScenario==='mixed_null'&&requests.length%2===0);const status=responseScenario==='http'?409:responseScenario==='html'?503:responseScenario==='expired401'?401:responseScenario==='expired419'?419:200;return responseScenario==='network'?Promise.reject(Error('offline')):Promise.resolve({status,ok:status===200,json:()=>['html','malformed'].includes(responseScenario)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(nullResponse?null:{status:['business','http'].includes(responseScenario)?'error':'success',msg:'fixture explanation',data:{status:'error',msg:'do not unwrap'},id:17,order_no:'OUT-17',redirect_url:responseScenario==='success_fallback'?undefined:'/out_order/17?copied=1'})});}};
ctx.window=ctx;if(p.scenario==='success_parent')ctx.parent={WmsTabs:{open:(u,t)=>opened.push({u,t})}};vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var handler='+p.handler+';',ctx);
if(p.scenario==='empty'){nodes.code.value='';nodes.batchPasteContent.value='';inlineFields['.material-code-field'].value='';}
async function invoke(){cellError=null;if(p.action==='cell'){try{cellResult=await ctx.handler(7,'remark','新备注&A',cellForm);}catch(e){cellError=e;}}else await ctx.handler.call(button,p.action==='inline'?button:p.action==='deleteDetail'?row:7);await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();const a=p.action;
if(['cancel','empty'].includes(p.scenario)){assert.equal(requests.length,0);assert.equal(reloads,0);assert.equal(button.disabled,false);return;}
const count=a==='batch'?2:1;assert.equal(requests.length,count);
const {url,options}=requests[0];assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'fixture-token');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');
if(['inline','add','cell'].includes(a)){assert(options.body instanceof FormData);assert.equal(options.headers['Content-Type'],undefined);if(a==='cell'){assert.equal(options.body,cellForm);assert.equal(options.body.get('value'),'新备注&A');}else{assert.equal(options.body.get('material_code'),'中文&M/1');assert.equal(options.body.get('quantity'),'2.5');assert.equal(options.body.get('price'),'3.2');if(a==='inline')assert.equal(options.body.get('remark'),'备注&A/东');}}
if(['header','paste','copyOrder'].includes(a)){const data=JSON.parse(options.body);assert.equal(options.headers['Content-Type'],'application/json');assert.deepEqual(data,a==='header'?header:a==='paste'?{content:'中文&M/1\t2.5\t备注'}:{});}
if(a==='batch'){assert(requests[0].url.endsWith('/7'));assert(requests[1].url.endsWith('/8'));}
if(CONFIRMED.has(a))assert.equal(confirms,1);
if(['null','mixed_null'].includes(p.scenario)){assert.equal(messages.length,1,'batch completion must fire exactly once');assert.equal(messages[0].t,'warning','null is a failed item, not a second completion');assert.equal(reloads,1);responseScenario='success';await invoke();assert.equal(requests.length,4);assert.equal(messages.at(-1).t,'success');assert.equal(reloads,2);return;}
if(p.scenario.startsWith('success')){if(a==='cell'){assert.equal(cellResult.status,'success');assert.equal(cellResult.data.status,'error');}else{assert(messages.some(m=>m.t==='success'));if(['copyOrder','deleteOrder'].includes(a)){if(p.scenario==='success_parent')assert.equal(opened.length,1);else assert.equal(ctx.location.href,a==='deleteOrder'?'/out_order':p.scenario==='success_fallback'?'/out_order/17':'/out_order/17?copied=1');}else assert.equal(reloads,1);}}
else {if(a==='cell'){if(p.scenario==='business')assert.equal(cellResult.status,'error');else assert(cellError);}else{assert(messages.some(m=>['danger','warning'].includes(m.t)));if(a!=='batch'){assert.equal(reloads,0);if(['business','http'].includes(p.scenario))assert(messages.some(m=>m.m.includes('fixture explanation')));}assert.equal(ctx.location.href,'original');if(a==='inline')assert.equal(button.disabled,false);}if(p.scenario.startsWith('expired'))assert.equal(sessionPrompts,1);
responseScenario='success';await invoke();assert.equal(requests.length,count*2,'errors must leave action available for retry');if(a==='cell')assert.equal(cellResult.status,'success');else assert.equal(messages.at(-1).t,'success');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    program = program.replace('CONFIRMED.has(a)', 'new Set(' + json.dumps(CONFIRMED) + ').has(a)')
    result = subprocess.run([node,'--max-old-space-size=64','-e',program],
                            input=json.dumps(dict(action=action,scenario=scenario,handler=handler_for(action),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),
                            capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_outbound_only_non_get_requests_migrated():
    source=(ROOT/'app/templates/out_order_detail.html').read_text(encoding='utf-8')
    assert 'csrfFetch(' not in source
    assert source.count('WMS.api.postRaw(')==12  # 11 migrated plus existing completion.
    # Material lookup now shares HTTP/session validation; the endpoint stays unchanged.
    assert "WMS.api.getRaw('/api/material/search?kw='" in source
    assert "fetch('/api/material/search?kw='" not in source
    assert "fetch('/api/ai/out_order/{{ order.id }}/anomaly_analysis'" in source


@pytest.mark.parametrize('role', ['admin','warehouse','viewer','purchase'])
@pytest.mark.parametrize('business_type', ['领料单','其他出库','销售出库','采购退货出库'])
def test_batch_paste_toolbar_role_and_source_gates(role, business_type):
    from html.parser import HTMLParser
    from types import SimpleNamespace
    from jinja2 import Environment

    source=(ROOT/'app/templates/out_order_detail.html').read_text(encoding='utf-8')
    marker=source.index('onclick="showBatchPasteModal()"')
    # Render the actual production button including its immediately preceding Jinja assignments.
    start=source.rfind('{% set batch_paste_source_restricted', 0, marker)
    if start < 0:
        start=source.rfind('<button', 0, marker)
    fragment=source[start:source.index('</button>',marker)+len('</button>')]
    html=Environment(autoescape=True).from_string(fragment).render(
        order=SimpleNamespace(business_type=business_type),current_user=SimpleNamespace(role=role))
    class Buttons(HTMLParser):
        def __init__(self):
            super().__init__();self.buttons=[]
        def handle_starttag(self, tag, attrs):
            if tag=='button':self.buttons.append(dict(attrs))
    parsed=Buttons();parsed.feed(html)
    assert len(parsed.buttons)==1
    button=parsed.buttons[0]
    source_restricted=business_type in ['销售出库','采购退货出库']
    allowed=role in ['admin','warehouse'] and not source_restricted
    assert ('disabled' not in button)==allowed
    if source_restricted:
        assert '维护来源' in button['title'] and '整单编辑' in button['title']
    elif not allowed:
        assert button['title']=='当前账号无批量添加权限'
    else:
        assert 'title' not in button
