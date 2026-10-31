"""A copied opening row is new; deleting it must never touch its saved source."""
import json
import shutil
import subprocess

import pytest

from tests.test_opening_stock_material_lookup_runtime import ROOT, SOURCE, Nodes, PROGRAM


@pytest.mark.parametrize('operation', ['single', 'batch', 'mixed'])
def test_copied_saved_row_has_no_persisted_identity_and_original_survives(operation):
    check = r'''
 ctx.confirm=()=>true;
 ctx.showConfirm=async()=>true;
 vm.runInContext("rows=[{line_id:73,material_id:1,material_code:'M1',material_name:'fixture',quantity:2,price:0,warehouse_id:1,remark:'old'}];selectedFlags=[false];",ctx);
 ctx.copyPreviousRow();
 const copied=vm.runInContext('rows[1]',ctx), original=vm.runInContext('rows[0]',ctx);
 assert.equal(copied.line_id??null,null,'copy is unsaved, never a reference to source row');
 assert.equal(original.line_id,73);assert.equal(copied.quantity,2);assert.equal(copied.price,0);assert.equal(copied.warehouse_id,1);assert.equal(copied.remark,'');
 assert(el('openingGridBody').innerHTML.includes('删除本行（尚未保存）'));
 const draft=vm.runInContext('collectDraftRows()',ctx);assert.equal(draft[0].line_id,73);assert.equal(draft[1].line_id??null,null);
 if(p.scenario==='single')ctx.deleteRow(1);
 else {vm.runInContext(p.scenario==='mixed'?'selectedFlags=[true,true]':'selectedFlags=[false,true]',ctx);ctx.batchDeleteSelectedRows();}
 await settle();
 if(p.scenario==='mixed'){assert.equal(calls.length,1);assert.deepEqual(calls[0].body.line_ids,[73],'source identity must occur only once');return;}
 assert.equal(calls.length,0,'unsaved duplicate deletion must be entirely local');
 assert.equal(vm.runInContext('rows.length',ctx),1);assert.equal(vm.runInContext('rows[0].line_id',ctx),73);assert.equal(vm.runInContext('rows[0].quantity',ctx),2);
 return;
'''
    program = PROGRAM.replace('__OPENING_DOC__:null', '__OPENING_DOC__:{id:8}')
    program = program.replace('(async()=>{', '(async()=>{' + check, 1)
    payload = dict(scenario=operation, source=SOURCE.read_text(encoding='utf-8'),
                   api=(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),
                   nodes=Nodes((ROOT/'app/templates/opening_stock.html').read_text(encoding='utf-8')).nodes)
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
