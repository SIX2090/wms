"""Run actual date consumers; browser acceptance also uses these source extracts."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = source.index('function ' + name + '(')
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


def sources():
    shared = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    material = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    opening = (ROOT / 'app/static/js/pages/opening-stock.js').read_text(encoding='utf-8')
    quality = (ROOT / 'app/templates/ai_business_quality.html').read_text(encoding='utf-8')
    reset_start = material.index("document.getElementById('addModal').addEventListener('hidden.bs.modal', function() {")
    reset_end = material.index('\n        });', reset_start) + len('\n        });')
    edit_start = material.index('window.editMaterial = function(id) {')
    copy_start = material.index('window.copyMaterial = function(id) {')
    return {
        'helper': function(shared, 'setWmsDateInputValue') if 'function setWmsDateInputValue(' in shared else '',
        'reset': material[reset_start:reset_end],
        'edit': material[edit_start:material.index('// 编辑物料 - 加载物料档案图片', edit_start)],
        'copy': material[copy_start:material.index('window.findMaterialImage =', copy_start)],
        'optional': function(material, 'setInputValueIfExists'),
        'restore': function(opening, 'restoreDraft'),
        'paste': function(opening, 'showPasteModal'),
        'header': function(opening, 'getHeaderDocDate'),
        'clear': function(quality, 'clearFilters'),
        'filters': function(quality, 'getFilters'),
    }


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const nodes={},events={},calls=[],timers=[];let fixtureDate=p.value,fixtureDraft;
function node(id){return nodes[id]??=( {id,value:'',defaultValue:'',type:'text',disabled:false,
 setAttribute(){},classList:{add(){},remove(){}},addEventListener(n,f){events[id+':'+n]=f;},
 reset(){for(const x of Object.values(nodes))if(x.form===id){x.value=x.defaultValue;x.alt.value=x.alt.defaultValue;}}} );}
const chinese=v=>v?v.replace(/(\d{4})-(\d{2})-(\d{2})/,'$1年$2月$3日'):'';
function date(id,form){const x=node(id);x.form=form;x.type='hidden';x.alt={value:'',defaultValue:''};
 Object.defineProperty(x,'value',{get(){return this.defaultValue;},set(v){this.defaultValue=String(v);},configurable:true});
 x._flatpickr={selectedDates:[],altInput:x.alt,setDate(v,trigger,format){assert.equal(trigger,false);assert.equal(format,'Y-m-d');calls.push(['set',id]);x.value=v;x.alt.value=chinese(v);this.selectedDates=[v];},clear(trigger){assert.equal(trigger,false);calls.push(['clear',id]);x.value='';x.alt.value='';this.selectedDates=[];}};
 return x;}
for(const[id,form]of [['add_expiry_date','addForm'],['edit_expiry_date','editForm'],['headerDocDate','headForm'],['pasteDocDate','pasteForm'],['time_start','filterForm'],['time_end','filterForm']])date(id,form);
const boot={Modal:class{show(){}hide(){}}};boot.Modal.getInstance=()=>new boot.Modal();boot.Modal.getOrCreateInstance=()=>new boot.Modal();
const ctx={console,document:{getElementById:node},bootstrap:boot,WMS:{api:{getRaw:()=>Promise.resolve({status:'success',material:{id:1,code:'M1',name:'物料',expiry_date:fixtureDate}}),post:()=>Promise.resolve({material:{id:1,expiry_date:fixtureDate}})}},
 setTimeout:fn=>timers.push(fn),setQuickSelectValue(){},loadEditMaterialImages(){},showToast(){},
 readDraft:()=>fixtureDraft,hideDraftBanner(){},syncSelectedFlags(){},renderRows(){},invalidatePasteLookup(){},
 loadSnapshot(){ctx.lastFilters=ctx.getFilters();},draftRestoring:false,rows:[],selectedFlags:[],addForm:node('addForm')};
ctx.window=ctx;vm.createContext(ctx);for(const code of Object.values(p.sources))if(code)vm.runInContext(code,ctx);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
function seed(id,v='2025-02-03'){node(id)._flatpickr.setDate(v,false,'Y-m-d');}
function check(id,expected){const x=node(id);assert.equal(x.value,expected,id+' submitted date');assert.equal(x.alt.value,chinese(expected),id+' visible date');assert.deepEqual(x._flatpickr.selectedDates,expected?[expected]:[],id+' selected calendar date');}
(async()=>{
 if(p.action==='helper'){
  if(p.kind==='missing'){ctx.setWmsDateInputValue(null,p.value);return;}
  if(p.kind==='native'){const x={value:'old'};ctx.setWmsDateInputValue(x,p.value);assert.equal(x.value,p.value??'');return;}
  seed('edit_expiry_date');calls.length=0;ctx.setWmsDateInputValue(node('edit_expiry_date'),p.value);check('edit_expiry_date',p.value??'');assert.equal(calls.length,1);return;
 }
 if(p.action==='edit'){seed('edit_expiry_date');await ctx.editMaterial(1);await settle();check('edit_expiry_date',p.value);return;}
 if(p.action==='copy'){seed('add_expiry_date');await ctx.copyMaterial(1);await settle();for(const fn of timers)fn();check('add_expiry_date',p.value);return;}
 if(p.action==='reset'){seed('add_expiry_date',p.value||'2025-02-03');events['addModal:hidden.bs.modal']();check('add_expiry_date','');return;}
 if(p.action==='restore'){seed('headerDocDate');fixtureDraft={rows:[{line_id:8,material_id:3,quantity:2}],header:{date:p.value,warehouse_id:'W2',remark:'恢复备注'}};ctx.restoreDraft();check('headerDocDate',p.value==null?'2025-02-03':p.value);assert.equal(node('headerWarehouse').value,'W2');assert.equal(node('headerRemark').value,'恢复备注');assert.equal(ctx.rows[0].line_id,8);assert.equal(ctx.draftRestoring,false);return;}
 if(p.action==='paste'){seed('headerDocDate',p.value);seed('pasteDocDate');ctx.showPasteModal();check('pasteDocDate',p.value);assert.equal(ctx.getHeaderDocDate(),p.value);return;}
 if(p.action==='filters'){seed('time_start',p.value||'2025-02-03');seed('time_end','2026-09-30');ctx.clearFilters();check('time_start','');check('time_end','');assert.equal(ctx.lastFilters.time_start,null);assert.equal(ctx.lastFilters.time_end,null);return;}
 throw Error(p.action);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


def run(**case):
    node = shutil.which('node')
    assert node, 'Node.js is required to execute actual date consumers'
    result = subprocess.run([node, '--max-old-space-size=64', '-e', PROGRAM],
                            input=json.dumps({'sources': sources(), **case}),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('action', ['edit', 'copy', 'reset', 'restore', 'paste', 'filters'])
@pytest.mark.parametrize('value', ['2027-03-01', '2028-02-29', ''])
def test_actual_date_consumer_keeps_display_calendar_and_payload_in_sync(action, value):
    run(action=action, value=value)


@pytest.mark.parametrize('kind', ['instance', 'native', 'missing'])
@pytest.mark.parametrize('value', ['2027-03-01', '', None])
def test_date_helper_handles_clear_native_and_missing_input_without_events(kind, value):
    run(action='helper', kind=kind, value=value)


def test_draft_without_date_keeps_current_date_and_other_header_fields():
    run(action='restore', value=None)
