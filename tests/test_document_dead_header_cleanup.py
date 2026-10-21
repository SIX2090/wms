"""Retain live line contracts and employee picking when removing orphaned header code."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['in_order_add', 'out_order_add', 'purchase_order_add', 'sales_order_add', 'sales_order_edit']


@pytest.mark.parametrize('page', PAGES)
def test_orphaned_header_removed_but_line_contract_fields_remain(page):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    assert 'line-contract-no' in source and 'line-project-name' in source
    assert 'data-column-key="contract_no"' in source
    assert "getElementById('contractSearch')" not in source
    assert "getElementById('contractDropdown')" not in source


def test_outbound_employee_search_and_selection_still_run():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / 'app/templates/out_order_add.html').read_text(encoding='utf-8')
    position = source.index("getElementById('pickerInput')")
    start = source.rindex('(function()', 0, position)
    end = source.index('\n})();', position) + len('\n})();')
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    escape_start = app.index('function escapeHtml(')
    escape_end = app.index('\n}', escape_start) + 2
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);let requests=[];
function node(){return {value:'EMP',style:{},handlers:{},dataset:{index:'0'},addEventListener(k,f){this.handlers[k]=f;},getBoundingClientRect:()=>({bottom:100,left:20})};}
const input=node(),dropdown=node(),button=node(),item=node();dropdown.querySelectorAll=()=>[item];const nodes={pickerInput:input,pickerDropdown:dropdown,pickerSearchBtn:button};
const ctx={document:{getElementById:id=>nodes[id],addEventListener(){}},console,fetch:url=>{requests.push(url);return Promise.resolve({json:()=>Promise.resolve({data:[{name:'Fixture Employee',department:'Audit Dept',phone:''}]})});}};vm.createContext(ctx);vm.runInContext(p.escape,ctx);vm.runInContext(p.code,ctx);
(async()=>{input.handlers.focus.call(input);await new Promise(r=>setImmediate(r));assert.deepEqual(requests,['/employee/api/search?q=EMP']);assert.equal(dropdown.style.display,'block');assert(dropdown.innerHTML.includes('Fixture Employee'));item.handlers.click.call(item);assert.equal(input.value,'Fixture Employee');assert.equal(dropdown.style.display,'none');})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([node, '-e', program, json.dumps({'code': source[start:end], 'escape': app[escape_start:escape_end]})], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
