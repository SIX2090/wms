"""Exercise reachable after-sale handlers with the production HTTP transport."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest
from tests.test_frontend_remaining_page_transport import callback

ROOT=Path(__file__).resolve().parents[1]
ACTIONS=[('after_sale_out','revertOrder'),('after_sale_out','deleteOrder'),('after_sale_out','submitDocumentImport'),
         ('after_sale_out_detail','revertOrder'),('after_sale_out_detail','copyOrder'),('after_sale_out_detail','deleteOrder')]
SCENARIOS=['success','business','http','html','invalid_json','null','primitive','expired401','expired419','network']
CASES=[(page,name,s) for page,name in ACTIONS for s in SCENARIOS]
CASES += [(page,name,'cancel') for page,name in ACTIONS if name!='submitDocumentImport']
CASES += [('after_sale_out','submitDocumentImport','empty'),('after_sale_out_detail','copyOrder','fallback'),('after_sale_out_detail','copyOrder','no_message')]


@pytest.mark.parametrize('page,name,scenario',CASES)
def test_after_sale_outcomes_payload_confirmation_and_retry(page,name,scenario):
    node=shutil.which('node')
    assert node,'Node required to execute actual after-sale callbacks'
    program=r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let sent=[],messages=[],timers=[],reloads=0,confirmed=0,expired=0,responseScenario=p.scenario;
const file={files:p.scenario==='empty'?[]:[{name:'after-sale.xlsx'}],value:'after-sale.xlsx',disabled:false},importButton={disabled:false},form={id:'afterSaleOutImportForm',action:'/after_sale_out/import'};
class FormData{constructor(owner){this.owner=owner.id;this.fields=[['csrf_token','fixture-csrf'],['file','after-sale.xlsx']];}}
const ctx={FormData,Headers,Promise,console,document:{querySelector:()=>({content:'fixture-csrf'}),getElementById:id=>id==='afterSaleOutImportFile'?file:id==='afterSaleOutImportFileButton'?importButton:form},
showConfirm:()=>{confirmed++;return Promise.resolve(p.scenario!=='cancel');},confirm:()=>{expired++;return false;},showToast:(m,t)=>messages.push({m,t}),setTimeout:(fn,delay)=>timers.push({fn,delay}),location:{href:'original',reload(){reloads++;}},
fetch:(url,options)=>{sent.push({url,options});const s=responseScenario,status=s==='http'?409:s==='html'?503:s==='expired401'?401:s==='expired419'?419:200;if(s==='network')return Promise.reject(Error('offline'));
return Promise.resolve({status,ok:status===200,json:()=>['html','invalid_json'].includes(s)?Promise.reject(SyntaxError('invalid JSON')):Promise.resolve(s==='null'?null:s==='primitive'?'unexpected':{status:['business','http'].includes(s)?'error':'success',msg:s==='no_message'?undefined:'服务端结果说明',data:{status:'error',msg:'must not unwrap'},redirect_url:s==='fallback'?undefined:'/after_sale_out/19/edit'})});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext('var action='+p.handler,ctx);
async function invoke(){if(p.name==='submitDocumentImport')ctx.action('afterSaleOutImportForm','afterSaleOutImportFile');else ctx.action(7);await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));}
(async()=>{await invoke();if(['cancel','empty'].includes(p.scenario)){assert.equal(sent.length,0);assert.equal(reloads,0);return;}
assert.equal(sent.length,1);const {url,options}=sent[0];assert.equal(url,p.name==='submitDocumentImport'?'/after_sale_out/import':'/after_sale_out/7/'+(p.name==='copyOrder'?'copy':p.name==='deleteOrder'?'delete':'revert'));
assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'fixture-csrf');assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');
if(p.name==='submitDocumentImport'){assert(options.body instanceof FormData);assert.equal(options.body.owner,'afterSaleOutImportForm');assert.equal(options.headers['Content-Type'],undefined);assert.equal(file.value,'','file cleared after all outcomes');assert.equal(file.disabled,p.scenario==='success','success stays locked until refresh; failure restores input');assert.equal(importButton.disabled,p.scenario==='success');assert.equal(!!ctx.action.pending,p.scenario==='success');}else{assert.equal(confirmed,1);assert.equal(options.body,undefined);}
assert.equal(messages.length,1);assert(!messages[0].m.includes('undefined'));
if(['success','fallback','no_message'].includes(p.scenario)){assert.equal(messages[0].t,'success');if(p.name==='copyOrder')assert.equal(messages[0].m,p.scenario==='no_message'?'复制成功':'服务端结果说明');
const refresh=timers.filter(x=>x.delay!==5000);if(p.name==='submitDocumentImport'){assert.equal(refresh[0].delay,900);}else if(p.name==='copyOrder'||(p.page==='after_sale_out_detail'&&p.name==='deleteOrder')){assert.equal(refresh[0].delay,600);}else assert.equal(refresh.length,0);
refresh.forEach(x=>x.fn());if(p.name==='copyOrder'&&p.scenario!=='fallback')assert.equal(ctx.location.href,'/after_sale_out/19/edit');else if(p.page==='after_sale_out_detail'&&p.name==='deleteOrder')assert.equal(ctx.location.href,'/after_sale_out');else assert.equal(reloads,1);}
else{assert.equal(messages[0].t,'danger');assert.equal(reloads,0);assert.equal(ctx.location.href,'original');assert.equal(timers.filter(x=>x.delay!==5000).length,0);if(['business','http'].includes(p.scenario))assert(messages[0].m.includes('服务端结果说明'));if(p.scenario==='html')assert(messages[0].m.includes('503'));if(p.scenario.startsWith('expired'))assert.equal(expired,1);
responseScenario='success';if(p.name==='submitDocumentImport')file.value='after-sale.xlsx';await invoke();assert.equal(sent.length,2);assert.equal(messages.at(-1).t,'success','failure permits a later retry');}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result=subprocess.run([node,'--max-old-space-size=64','-e',program],
        input=json.dumps(dict(page=page,name=name,scenario=scenario,handler=callback(page,('async ' if name=='submitDocumentImport' else '')+'function '+name+'('),api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))),
        capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


def test_only_reachable_after_sale_mutations_remain():
    sources=[(ROOT/f'app/templates/{page}.html').read_text(encoding='utf-8') for page in ['after_sale_out','after_sale_out_detail']]
    assert not any(re.search(r'\b(?:fetch|csrfFetch)\s*\(',s) for s in sources)
    assert sum(s.count('WMS.api.postRaw(') for s in sources)==8  # Six migrated plus two existing completions.
    assert 'function batchDelete(' not in sources[0]
    app=(ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    module=app[app.index('    after_sale_out: {'):app.index('    purchase_request:',app.index('    after_sale_out: {'))]
    assert "deleteUrl: '/after_sale_out/batch_delete'" in module


def test_preserved_after_sale_actions_have_real_dom_entries():
    class Attributes(HTMLParser):
        def __init__(self):super().__init__();self.attrs=[]
        def handle_starttag(self,tag,attrs):self.attrs.extend(attrs)
    for page in ['after_sale_out','after_sale_out_detail']:
        parsed=Attributes();parsed.feed((ROOT/f'app/templates/{page}.html').read_text(encoding='utf-8'))
        actions=' '.join(value or '' for name,value in parsed.attrs if name in ['onclick','onchange'])
        assert 'batchDelete(' not in actions
        assert 'revertOrder(' in actions and 'deleteOrder(' in actions
        if page=='after_sale_out_detail':assert 'copyOrder(' in actions
        else:
            assert 'submitDocumentImport(' in actions
            assert ('id','afterSaleOutImportForm') in parsed.attrs
            assert ('id','afterSaleOutImportFile') in parsed.attrs
