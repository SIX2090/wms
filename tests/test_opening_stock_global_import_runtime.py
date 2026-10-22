"""Opening-stock global imports must reach manual precheck before any upload."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app/static/js/app.js'


def source():
    text = APP.read_text(encoding='utf-8')
    names = ['getWmsActionModule', 'showImportModalForModule', 'openUrl',
             'preserveEmbeddedUrl', 'withEmbeddedParam']
    functions = [re.search(r'^function ' + name + r'\([^\n]*\) \{[\s\S]*?^\}', text, re.M).group() for name in names]
    modules = text[text.index('const WMS_ACTION_MODULES ='):text.index('function getWmsActionModule()')]
    return modules + '\n' + '\n'.join(functions)


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
const requests=[],events=[],handlers={},toasts=[],timers=[];
const modal={};
const fields={cbGlobalImportModal:modal,cbGlobalImportFile:{files:p.mode==='no-file'?[]:[{name:'fixture.xlsx'}]},cbGlobalImportSubmit:{addEventListener:(event,fn)=>handlers[event]=fn}};
const doc={body:{classList:{contains:name=>name==='embedded-page'&&p.embedded==='body'},insertAdjacentHTML:(position,html)=>{events.push('modal-html');assert.ok(html.includes('cbGlobalImportFile'));}},getElementById:id=>{if(id==='cbGlobalImportModal'&&!events.includes('modal-html'))return null;return fields[id];}};
class FormData { constructor(){this.values=[];} append(k,v){this.values.push([k,v]);} }
const ctx={URL,URLSearchParams,document:doc,FormData,showToast:(msg,type)=>toasts.push({msg,type}),setTimeout:fn=>timers.push(fn),
bootstrap:{Modal:class{show(){events.push('modal-show');}hide(){events.push('modal-hide');}}},
csrfFetch:(url,options)=>{requests.push({url,options});return p.mode==='network'?Promise.reject(Error('offline-fixture')):Promise.resolve({json:()=>Promise.resolve({status:'success',msg:'imported-fixture'})});}};
ctx.window=ctx;ctx.location={pathname:p.path,search:p.embedded==='query'?'?embedded=1':'',origin:'http://fixture.invalid',href:'original',reload:()=>events.push('reload')};ctx.open=()=>events.push('new-window');
vm.createContext(ctx);vm.runInContext(p.source,ctx);
(async()=>{
  const module=ctx.getWmsActionModule();assert.ok(module,'real path must match a real configured module');
  ctx.showImportModalForModule(module);
  if(module.key==='opening_stock'){
    const url=new URL(ctx.location.href,ctx.location.origin);
    assert.equal(url.pathname,'/batch_import');assert.equal(url.searchParams.get('type'),'opening_stock');
    assert.equal(url.searchParams.get('embedded'),p.embedded==='none'?null:'1');
    assert.deepEqual(events,[]);assert.equal(requests.length,0);assert.deepEqual(toasts,[]);
  }else{
    assert.equal(ctx.location.href,'original');assert.deepEqual(events,['modal-html','modal-show']);
    handlers.click();await new Promise(r=>setImmediate(r));
    if(p.mode==='no-file'){
      assert.equal(requests.length,0);assert.equal(toasts[0].type,'warning');return;
    }
    assert.equal(requests.length,1);assert.equal(requests[0].url,module.importUrl);
    assert.equal(requests[0].options.method,'POST');
    assert.equal(requests[0].options.headers['X-Requested-With'],'XMLHttpRequest');
    assert.equal(requests[0].options.body.values[0][0],'file');assert.equal(requests[0].options.body.values[0][1],fields.cbGlobalImportFile.files[0]);
    if(p.mode==='network'){
      assert.equal(toasts[0].type,'danger');assert.ok(toasts[0].msg.includes('offline-fixture'));assert.equal(timers.length,0);
    }else{
      assert.equal(toasts[0].type,'success');assert.ok(events.includes('modal-hide'));assert.equal(timers.length,1);timers[0]();assert.equal(events.at(-1),'reload');
    }
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
'''


def run(path, embedded='none', mode='success'):
    node=shutil.which('node')
    if not node:pytest.skip('Node.js required')
    payload=dict(source=source(),path=path,embedded=embedded,mode=mode)
    result=subprocess.run([node,'--max-old-space-size=64','-e',PROGRAM,json.dumps(payload)],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.parametrize('path',['/opening_stock','/opening_stock/add','/opening_stock/12','/opening_stock/line/12'])
@pytest.mark.parametrize('embedded',['none','query','body'])
def test_opening_global_import_routes_to_precheck_without_upload(path,embedded):
    run(path,embedded)


@pytest.mark.parametrize('path',['/material','/in_order/12','/out_order/add'])
@pytest.mark.parametrize('mode',['success','no-file','network'])
def test_other_module_modal_upload_contract_is_preserved(path,mode):
    run(path,'query',mode)
