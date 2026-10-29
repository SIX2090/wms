"""Run the material designer against field-only legacy layouts and its real preview."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

from tests.test_material_label_editor_state_runtime import Nodes, PROGRAM

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('field,label,canonical', [
    ('name', '物料名称', 'name'), ('unit', '单位', 'unit_name'),
    ('category', '分类', 'category_name'), ('supplier', '供应商', 'supplier_name')])
def test_legacy_field_only_cells_load_as_visible_editable_bindings(field, label, canonical):
    template = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    source = template[template.index('// 标签打印模板相关函数'):
                      template.index('// ==================== 所见即所得预览')]
    start = template.index('<div class="modal fade" id="labelTemplateModal"')
    nodes = Nodes(template[start:template.index('<script>', start)]).nodes
    branch = r'''
 if(p.action==='audit_field'){
  ctx.loadTemplateToEditor({rows:1,cols:1,width:90,height:50,layout:{cells:[
   {row:0,col:0,field:p.field,style:{fontSize:13}}
  ]}});
  const content=ids.labelTable.querySelector('.cell-content');
  assert.equal(content.textContent,'['+p.label+']');
  assert.equal(content.dataset.field,p.canonical);
  assert.equal(content.style.fontSize,'13px');
  const saved=ctx.__captureSnapshot();
  assert.equal(saved.cells[0].field,p.canonical);
  assert.equal(saved.cells[0].text,'['+p.label+']');
  return;
 }
'''
    program = PROGRAM.replace(" await ready();rendered('A');", branch + " await ready();rendered('A');")
    assert branch in program
    result = subprocess.run([shutil.which('node'), '-e', program],
        input=json.dumps(dict(action='audit_field', scenario='success', field=field,
            label=label, canonical=canonical, nodes=nodes, source=source,
            api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))),
        text=True, capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


class PrintStructure(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.stack, self.rows, self.tables = [], [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.tables.append(dict(attrs))
        if tag == 'tr':
            self.rows.append((list(self.stack), dict(attrs)))
        if tag not in ('img', 'br', 'hr', 'input', 'meta', 'link'):
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]


def test_real_label_preview_keeps_table_structure_and_fits_label_height():
    template = (ROOT / 'app/templates/material.html').read_text(encoding='utf-8')
    source = template[template.index('function __escapeHtml('):template.index('function previewLabel()')]
    alias = re.search(r'function __labelFieldKey\([^)]*\) \{.*?\n\}', template, re.S)
    if alias:
        source = alias[0] + '\n' + source
    program = r'''
const vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const output={innerHTML:''},model={rows:5,cols:1,labelWidth:90,labelHeight:50,
 rowHeights:[24,36,22,22,22],cells:['name','barcode','code','spec','unit_name'].map((field,row)=>
 ({row,col:0,field,text:'['+field+']',style:{fontSize:'12px',fontWeight:'normal',textAlign:'center'}}))};
const ctx={document:{getElementById:id=>id==='previewContent'?output:{checked:false}},
 __buildLabelModel:()=>model,previewUseSample:true,
 labelSampleData:{name:'验收产品',code:'M29',barcode:'M29',spec:'验收规格',unit_name:'件'},
 location:{origin:'http://fixture'}};
vm.createContext(ctx);vm.runInContext(p.source,ctx);ctx.__renderPreview();
process.stdout.write(output.innerHTML);
'''
    result = subprocess.run([shutil.which('node'), '-e', program],
        input=json.dumps({'source': source}), text=True, encoding='utf-8',
        capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    structure = PrintStructure(result.stdout)
    assert len(structure.tables) == 1
    assert len(structure.rows) == 5
    assert all('table' in ancestors for ancestors, attrs in structure.rows)
    heights = [float(re.search(r'height:\s*([\d.]+)px', attrs['style'])[1])
               for ancestors, attrs in structure.rows]
    assert sum(heights) <= 201, 'row heights must be scaled into the 50mm label, not multiplied blindly'
    image_height = float(re.search(r'<img[^>]+height:([\d.]+)px', result.stdout)[1])
    assert image_height + 5 <= heights[1] + .01, 'barcode must fit inside its row including padding and borders'
    assert '验收产品' in result.stdout and '验收规格' in result.stdout


def test_old_technical_checkbox_caption_does_not_override_new_human_label():
    source = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    source = source[source.index('    function readState(table, columns) {'):
                    source.index('    function setHeaderLabel(th, label) {')]
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const saved={order:['actions','name'],hidden:[],labels:{actions:'actions',name:'自定义名称'}};
const ctx={CSS:{escape:s=>s},storageKey:()=> 'test',localStorage:{getItem:()=>JSON.stringify(saved)}};
vm.createContext(ctx);vm.runInContext(p.source,ctx);
const state=ctx.readState({querySelector:s=>s.includes('actions')?{}:null},
 [{key:'actions',label:'选择',locked:true},{key:'name',label:'名称',locked:false}]);
assert.equal(state.labels.actions,undefined);assert.equal(state.labels.name,'自定义名称');
'''
    result = subprocess.run([shutil.which('node'), '-e', program],
        input=json.dumps({'source': source}), text=True, capture_output=True,
        encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
