"""Local copied rows use an explicit cancellable application confirmation."""
import json
import shutil
import subprocess
import pytest
from tests.test_opening_stock_material_lookup_runtime import ROOT,SOURCE,Nodes,PROGRAM

@pytest.mark.parametrize('decision',['accept','cancel','changed'])
def test_opening_batch_confirmation_preserves_local_scope(decision):
    check=r'''
 let dialogs=0,nativeCalls=0,answer;
 ctx.confirm=()=>{nativeCalls++;return true;};
 ctx.showConfirm=(message,options)=>{dialogs++;assert(message.includes('尚未保存'));assert(!message.includes('已建账'));return new Promise(resolve=>answer=resolve);};
 vm.runInContext("rows=[{line_id:73,material_id:1,material_code:'M1',quantity:2,warehouse_id:1}];selectedFlags=[false];",ctx);
 ctx.copyPreviousRow();ctx.copyPreviousRow();vm.runInContext('selectedFlags=[false,true,true]',ctx);
 const pending=ctx.batchDeleteSelectedRows();assert.equal(dialogs,1);assert.equal(nativeCalls,0);
 assert.equal(vm.runInContext('rows.length',ctx),3);
 if(p.scenario==='changed')vm.runInContext('rows[1].line_id=99',ctx);
 answer(p.scenario!=='cancel');await pending;await settle();
 assert.equal(calls.length,0,'no business API for local copies or changed context');
 assert.equal(vm.runInContext('rows[0].line_id',ctx),73);assert.equal(vm.runInContext('rows[0].quantity',ctx),2);
 assert.equal(vm.runInContext('rows.length',ctx),p.scenario==='accept'?1:3);
 return;
'''
    program=PROGRAM.replace('__OPENING_DOC__:null','__OPENING_DOC__:{id:8}').replace('(async()=>{','(async()=>{'+check,1)
    payload={'scenario':decision,'source':SOURCE.read_text(encoding='utf-8'),'api':(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),
             'nodes':Nodes((ROOT/'app/templates/opening_stock.html').read_text(encoding='utf-8')).nodes}
    result=subprocess.run([shutil.which('node'),'-e',program],input=json.dumps(payload),capture_output=True,text=True,encoding='utf-8',timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
