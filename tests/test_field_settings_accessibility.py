"""Execute field-settings keyboard handlers, focus restoration and row naming."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _function(source, name):
    start = source.index('function ' + name + '(')
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if not depth:
            return source[start:end + 1]
    raise AssertionError(name)


@pytest.mark.parametrize('case', ['close', 'removed', 'controls', 'forward', 'backward', 'outside', 'escape', 'nested', 'focus', 'row', 'parent'])
def test_field_settings_keyboard_runtime(case):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    module = source.split('// Unified document-grid field settings,')[1].split('// Global fill-down controls')[0]
    # Use the production listeners without running unrelated global application setup.
    key = re.search(r"document.addEventListener\('keydown', function\(event\) \{(.*?)\n        \}, true\);", module, re.S)
    focus = re.search(r"document.addEventListener\('focusin', function\(event\) \{(.*?)\n        \}\);", module, re.S)
    assert key and focus, 'field settings must bind keyboard and focus handlers'
    functions = '\n'.join(_function(module, name) for name in ['closeFieldSettings', 'fieldSettingsControls', 'renderRows', 'open'])
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
let restored=0; const document={activeElement:null,createElement(){const text={attrs:{},value:'',setAttribute(k,v){this.attrs[k]=v;},addEventListener(){}};const checkbox={attrs:{},setAttribute(k,v){this.attrs[k]=v;},addEventListener(){}};return {dataset:{},cells:Array.from({length:4},()=>({dataset:{}})),handlers:{},querySelector:q=>q.includes('checkbox')?checkbox:text,classList:{add(){this.selected=true;},remove(){this.selected=false;}},addEventListener(k,v){this.handlers[k]=v;}};}};
const control=()=>({disabled:false,tabIndex:0,getClientRects:()=>[{}],focus(){document.activeElement=this;}});
const first=control(),last=control(),disabled=control(),hidden=control(),negative=control();disabled.disabled=true;hidden.getClientRects=()=>[];negative.tabIndex=-1;
const tbody={rows:[],appendChild(row){this.rows.push(row);},querySelectorAll(){return this.rows;}};
const host={hidden:false,querySelectorAll:()=>[first,disabled,hidden,negative,last],contains:n=>n===first||n===last,querySelector:q=>q.includes('body')?tbody:first};first.value='';
const ctx={host,document,activeController:{table:{}},fieldSettingsReturnFocus:{isConnected:true,focus(){restored++;}},activeConfirm:null,escapeHtml:s=>s};
vm.createContext(ctx);vm.runInContext(p.functions,ctx);vm.runInContext('var keyHandler=function(event){'+p.key+'};var focusHandler=function(event){'+p.focus+'};',ctx);
let prevented=0,stopped=0;const event={key:'Tab',shiftKey:false,preventDefault(){prevented++;},stopImmediatePropagation(){stopped++;}};
if(p.case==='close'||p.case==='removed'){ctx.fieldSettingsReturnFocus.isConnected=p.case==='close';ctx.closeFieldSettings(host);assert(host.hidden);assert.equal(ctx.activeController,null);assert.equal(restored,p.case==='close'?1:0);assert.equal(ctx.fieldSettingsReturnFocus,null);}
if(p.case==='controls')assert.deepEqual(Array.from(ctx.fieldSettingsControls(host)),[first,last]);
if(p.case==='forward'||p.case==='backward'||p.case==='outside'){document.activeElement=p.case==='forward'?last:p.case==='backward'?first:{};event.shiftKey=p.case==='backward';ctx.keyHandler(event);assert.equal(prevented,1);assert.equal(document.activeElement,p.case==='backward'?last:first);}
if(p.case==='escape'){event.key='Escape';ctx.keyHandler(event);assert(host.hidden);assert.equal(restored,1);assert.equal(stopped,1);}
if(p.case==='nested'){ctx.activeConfirm={};event.key='Escape';ctx.keyHandler(event);ctx.focusHandler({target:{}});assert(!host.hidden);assert.equal(document.activeElement,null);assert.equal(prevented,0);}
if(p.case==='focus'){ctx.focusHandler({target:{}});assert.equal(document.activeElement,first);document.activeElement=last;ctx.focusHandler({target:last});assert.equal(document.activeElement,last);}
if(p.case==='parent'){const parent={appendChild(n){n.parentElement=this;}},body={};ctx.document.body=body;host.parentElement=body;ctx.findGrid=()=>({});ctx.columnsOf=()=>[];ctx.readState=()=>({});ctx.ensureModal=()=>host;ctx.renderRows=()=>{};first.click=()=>{};ctx.open({closest:()=>parent});assert.equal(host.parentElement,parent);assert.equal(document.activeElement,first);}
if(p.case==='row'){ctx.renderRows(host,{state:{order:['memo'],labels:{},hidden:[]},columns:[{key:'memo',defaultLabel:'备注'}]});const row=tbody.rows[0];assert.equal(row.querySelector('input[type=text]').attrs['aria-label'],'备注显示名称');assert.equal(row.querySelector('input[type=checkbox]').attrs['aria-label'],'显示备注');assert.equal(row.cells[2].dataset.fsLabel,'显示名称');row.handlers.focusin();assert(row.classList.selected);}
'''
    result = subprocess.run([node, '--max-old-space-size=64', '-e', script, json.dumps(dict(case=case, functions=functions, key=key[1], focus=focus[1]))], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_mobile_field_settings_preserves_hidden_search_rows():
    css = (ROOT / 'app/static/css/custom.css').read_text(encoding='utf-8')
    assert '.wms-field-settings__table tr[hidden]{display:none}' in css
    assert 'max-height:calc(100dvh - 16px)' in css


def test_observer_reloads_saved_order_instead_of_reverting_it():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    functions = '\n'.join(_function(source, name) for name in ['storageKey', 'readState', 'refreshSavedFieldSettings'])
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);let applied;
const saved={order:['memo','quantity'],hidden:['memo'],labels:{memo:'已保存备注'}};
const controller={table:{id:'fixture'},columns:[{key:'quantity',locked:true},{key:'memo',locked:false}],state:{order:['quantity','memo'],hidden:[],labels:{}}};
const ctx={location:{pathname:'/isolated'},localStorage:{getItem:()=>JSON.stringify(saved)},applyState:c=>applied=c.state};vm.createContext(ctx);vm.runInContext(p,ctx);ctx.refreshSavedFieldSettings(controller);assert.equal(JSON.stringify(applied),JSON.stringify(saved));
'''
    result = subprocess.run([node, '--max-old-space-size=64', '-e', script, json.dumps(functions)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
