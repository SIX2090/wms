"""Execute the master checkbox click and the shared selection listener."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('checked', [True, False])
def test_sales_master_checkbox_click_and_change(checked):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    sales = (ROOT / 'app/templates/sales_order.html').read_text(encoding='utf-8')
    master = re.search(r'<input[^>]*id="checkAllSalesOrders"[^>]*>', sales).group()
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    start = base.index('function bindListActions(opts)')
    function = base[start:base.index('// SM-P6-03-3: 通用分页', start)]
    payload = json.dumps(dict(master=master, function=function, checked=checked))
    script = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(process.argv[1]), events={};
const rows=[{checked:!p.checked,disabled:false},{checked:!p.checked,disabled:false},{checked:false,disabled:true}];
const master={checked:p.checked,addEventListener:(event,fn)=>events[event]=fn};
const table={addEventListener:()=>{},querySelectorAll:selector=>selector.includes(':not(:disabled)')?rows.filter(r=>!r.disabled):rows};
const ctx={document:{getElementById:()=>table,querySelector:()=>master,addEventListener:()=>{}}};
vm.createContext(ctx);vm.runInContext(p.function,ctx);
ctx.bindListActions({tableId:'salesOrderTable',masterCheckbox:'#checkAllSalesOrders'});
const onclick=p.master.match(/onclick="([^"]+)"/);
if(onclick) vm.runInContext(onclick[1],ctx);
assert.equal(typeof events.change,'function');events.change();
assert.equal(rows[0].checked,p.checked);assert.equal(rows[1].checked,p.checked);
assert.equal(rows[2].checked,false);
'''
    result = subprocess.run([node, '-e', script, payload], capture_output=True,
                            text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
