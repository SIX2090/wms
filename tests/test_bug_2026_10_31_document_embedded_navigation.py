"""Execute actual shared-form callbacks with the real embedded-URL helper."""
import json
import re
import shutil
import subprocess

import pytest

from tests.test_document_action_busy import _function
from tests.test_document_table_transport_runtime import ROOT, Controls, PROGRAM, render


@pytest.mark.parametrize('doc,mode', [('check','save'), ('check','complete'), ('transfer','save'),
                                   ('transfer','complete'), ('bom','save'), ('requisition','complete')])
@pytest.mark.parametrize('embedded', [False, True])
def test_shared_form_success_preserves_rendering_mode(doc, mode, embedded):
    html = render(doc)
    source = (ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    helpers = '\n'.join(_function(source, name) for name in ['withEmbeddedParam', 'preserveEmbeddedUrl'])
    setup = "ctx.URL=URL;ctx.location.origin='http://fixture.test';ctx.location.search=p.embedded?'?embedded=1':'';document.body.classList={contains:()=>p.embedded};"
    program = PROGRAM.replace('ctx.window=ctx;', 'ctx.window=ctx;' + setup)
    program = program.replace('vm.createContext(ctx);', 'vm.createContext(ctx);vm.runInContext(p.helpers,ctx);')
    # Non-embedded paths keep their original contract; embedded ones stay in content mode.
    program = program.replace("assert.equal(ctx.location.href,'/'+p.doc+'/7');", "assert.equal(new URL(ctx.location.href,'http://fixture.test').pathname,'/'+p.doc+'/7');assert.equal(new URL(ctx.location.href,'http://fixture.test').searchParams.get('embedded'),p.embedded?'1':null);")
    program = program.replace("assert.equal(query.get('picker'),'张三');", "assert.equal(query.get('embedded'),p.embedded?'1':null);assert.equal(query.get('picker'),'张三');")
    program = program.replace("assert(ctx.location.href.startsWith('/requisition/add?'));", "assert.equal(new URL(ctx.location.href,'http://fixture.test').pathname,'/requisition/add');")
    actions = [a['onclick'] for tag,a in Controls(html).nodes if tag=='button' and a.get('onclick','').startswith(('submitForm(', 'completeDocument(', 'revertDocument('))]
    payload = dict(doc=doc, mode=mode, scenario='success', embedded=embedded, helpers=helpers,
                   actions=actions, script=re.findall(r'<script>(.*?)</script>', html, re.S)[0],
                   api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('complete', [False, True])
@pytest.mark.parametrize('embedded', [False, True])
def test_adjustment_waits_for_preserved_navigation_without_duplicate_save(complete, embedded):
    page = (ROOT/'app/templates/adjustment_add.html').read_text(encoding='utf-8')
    source = (ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    payload = dict(complete=complete, embedded=embedded, submit=_function(page,'submitForm'),
        helper=(ROOT/'app/static/js/document-action.js').read_text(encoding='utf-8'),
        urls='\n'.join(_function(source,n) for n in ['withEmbeddedParam','preserveEmbeddedUrl']))
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let calls=[],timers=[];const button={disabled:false,getAttribute:()=>null,setAttribute(){},removeAttribute(){}};
const values={date:'2026-10-31',warehouse_id:'1',order_id:'8',adjustment_no:'ADJ8',adjustment_type:'loss',remark:''};
const fields=Object.fromEntries(Object.entries(values).map(([k,v])=>[k,{value:v}]));
const ctx={Promise,URL,URLSearchParams,readonly:false,showToast(){},setTimeout:(fn,delay)=>timers.push({fn,delay}),
 location:{href:'/original',origin:'http://fixture.test',search:p.embedded?'?embedded=1':''},
 collectItems:()=>({invalidRows:[],items:[{material_id:1,quantity:1}]}),
 document:{body:{classList:{contains:()=>p.embedded}},querySelectorAll:()=>[button],querySelector:s=>fields[(s.match(/name="([^"]+)"/)||[])[1]]||button},
 WMS:{api:{postRaw:async url=>{calls.push(url);return {status:'success',id:8};}}}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.helper+p.urls+p.submit,ctx);
(async()=>{let settled=false;const first=ctx.submitForm(p.complete).then(()=>settled=true);
for(let i=0;i<6;i++)await new Promise(r=>setImmediate(r));
assert.equal(calls.length,p.complete?2:1);assert.equal(timers.length,1);assert.equal(settled,false,'action stays locked until navigation');assert.equal(button.disabled,true);
ctx.submitForm(p.complete);await new Promise(r=>setImmediate(r));assert.equal(calls.length,p.complete?2:1,'second click cannot duplicate save while redirect waits');
timers[0].fn();await first;const url=new URL(ctx.location.href,'http://fixture.test');assert.equal(url.pathname,'/adjustment/8');assert.equal(url.searchParams.get('embedded'),p.embedded?'1':null);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(payload),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_workspace_persists_loaded_detail_and_reuses_its_current_url():
    source = (ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    start = source.index('window.WmsTabs = (function()')
    module = source[start:source.index('\n})();',start)+6]
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const frames=[],stored={};
function element(){return {dataset:{},children:[],classList:{toggle(){}},setAttribute(){},addEventListener(k,fn){this[k]=fn;},appendChild(n){this.children.push(n);},querySelector(){return element();},remove(){},getAttribute(){return null;}};}
const bar=element(),wrap=element();const ctx={URL,URLSearchParams,Map,setTimeout(){},localStorage:{setItem:(k,v)=>stored[k]=v,getItem:k=>stored[k]},
 document:{querySelectorAll:()=>[],getElementById:id=>id==='tabBar'?bar:wrap,createElement(tag){const node=element();if(tag==='iframe')frames.push(node);return node;}},
 location:{origin:'http://fixture.test',pathname:'/check',search:'',hash:''}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(require('node:fs').readFileSync(0,'utf8'),ctx);
ctx.WmsTabs.open('/check/add','新增');assert.equal(frames.length,1);
frames[0].contentDocument={title:'查看盘点单'};frames[0].contentWindow={location:{href:'http://fixture.test/check/8?embedded=1'}};frames[0].load();
assert.equal(ctx.WmsTabs.getActiveContext().url,'/check/8','saved detail replaces stale new-document URL');
assert.equal(JSON.parse(stored.wms_open_tabs).tabs[0].url,'/check/8');
ctx.WmsTabs.open('/check/8?embedded=1','详情');assert.equal(frames.length,1,'current detail reuses its tab');
// Cross-origin load is inaccessible and must keep the last known safe path.
Object.defineProperty(frames[0],'contentWindow',{get(){throw Error('cross-origin');}});frames[0].load();assert.equal(ctx.WmsTabs.getActiveContext().url,'/check/8');
ctx.WmsTabs.open('/check/add','新增');assert.equal(frames.length,2,'new-document entry stays available after its old tab navigated to a detail');assert.equal(ctx.WmsTabs.getActiveContext().url,'/check/add');
'''
    result = subprocess.run([shutil.which('node'),'-e',program],input=module,
        capture_output=True,text=True,encoding='utf-8',timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
