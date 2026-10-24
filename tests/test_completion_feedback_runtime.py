"""Saved documents retain actionable completion failures instead of losing a toast."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _function(source, name, optional=False):
    start = source.find('function ' + name + '(')
    if start < 0 and optional:
        return ''
    assert start >= 0, name
    depth = 0
    for end in range(source.index('{', start), len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let calls=[],pending=[],messages=[],timers=[],confirmed=0;
const reason='出库仓库 铜排仓 库存不足：物料1280 需要16.00，可用3.00 <img src=x onerror=alert(1)>';
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.style={};this.value='';this.disabled=false;this._text='';}
 setAttribute(k,v){this.attrs[k]=String(v);}
 getAttribute(k){return this.attrs[k]??null;}
 get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
 set textContent(v){this._text=String(v??'');this.children=[];}
 set innerHTML(v){throw Error('Untrusted completion feedback must never use innerHTML');}
 appendChild(n){this.children.push(n);return n;}
 insertBefore(n,before){const at=this.children.indexOf(before);this.children.splice(at<0?this.children.length:at,0,n);return n;}
 replaceChildren(...nodes){this.children=nodes;this._text='';}
 get firstChild(){return this.children[0]||null;}
 focus(){this.focused=true;}
 scrollIntoView(){this.scrolled=true;}
 click(){if(this.tag==='a')ctx.location.href=this.href;}
}
const root=new Element('div');
const buttons=[new Element('button'),new Element('button'),new Element('button')];buttons[2].disabled=true;
const fields=Object.fromEntries(Object.entries({order_id:p.existing?'7':'',order_no:'OLD-7',date:'2026-10-24',
 department_id:'1',picker:'',warehouse_id:'2',supplier_id:'1',business_type:p.kind==='in'?'采购入库':'领料单',purpose:'',remark:''})
 .map(([name,value])=>{const field=new Element('input');field.value=value;return[name,field];}));
const values={'.material-code':'1280','.material-qty':'16','.material-price':'0'};
const row={dataset:{},querySelector(s){return s in values?{value:values[s],style:{}}:null;}};
const all=()=>{const result=[];function visit(node){result.push(node);node.children.forEach(visit);}visit(root);return result;};
const document={body:{classList:{contains:()=>p.embedded}},
 querySelector(s){if(s==='.embedded-content')return root;if(s.startsWith('meta'))return{content:'fixture-token'};return fields[(s.match(/name="([^"]+)"/)||[])[1]]||null;},
 querySelectorAll:s=>s==='#materialTableBody tr'?[row]:buttons,
 createElement:tag=>new Element(tag),getElementById:id=>all().find(n=>n.id===id)||null};
const ctx={document,Headers,FormData,URL,URLSearchParams,
 location:{origin:'http://fixture',href:'/original',search:p.embedded?'?embedded=1':''},
 showToast:(message,type)=>messages.push({message,type}),confirm:()=>true,
 setTimeout:(fn,delay)=>{timers.push({fn,delay});},
 clearInOrderValidation(){},showInOrderValidation(){assert.fail('unexpected validation');},markRowError(){},findMaterialByCode:()=>true,
 clearDraft(){},collectItems:()=>({items:[{material_id:1,quantity:16}],invalidRows:[]}),collectHeader:()=>({warehouse_id:'2'}),
 showCompleteConfirm(){confirmed++;},
 fetch:(url,options)=>{calls.push({url,options,body:JSON.parse(options.body)});return new Promise((resolve,reject)=>pending.push({resolve,reject}));}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.shared,ctx);
vm.runInContext(`const isSaleOrder=false,isOtherOut=false,isPurchaseReturn=false,purchaseReturnRequiresOrder=false,
 partyField='supplier_id',partyLabel='供应商',supplierRequired=true,returnAddUrl='/${p.kind}_order/add',
 readonly=false,documentRoleAllowed=true,requisitionLocationRequired=false,saveUrl='/requisition/save_table',completeUrl='/requisition/0/complete',detailUrl='/requisition',docType='requisition';
 let inOrderSubmitting=false,outOrderSubmitting=false;`,ctx);
vm.runInContext(p.script,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
function response(scenario,save=false){
 const status=save?200:({http400:400,http409:409,http408:408,http500:500}[scenario]||200);
 const body=save?{status:scenario==='save_error'?'error':'success',id:7,order_no:'SAVED-7',msg:reason}:
   scenario==='null'?null:scenario==='empty'?{}:{status:scenario==='success'?'success':scenario==='confirm'?'confirm':scenario==='warning'?'warning':'error',msg:reason};
 return {ok:status===200,status,json:()=>!save&&scenario==='malformed'?Promise.reject(Error('无效JSON')):Promise.resolve(body)};
}
const invoke=()=>p.kind==='shared'?ctx.submitForm(true):ctx.submitForm(false,true);
(async()=>{
 const first=invoke();invoke();assert.equal(calls.length,1,'save mutex must reject double click');
 assert.equal(calls[0].body.order_id,p.existing?'7':'');
 if(p.scenario==='save_network')pending[0].reject(Error('网络中断'));else pending[0].resolve(response(p.scenario,true));
 await settle();
 if(p.scenario.startsWith('save_')){
  await first;assert.equal(calls.length,1);assert.equal(ctx.location.href,'/original');assert.equal(root.children.length,0);
  assert.equal(buttons[0].disabled,false);assert.equal(buttons[2].disabled,true);
  invoke();assert.equal(calls.length,2,'save failure remains manually retryable');return;
 }
 assert.equal(calls.length,2);assert.equal(String(fields.order_id.value),'7');
 assert.equal(calls[1].options.headers['X-CSRFToken'],'fixture-token');
 assert.deepEqual(calls[1].body,p.kind==='shared'?{force:false}:{});
 invoke();assert.equal(calls.length,2,'completion in flight must not resave');
 if(p.scenario==='network')pending[1].reject(Error('网络中断'));else pending[1].resolve(response(p.scenario));
 await first;await settle();timers.splice(0).forEach(t=>t.fn());
 if(p.scenario==='success'){
  assert.equal(root.children.length,0);assert(ctx.location.href.includes(p.kind==='shared'?'/requisition/add':`/${p.kind}_order/add`));
  invoke();assert.equal(calls.length,2,'successful navigation stays locked');return;
 }
 if(p.scenario==='confirm' && p.kind==='shared'){
  assert.equal(confirmed,1);assert.equal(root.children.length,0);assert.equal(ctx.location.href,'/original');
  assert.equal(buttons[0].disabled,false);assert.equal(buttons[2].disabled,true);
  assert.equal(vm.runInContext('submitForm.pending',ctx),false);
  ctx.runComplete('/requisition/7/complete',true,7);assert.equal(calls.length,3);assert.deepEqual(calls[2].body,{force:true});return;
 }
 assert.equal(ctx.location.href,'/original','completion problems must remain visible before any navigation');
 const panel=document.getElementById('wmsCompletionIssue');assert(panel,'persistent recovery panel is missing');
 assert.equal(panel.getAttribute('role'),'alert');assert.equal(panel.getAttribute('tabindex'),'-1');assert(panel.focused && panel.scrolled);
 assert(panel.textContent.includes('SAVED-7'),'panel identifies the server-saved document');
 const uncertain=['http408','http500','network','null','empty','malformed'].includes(p.scenario);
 assert(panel.textContent.includes(uncertain?'完成结果待核对':'本次完成请求未成功'));
 if(!['null','empty','malformed','network'].includes(p.scenario))assert(panel.textContent.includes(reason),'server rejection reason must not disappear');
 if(p.scenario==='network')assert(panel.textContent.includes('网络中断'));
 assert(!all().some(n=>n.tag==='img'||n.tag==='script'),'reason must remain literal text');
 assert.equal(buttons[0].disabled,true);assert.equal(buttons[2].disabled,true);invoke();assert.equal(calls.length,2);
 if(p.kind==='shared'){ctx.runComplete('/requisition/7/complete',true,7);assert.equal(calls.length,2,'uncertain completion cannot be forced or retried');}
 assert(!calls.some(c=>c.url.includes('force')));
 const link=all().find(n=>n.tag==='a');assert(link);const url=new URL(link.href,ctx.location.origin);
 assert.equal(url.pathname,p.kind==='shared'?'/requisition/7':`/${p.kind}_order/7`);assert.equal(url.searchParams.get('embedded'),p.embedded?'1':null);
 assert(link.textContent.includes('查看已保存单据'));
 ctx.showDocumentCompletionIssue(link.href,{status:'error',msg:'再次核对'});assert.equal(root.children.length,1,'reuse the same result panel');
 all().find(n=>n.tag==='a').click();assert.equal(new URL(ctx.location.href,ctx.location.origin).pathname,url.pathname);assert.equal(calls.length,2);
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


def _run(kind, scenario, embedded=False, existing=False):
    binary = shutil.which('node')
    assert binary, 'Node.js required for completion-feedback runtime regression'
    source = (ROOT / 'app/templates' / ('document_table_form.html' if kind == 'shared' else kind + '_order_add.html')).read_text(encoding='utf-8')
    names = ['submitForm'] if kind != 'shared' else ['beginDocumentAction', 'endDocumentAction', 'submitForm', 'runComplete']
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    payload = dict(kind=kind, scenario=scenario, embedded=embedded, existing=existing,
        script='\n'.join(_function(source, name) for name in names),
        shared='\n'.join(_function(shared, name, optional=name=='showDocumentCompletionIssue') for name in ['withEmbeddedParam','preserveEmbeddedUrl','showDocumentCompletionIssue']),
        api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([binary, '--max-old-space-size=64', '-e', PROGRAM], input=json.dumps(payload),
        text=True, encoding='utf-8', capture_output=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('kind', ['out', 'in', 'shared'])
@pytest.mark.parametrize('embedded', [False, True])
@pytest.mark.parametrize('scenario', ['business','warning','http400','http409','http408','http500','network','null','empty','malformed'])
def test_completion_failure_remains_visible_locked_and_reachable(kind, embedded, scenario):
    _run(kind, scenario, embedded)


@pytest.mark.parametrize('kind', ['out', 'in', 'shared'])
@pytest.mark.parametrize('scenario', ['success','save_error','save_network'])
def test_success_and_save_failure_keep_existing_behavior(kind, scenario):
    _run(kind, scenario)


@pytest.mark.parametrize('kind', ['out', 'in', 'shared'])
def test_existing_draft_retains_saved_identity_without_resubmission(kind):
    _run(kind, 'http400', embedded=True, existing=True)


def test_shared_risk_confirmation_remains_a_separate_manual_decision():
    _run('shared', 'confirm')
