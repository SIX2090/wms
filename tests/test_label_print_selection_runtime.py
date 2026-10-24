"""BUG-2026-10-24-011: execute rendered checkbox handlers and inspect print-time DOM."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def _render():
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}'}),
        FileSystemLoader(str(ROOT / 'app/templates')),
    ]), autoescape=True)
    env.filters['from_json'] = json.loads
    template = SimpleNamespace(id=4, name='测试标签', width=60, height=40, rows=1, cols=1, layout='{}')
    materials = [SimpleNamespace(id=i, code=f'M-{i}', name=f'物料{i}') for i in [101, 202]]
    return env.get_template('print_label.html').render(template=template, templates=[template], materials=materials)


@pytest.mark.parametrize('scenario', [
    'initial', 'uncheck', 'uncheck_all', 'select_none_then_one', 'select_all_then_uncheck',
    'toggle_repeatedly', 'string_id', 'browser_restored', 'unrelated_checkbox', 'no_auto_print',
])
def test_printed_labels_match_checkbox_selection(scenario):
    html = _render()
    payload = {'scenario': scenario, 'script': re.search(r'<script>(.*?)</script>', html, re.S).group(1),
               'ids': re.findall(r'class="label-item-wrapper" data-material-id="(\d+)"', html),
               'handlers': re.findall(r'onchange="(toggleMaterial[^"]+)"', html)}
    assert payload['ids'] == ['101', '202'] and len(payload['handlers']) == 2
    program = r"""
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(fs.readFileSync(0,'utf8')),events={},prints=[];
const wrappers=p.ids.map(id=>({dataset:{materialId:id},style:{display:'block'}}));
const boxes=wrappers.map(w=>({checked:true,closest:s=>s==='.label-item-wrapper'?w:null}));
const unrelated={checked:false,closest:()=>null};
const document={addEventListener:(name,fn)=>{events[name]=fn},querySelectorAll:s=>{
 if(s==='.label-item-wrapper')return wrappers;
 if(s==='input[type="checkbox"]')return [...boxes,unrelated];
 if(s==='.label-item-wrapper input[type="checkbox"]')return boxes;
 throw Error('Unsupported selector '+s);
}};
const window={print:()=>prints.push(wrappers.filter(w=>w.style.display!=='none').map(w=>w.dataset.materialId))};
const ctx=vm.createContext({document,window,Set,URLSearchParams});
vm.runInContext(p.script,ctx);
if(p.scenario==='browser_restored')boxes[0].checked=false;
events.DOMContentLoaded();
function toggle(i,checked){boxes[i].checked=checked;ctx.box=boxes[i];vm.runInContext('(function(){'+p.handlers[i]+'}).call(box)',ctx)}
function print(expected){ctx.printSelected();assert.deepEqual(prints.at(-1),expected);assert(wrappers.every(w=>w.style.display==='block'));}
switch(p.scenario){
 case 'initial': print(['101','202']);break;
 case 'uncheck': toggle(0,false);print(['202']);break;
 case 'uncheck_all': toggle(0,false);toggle(1,false);print([]);break;
 case 'select_none_then_one':ctx.selectNone();toggle(1,true);print(['202']);break;
 case 'select_all_then_uncheck':ctx.selectNone();ctx.selectAll();toggle(1,false);print(['101']);break;
 case 'toggle_repeatedly':toggle(0,false);toggle(0,true);toggle(0,false);print(['202']);break;
 case 'string_id':boxes[0].checked=false;ctx.toggleMaterial(boxes[0],'101');print(['202']);break;
 case 'browser_restored':print(['202']);break;
 case 'unrelated_checkbox':ctx.selectAll();assert.equal(unrelated.checked,false);unrelated.checked=true;ctx.selectNone();assert.equal(unrelated.checked,true);print([]);break;
 case 'no_auto_print':toggle(0,false);ctx.selectNone();ctx.selectAll();assert.equal(prints.length,0);ctx.printAll();assert.deepEqual(prints.at(-1),['101','202']);break;
}
process.stdout.write('ok');
"""
    node = shutil.which('node')
    assert node, 'Node is required for real template runtime tests'
    result = subprocess.run([node, '-e', program], input=json.dumps(payload), capture_output=True,
                            text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'ok'
