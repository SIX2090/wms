"""Execute active subcontract listeners and handlers through the real HTTP client."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ACTIONS = ['batchDelete', 'add', 'delete', 'revert', 'batchAction', 'import',
           'inlineProduct', 'addProductItem', 'deleteProduct', 'confirmIssue', 'confirmReceive',
           'deleteOrder', 'copyOrder', 'submitOrder', 'revertToPending', 'saveHeaderEdit']
CONFIRMED = {'batchDelete', 'delete', 'revert', 'batchAction', 'deleteProduct', 'deleteOrder', 'copyOrder', 'submitOrder', 'revertToPending'}


def source_for(action):
    page = 'subcontract' if ACTIONS.index(action) < 6 else 'subcontract_detail'
    text = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    source = '\n'.join(re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>', text, re.S))
    def expression(match):
        value = match[1]
        endpoint = re.search(r"url_for\('([^']+)'", value)
        if endpoint:
            return '/fixture/' + endpoint[1] + ('/0' if 'id=0' in value else '')
        return '[]' if 'materials|tojson' in value else 'true' if 'tojson' in value else '7'
    return re.sub(r'\{\{(.*?)\}\}', expression, source)


CASES = [(action, scenario) for action in ACTIONS for scenario in
         ['success', 'business', 'httpjson', 'html', 'malformed', 'unauthorized', 'expired', 'network']]
CASES += [(action, 'cancel') for action in ACTIONS if action in CONFIRMED]


@pytest.mark.parametrize('action,scenario', CASES)
def test_subcontract_transport_runtime(action, scenario):
    node = shutil.which('node')
    assert node, 'Node.js is required for the production transport runtime regression'
    payload = {'action': action, 'scenario': scenario, 'source': source_for(action),
               'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')}
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let requests=[],messages=[],alerts=[],reloads=0,confirms=0,trace=[],hidden=0;
function field(id,value='fixture'){return {id,value,checked:true,disabled:false,files:[{name:'audit.xlsx'}],dataset:{id:'7'},handlers:{},style:{},addEventListener(k,f){this.handlers[k]=f;},getAttribute(k){return k==='data-id'?'7':this[k];},focus(){},select(){},querySelector(){return null;}};}
const nodes=new Proxy({}, {get(o,k){if(!o[k])o[k]=field(k);return o[k];}});
for(const id of ['productCode','issueCode','receiveCode'])nodes[id].value='中文&A/1';
for(const id of ['productQty','issueQty','receiveQty'])nodes[id].value='2.5';
for(const id of ['issueLocation','receiveLocation'])nodes[id].value='东&A/位';
nodes.receivePrice.value='3.2';nodes.upload.value='chosen.xlsx';nodes.importForm.action='/fixture/import';
const checks=[field('check7','7'),field('check8','8')],del=field('delete'),rev=field('revert'),productDel=field('productDelete');
const document={getElementById:id=>nodes[id],addEventListener(){},querySelector:s=>s.startsWith('meta')?{content:'test-token'}:null,querySelectorAll:s=>s.startsWith('.itemCheck')?checks:s==='.delete-btn'?[del]:s==='.revert-btn'?[rev]:s==='.delProductBtn'?[productDel]:[]};
class FormData{constructor(form){this.rows=form?[['csrf_token','test-token'],['supplier_id','3'],['file','audit.xlsx']]:[];}append(k,v){this.rows.push([k,String(v)]);}get(k){return this.rows.find(x=>x[0]===k)?.[1]??null;}getAll(k){return this.rows.filter(x=>x[0]===k).map(x=>x[1]);}}
const ctx={document,FormData,Headers,Promise,URL,URLSearchParams,console,parseFloat,encodeURIComponent,
location:{href:'http://fixture/subcontract',reload(){trace.push('reload');reloads++;}},setTimeout(fn){fn();},clearTimeout(){},
showToast:(m,t)=>messages.push({m,t}),showConfirm:()=>{confirms++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>{confirms++;return p.scenario!=='cancel';},alert:m=>{assert.equal(reloads,0);trace.push('alert');alerts.push(m);},
bootstrap:{Modal:{getInstance:()=>({hide(){hidden++;}})}},
fetch:(url,options)=>{requests.push({url,options});if(p.scenario==='network')return Promise.reject(new Error('网络已断开'));const status=p.scenario==='httpjson'?409:p.scenario==='html'?502:p.scenario==='unauthorized'?401:p.scenario==='expired'?419:200;return Promise.resolve({status,ok:status<400,json:()=>['html','malformed'].includes(p.scenario)?Promise.reject(new Error('invalid JSON')):Promise.resolve(['business','httpjson'].includes(p.scenario)?{status:'error',msg:'业务拒绝'}:{status:'success',data:{status:'error',msg:'must not unwrap'},count:2,msg:'完整响应成功',redirect_url:'/draft/99'})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);
const row={querySelector:s=>s.includes('code')?field('code','中文&A/1'):field('qty','2.5')};
(async()=>{const a=p.action;if(a==='batchDelete')nodes.batchDeleteBtn.handlers.click();else if(a==='add')nodes.submitAdd.handlers.click();else if(a==='delete')del.handlers.click.call(del);else if(a==='revert')rev.handlers.click.call(rev);else if(a==='batchAction')ctx.batchAction('processing');else if(a==='import')ctx.submitDocumentImport('importForm','upload');else if(a==='inlineProduct')ctx.saveInlineProductRow(row);else if(a==='deleteProduct')productDel.handlers.click.call(productDel);else if(a==='saveHeaderEdit')ctx.saveHeaderEdit(7);else if(['confirmIssue','confirmReceive','addProductItem'].includes(a))ctx[a]();else ctx[a](7);
await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));
if(p.scenario==='cancel'){assert.equal(requests.length,0);assert.equal(reloads,0);return;}
assert.equal(requests.length,1);const {url,options}=requests[0];assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'test-token');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');
const form=options.body instanceof FormData;
if(['add','batchAction','import','inlineProduct','addProductItem','confirmIssue','confirmReceive'].includes(a)){assert(form);assert.equal(options.headers['Content-Type'],undefined);}
if(a==='batchDelete'){assert.deepEqual(JSON.parse(options.body),{ids:['7','8']});}
if(a==='batchAction'){assert.deepEqual(options.body.getAll('ids'),['7','8']);assert.equal(options.body.get('action'),'processing');}
if(['inlineProduct','addProductItem','confirmIssue','confirmReceive'].includes(a)){assert.equal(options.body.get('material_code'),'中文&A/1');assert.equal(options.body.get('quantity'),'2.5');}
if(['confirmIssue','confirmReceive'].includes(a))assert.equal(options.body.get('location'),'东&A/位');
if(a==='confirmReceive')assert.equal(options.body.get('price'),'3.2');
if(a==='saveHeaderEdit'){const data=JSON.parse(options.body);assert.equal(data.contact,'fixture');assert.equal(data.remark,'fixture');assert.equal(options.headers['Content-Type'],'application/json');}
if(a==='import'){assert.equal(options.body.get('file'),'audit.xlsx');assert.equal(nodes.upload.value,'');}
if(p.scenario==='success'){if(['batchDelete','add','delete','revert','batchAction','import'].includes(a)){assert.equal(alerts.length,1);assert.deepEqual(trace,['alert','reload']);}else{assert(messages.some(x=>x.t==='success'));assert(reloads>0||ctx.location.href!== 'http://fixture/subcontract');}if(a==='saveHeaderEdit')assert.equal(hidden,1);}
else{assert.equal(hidden,0);assert.equal(nodes.productCode.value,'中文&A/1');assert.equal(nodes.issueLocation.value,'东&A/位');assert.equal(reloads,0);assert.equal(ctx.location.href,['unauthorized','expired'].includes(p.scenario)?'/login':'http://fixture/subcontract');assert.equal(alerts.length,0);assert(messages.some(x=>x.t==='danger'&&x.m));if(['business','httpjson'].includes(p.scenario))assert(messages.some(x=>x.m.includes('业务拒绝')));if(['unauthorized','expired'].includes(p.scenario))assert(confirms>=1);}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '--max-old-space-size=64', '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_active_subcontract_pages_have_no_legacy_transport():
    for page in ['subcontract', 'subcontract_detail']:
        source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
        assert not re.search(r'\b(?:fetch|csrfFetch)\s*\(', source)
    assert sum(source_for(action).count('WMS.api.postRaw(') for action in ['batchDelete', 'addProductItem']) == 16
