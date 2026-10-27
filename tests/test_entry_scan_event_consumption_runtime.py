"""BUG-2026-10-25-003: run real row and document Enter listeners in order."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def page_handlers(template):
    text = (ROOT / 'app/templates' / template).read_text(encoding='utf-8')
    names = ['fillMaterialFields', 'selectMaterial', 'handleKeydown',
             'focusNextEditable', 'setupScanAutoFill']
    parts = []
    if 'const materialSearchState =' in text:
        parts.append(re.search(r'const materialSearchState = [^\n]+', text).group())
        names.insert(0, 'cancelMaterialSearch')
    for name in names:
        parts.append(re.search(r'function ' + name + r'\([^\n]*\) \{.*?\n\}',
                               text, re.S).group())
    callback = re.search(
        r"row\.querySelector\('\.material-code'\)\.addEventListener\('keydown', (function\(event\) \{.*?\n    \})\);",
        text, re.S).group(1)
    return '\n'.join(parts), callback


SCRIPT = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const fields={},focuses=[],timers=[],documentEvents={};let calculated=0,selected=0;
for(const name of ['material-code','material-brand','material-name','material-spec',
 'material-unit','material-stock','material-price','material-qty']) {
 fields['.'+name]={value:'',handlers:{},addEventListener(n,f){this.handlers[n]=f},
  focus(){focuses.push(name)},select(){selected++}};
}
const input=fields['.material-code'],price=fields['.material-price'];
input.value='M001';price.value='12.34';
const candidate={dataset:{code:'M002'}};
const dropdown={style:{display:p.mode==='closed'?'none':'block'},
 querySelector(){return candidate}};
const row={isConnected:true,querySelector(s){return s==='.material-dropdown'?dropdown:fields[s]||null}};
input.closest=()=>row;input.classList={contains:c=>c==='material-code'};
const context={row,materials:[{id:1,code:'M001',name:'轴承',price:99,stock:10},
 {id:2,code:'M002',name:'螺栓',price:77,stock:20}],activeDropdown:dropdown,
 document:{addEventListener(n,f){(documentEvents[n]||=[]).push(f)},querySelector(){return null},
  querySelectorAll(){return [input,fields['.material-qty'],price]}},
 getMaterialUnit:()=>'',formatStock:String,fillPurposeFromMaterial(){},
 calcAmount(){calculated++},calcTotal(){},clearTimeout(){},
 setTimeout(f,ms){timers.push({f,ms})},
 WMS:{api:{get(){throw Error('Unexpected network')}}}};
context.window=context;vm.createContext(context);vm.runInContext(p.cache,context);vm.runInContext(p.source,context);
vm.runInContext("row.querySelector('.material-code').addEventListener('keydown',"+p.callback+");setupScanAutoFill();",context);
const event={key:p.mode==='non_enter'?'Tab':'Enter',target:input,
 defaultPrevented:p.mode==='preconsumed',isComposing:p.mode==='ime',
 keyCode:p.mode==='ime229'?229:0,preventDefault(){this.defaultPrevented=true}};
if(p.mode.startsWith('barcode')) {
 price.value='';
 if(p.mode==='barcode_short')input.value='M1';
 if(p.mode==='barcode_unknown')input.value='M999';
 if(p.mode==='barcode_non_code')input.classList={contains:()=>false};
}
const rowHandled=['candidate','closed','ime','ime229','non_enter'].includes(p.mode);
if(rowHandled)input.handlers.keydown.call(input,event);
const priceAfterRow=price.value,focusAfterRow=focuses.length,calcsAfterRow=calculated;
for(const f of documentEvents.keydown||[])f(event);
if(p.mode==='candidate'||p.mode==='closed'||p.mode==='preconsumed') {
 assert.equal(priceAfterRow,'12.34','row selection preserves manually entered price');
 assert.equal(event.defaultPrevented,true);
 assert.equal(price.value,'12.34','consumed Enter must not overwrite the manual price');
 assert.equal(calculated,calcsAfterRow,'consumed Enter must not calculate twice');
 assert.deepEqual(timers,[],'consumed Enter must not queue a delayed focus');
 assert.equal(focuses.length,focusAfterRow);
 if(p.mode==='candidate'){assert.equal(input.value,'M002');assert.equal(focusAfterRow,1)}
 if(p.mode==='closed')assert.equal(focusAfterRow,1);
} else if(p.mode==='barcode') {
 assert.equal(event.defaultPrevented,false);
 assert.equal(price.value,'99.00','unhandled barcode retains its normal default price');
 assert.equal(calculated,1);assert.deepEqual(timers.map(t=>t.ms),[50]);
 assert.equal(focuses.length,0);timers[0].f();assert.deepEqual(focuses,['material-qty']);
} else {
 assert.equal(price.value,priceAfterRow);assert.equal(calculated,0);
 assert.deepEqual(timers,[]);assert.deepEqual(focuses,[]);
}
process.stdout.write(JSON.stringify({mode:p.mode,price:price.value,calculated,timers:timers.length}));
'''


@pytest.mark.parametrize('template', ['in_order_add.html', 'out_order_add.html'])
@pytest.mark.parametrize('mode', ['candidate', 'closed', 'preconsumed', 'barcode',
                                 'barcode_short', 'barcode_unknown', 'barcode_non_code',
                                 'ime', 'ime229', 'non_enter'])
def test_scan_respects_consumed_enter(template, mode):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for actual entry event handlers')
    source, callback = page_handlers(template)
    result = subprocess.run([node, '-e', SCRIPT],
                            input=json.dumps(dict(source=source, callback=callback, mode=mode, cache=(ROOT/'app/static/js/material-cache.js').read_text(encoding='utf-8'))),
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
