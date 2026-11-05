"""Real editor and transports: stale-page rejection retains the pending input."""
from pathlib import Path
import json
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('transport', ['default', 'callback'])
@pytest.mark.parametrize('scenario', ['conflict', 'business_conflict', 'validation', 'success'])
@pytest.mark.parametrize('field', ['quantity', 'box_no'])
def test_editor_preserves_only_conflict_input_and_keeps_old_error_contract(transport, scenario, field):
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    helpers = base[base.index('    function getCsrfToken()'):base.index('    // Deprecated alias')]
    data = dict(transport=transport, scenario=scenario, field=field, helpers=helpers,
                api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
                excel=(ROOT / 'app/static/js/excel-table.js').read_text(encoding='utf-8'))
    program = r'''
const vm=require('vm'),assert=require('assert/strict'),p=JSON.parse(require('fs').readFileSync(0,'utf8'));
const messages=[],calls=[];let success=0,updates=0,child=null,html='1.00';
const classes=new Set();
const doc={activeElement:null,querySelector(){return {content:'csrf'};},createElement(){return {handlers:{},value:'',addEventListener(k,f){this.handlers[k]=f;},focus(){doc.activeElement=this;},select(){}};}};
const originalValue=p.field==='box_no'?'001-A':'1',newValue=p.field==='box_no'?'0002-B':'7.25';html=originalValue;
const row={dataset:{id:'9'},querySelector(s){return s.includes('price')?{dataset:{value:'2'}}:s.includes('remark')?{dataset:{value:'memo'},textContent:'memo'}:s.includes('quantity')&&p.field==='box_no'?{dataset:{value:'1'}}:cell;}};
const cell={dataset:{value:originalValue,field:p.field},closest(){return row;},querySelector(){return child;},appendChild(n){child=n;},focus(){doc.activeElement=this;},classList:{add(k){classes.add(k);},remove(k){classes.delete(k);}}};
Object.defineProperty(cell,'innerHTML',{get(){return html;},set(v){html=v;child=null;}});Object.defineProperty(cell,'textContent',{get(){return html;},set(v){html=String(v);child=null;}});
const ctx={Headers,FormData,document:doc,setTimeout,location:{href:'http://fixture/in_order/1'},fetch(url,options){calls.push({url,options});let status=p.scenario==='conflict'?409:p.scenario==='validation'?400:200;const body=p.scenario==='success'?{status:'success'}:{status:'error',code:p.scenario==='validation'?'INVALID_VALUE':'DOCUMENT_EDIT_CONFLICT',msg:'fixture error'};return Promise.resolve({ok:status===200,status,json:()=>Promise.resolve(body)});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.helpers,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.excel,ctx);
const editor=Object.create(ctx.ExcelTable.prototype);editor.table={querySelector(){return classes.has('cell-selected')?cell:null;}};editor.options={onSave:p.transport==='callback'?(_id,_field,_value,data)=>ctx.WMS.api.postRaw('/in_order/item/update',data):null};editor.isEditing=false;editor.showSuccess=()=>success++;editor.showError=m=>messages.push(m);editor.updateAmount=()=>updates++;
editor.startEdit(cell);if(p.field==='box_no'){assert.equal(child.type,'text');assert.equal(child.maxLength,100);}child.value=newValue;child.handlers.blur();
(async()=>{await new Promise(r=>setImmediate(r));await new Promise(r=>setImmediate(r));
 assert.equal(calls.length,1);assert.equal(calls[0].url,'/in_order/item/update');assert.equal(calls[0].options.body.get('quantity'),p.field==='box_no'?'1':'7.25');assert.equal(new Headers(calls[0].options.headers).get('X-CSRFToken'),'csrf');
 if(p.field==='box_no'){assert.equal(calls[0].options.body.get('box_no'),'0002-B');assert.equal(calls[0].options.body.get('remark'),'memo');}
 const conflict=['conflict','business_conflict'].includes(p.scenario);
 if(conflict){assert(child,'pending editor must be restored');assert.equal(child.value,newValue);assert.equal(editor.isEditing,true);assert.equal(cell.dataset.value,originalValue,'failed edit must not masquerade as persisted');assert.equal(doc.activeElement,child);assert.equal(updates,0);assert.equal(success,0);assert.equal(messages.length,1);child.handlers.keydown({key:'Escape',preventDefault(){}});assert.equal(editor.isEditing,false);assert.equal(cell.dataset.value,originalValue);}
 else if(p.scenario==='validation'){assert.equal(child,null);assert.equal(editor.isEditing,false);assert.equal(cell.dataset.value,originalValue);assert.equal(updates,0);assert.equal(success,0);assert.equal(messages.length,1);}
 else {assert.equal(child,null);assert.equal(editor.isEditing,false);assert.equal(cell.dataset.value,p.field==='box_no'?newValue:7.25);assert.equal(updates,p.field==='box_no'?0:1);assert.equal(success,1);assert.equal(messages.length,0);}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run(['node', '-e', program], input=json.dumps(data), capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
