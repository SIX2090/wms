"""BUG-2026-10-24-018: run the real standalone editor and normalize saved layouts."""
import ast
import json
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes, self.scripts = [], []
        self.in_script = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.nodes.append([tag, dict(attrs)])
        if tag == 'script':
            self.in_script = True
            self.scripts.append('')

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_script = False

    def handle_data(self, data):
        if self.in_script:
            self.scripts[-1] += data


PROGRAM = r'''
const vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const htmlWrites=[],requests=[],messages=[],events={};
class El {
 constructor(tag,a={}){this.tagName=tag;this.attrs=a;this.id=a.id;this.dataset={};for(const[k,v]of Object.entries(a))if(k.startsWith('data-'))this.dataset[k.slice(5)]=v;this.value=a.value||'';this.style={};this.children=[];this.events={};this.colSpan=1;this.disabled=false;this._html='';this._text='';const classes=new Set((a.class||'').split(' '));this.classList={add:k=>classes.add(k),remove:k=>classes.delete(k),contains:k=>classes.has(k)};}
 addEventListener(k,f){this.events[k]=f;}
 appendChild(n){this.children.push(n);return n;}
 set textContent(v){this._text=String(v??'');this._html='';this.children=[];}
 get textContent(){return this._text+this._html.replace(/<[^>]*>/g,'')+this.children.map(c=>c.textContent).join('');}
 set innerHTML(v){this._html=String(v);this._text='';this.children=[];htmlWrites.push(String(v));}
 get innerHTML(){return this._html;}
 querySelector(s){return s==='.cell-content'?this.content:s==='.delete-cell'?this.del:null;}
 contains(n){return n===this;}
}
const nodes=p.nodes.map(([t,a])=>new El(t,a)),ids=Object.fromEntries(nodes.filter(n=>n.id).map(n=>[n.id,n]));
const cells=nodes.filter(n=>n.tagName==='td'&&n.id?.startsWith('cell-'));
for(const cell of cells){cell.content=new El('div');cell.content.textContent='EMPTY';cell.del=new El('button');cell.del.attrs.onclick='removeCell('+cell.dataset.row+','+cell.dataset.col+')';}
const align=nodes.filter(n=>n.attrs.class?.includes('align-btn')&&n.dataset.align);
const save=nodes.find(n=>n.attrs.onclick==='saveLayout()');
const document={getElementById:id=>ids[id]||null,createElement:t=>new El(t),querySelectorAll:s=>s==='.label-table td'?cells:s==='.align-btn'?align:[],querySelector:s=>s.includes('csrf-token')?{content:'fixture'}:s==='.align-btn.active'?align.find(n=>n.classList.contains('active')):s.includes('saveLayout')?save:null,addEventListener:(k,f)=>events[k]=f};
const ctx={document,Headers,FormData,showToast:(m,t)=>messages.push({m,t}),confirm:()=>true,
fetch:async(url,options)=>{requests.push({url,body:JSON.parse(options.body)});return{ok:true,status:200,json:async()=>({status:'success'})};}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.source,ctx);events.DOMContentLoaded();
const first=ids['cell-0-0'];
const initial={text:first.content.textContent,style:{...first.content.style},children:first.content.children.map(n=>({tag:n.tagName,text:n.textContent,style:n.style})),span:first.colSpan};
if(p.action==='edit')first.events.drop({preventDefault(){},dataTransfer:{getData:()=> 'spec'}});
if(p.action==='delete')vm.runInContext(first.del.attrs.onclick,ctx);
if(p.action==='clear')vm.runInContext('clearLayout()',ctx);
if(p.action==='style'){
 first.events.dblclick({});ids.styleFontSize.value='18';ids.styleColor.value='#123456';
 vm.runInContext('applyStyle()',ctx);
}
(async()=>{await vm.runInContext('saveLayout()',ctx);process.stdout.write(JSON.stringify({initial,requests,messages,htmlWrites,finalText:first.content.textContent,finalStyle:first.content.style,injected:ctx.injected===true}));})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''


def run_editor(layout, action='load'):
    env = Environment(loader=ChoiceLoader([
        DictLoader({'base.html': '{% block content %}{% endblock %}'}),
        FileSystemLoader(str(ROOT / 'app/templates')),
    ]), autoescape=True)
    html = env.get_template('label_template_detail.html').render(
        template=SimpleNamespace(id=7, name='fixture', width=90, height=50,
                                 rows=2, cols=2, layout=json.dumps(layout)),
        url_for=lambda *a, **kw: '/test')
    page = Page(html)
    assert len(page.scripts) == 1
    result = subprocess.run([shutil.which('node'), '-e', PROGRAM],
                            input=json.dumps({'source': page.scripts[0], 'nodes': page.nodes,
                                              'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
                                              'action': action}),
                            text=True, capture_output=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data['requests']) == 1
    assert data['requests'][0]['url'] == '/label_template/7/save_layout'
    assert data['messages'][-1]['t'] == 'success'
    return data, data['requests'][0]['body']['layout']


def normalize(layout):
    # Execute the real pure helper without importing the application or touching a DB.
    source = ast.parse((ROOT / 'app/app.py').read_text(encoding='utf-8'))
    fn = next(n for n in source.body if isinstance(n, ast.FunctionDef)
              and n.name == '_normalize_label_template_layout')
    namespace = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'normalizer', 'exec'), namespace)
    return namespace[fn.name](layout)['cells']


def layout_fixture(kind):
    cell = {'row': 0, 'col': 0, 'field': 'name', 'text': '[物料名称]', 'style': {}}
    if kind == 'keyed':
        return {'0-0': cell}
    if kind == 'mixed':
        return {'cells': [cell], '0-0': {'field': 'code', 'style': {}},
                '1-1': {'field': 'unit', 'style': {}}}
    return {'cells': [cell]}


@pytest.mark.parametrize('kind', ['cells', 'keyed', 'mixed'])
@pytest.mark.parametrize('action', ['load', 'edit', 'delete'])
def test_visible_and_saved_cells_agree(kind, action):
    data, saved = run_editor(layout_fixture(kind), action)
    if action == 'load':
        assert data['initial']['text'] == '示例物料'
    if action == 'edit':
        assert data['finalText'] == '规格示例'
    cells = normalize(saved)
    selected = [c for c in cells if int(c['row']) == 0 and int(c['col']) == 0]
    if action == 'delete':
        assert selected == [], 'Deleted cells must not reappear through the old cells list'
    else:
        assert len(selected) == 1
        assert selected[0]['field'] == ('spec' if action == 'edit' else 'name')
        assert saved['0-0']['field'] == selected[0]['field']
    if kind == 'mixed':
        assert any(int(c['row']) == 1 and c['field'] == 'unit' for c in cells)


@pytest.mark.parametrize('kind', ['cells', 'keyed', 'mixed'])
def test_clear_removes_all_cells_but_keeps_metadata(kind):
    layout = {**layout_fixture(kind), 'rows': 2, 'cols': 2, 'rowHeights': [60, 30],
              'labelWidth': 90, 'labelHeight': 50, 'marginTop': 3,
              'customMetadata': {'note': 'retain'}}
    _, saved = run_editor(layout, 'clear')
    assert normalize(saved) == []
    for key in ('rows', 'cols', 'rowHeights', 'labelWidth', 'labelHeight', 'marginTop', 'customMetadata'):
        assert saved[key] == layout[key]
    assert not any(key[0].isdigit() and '-' in key for key in saved)


@pytest.mark.parametrize('text', ['固定标题', '<img src=x onerror="injected=true">&文字',
                                  '</script><script>injected=true</script>', '引号\'"\\\n'])
def test_static_text_is_safe_and_survives_save(text):
    data, saved = run_editor({'cells': [{'row': '0', 'col': '0', 'field': '', 'text': text,
                                       'style': {}}]})
    assert data['initial']['text'] == text
    assert normalize(saved)[0]['text'] == text
    assert not data['injected']
    assert all(text not in fragment for fragment in data['htmlWrites'])
    assert data['initial']['children'][0]['tag'] == 'span'


@pytest.mark.parametrize('action', ['load', 'style'])
def test_styles_and_cell_metadata_survive_round_trip(action):
    cell = {'row': 0, 'col': 0, 'field': 'name', 'text': '[物料名称]', 'colSpan': 2,
            'barcodeWidth': 40, 'barcodeHeight': 15, 'customCell': {'x': 1},
            'style': {'fontSize': '15px', 'fontWeight': 'bold', 'verticalAlign': 'bottom',
                      'fontFamily': 'Arial', 'color': '#333333', 'textAlign': 'left'}}
    data, saved = run_editor({'cells': [cell]}, action)
    assert data['initial']['style']['fontSize'] == '15px'
    assert data['initial']['style']['fontWeight'] == 'bold'
    assert data['initial']['style']['verticalAlign'] == 'bottom'
    result = normalize(saved)[0]
    assert result['style']['fontWeight'] == 'bold'
    assert result['style']['verticalAlign'] == 'bottom'
    if action == 'style':
        assert result['style']['fontSize'] == 18
        assert result['style']['color'] == '#123456'
    for key in ('colSpan', 'barcodeWidth', 'barcodeHeight', 'customCell'):
        assert result[key] == cell[key]


def test_unknown_metadata_is_not_treated_as_a_cell():
    _, saved = run_editor({'cells': [{'row': 0, 'col': 0, 'field': 'name'}],
                           'version': None, 'customMetadata': {'x': 1}})
    assert saved['version'] is None
    assert saved['customMetadata'] == {'x': 1}


@pytest.mark.parametrize('action', ['edit', 'delete', 'clear'])
def test_saved_layout_reopens_through_actual_normalizer(action):
    _, saved = run_editor(layout_fixture('mixed'), action)
    normalized_cells = normalize(saved)
    selected = [c for c in normalized_cells if int(c['row']) == 0 and int(c['col']) == 0]
    if action == 'edit':
        assert len(selected) == 1 and selected[0]['field'] == 'spec'
    else:
        assert selected == []
    reopened, saved_again = run_editor({**saved, 'cells': normalized_cells})
    if action == 'edit':
        assert reopened['initial']['text'] == '规格示例'
    else:
        assert reopened['initial']['text'] == 'EMPTY'
    assert normalize(saved_again) == normalized_cells
