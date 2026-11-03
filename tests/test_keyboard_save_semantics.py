"""Ctrl+S must follow an explicit ordinary-save button, never a generic submit."""
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]


def _header(filename, **context):
    source = (ROOT / 'app/templates' / filename).read_text(encoding='utf-8')
    if filename == '_other_order_toolbar.html':
        fragment = source
    else:
        fragment = source.split('{% block content %}', 1)[1]
        end = '<div class="card'
        if filename == 'document_table_form.html':
            end = '<div class="doc-body">'
        elif filename == 'adjustment_add.html':
            end = '<div class="adjust-body">'
        fragment = fragment.split(end, 1)[0]
    env = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=True)
    return env.from_string(fragment).render(
        url_for=lambda *args, **kwargs: '/fixture',
        order=SimpleNamespace(order_no='SO1', id=1), **context)


def _run(html, **options):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for real keyboard handler checks')
    soup = BeautifulSoup(html, 'html.parser')
    nodes = []
    for button in soup.select('button, input[type=submit]'):
        ancestors = list(button.parents)
        def has_class(item, name):
            return name in item.get('class', [])
        nodes.append({
            'attrs': button.attrs,
            'label': button.get_text(' ', strip=True),
            'modal': any(has_class(item, 'modal') or item.get('role') == 'dialog' for item in ancestors),
            'hidden': any(item.has_attr('hidden') or item.has_attr('inert') or item.get('aria-hidden') == 'true' for item in [button, *ancestors]),
            'readonly': any(has_class(item, 'readonly-mask') for item in ancestors),
            'fieldsetDisabled': any(item.name == 'fieldset' and item.has_attr('disabled') for item in ancestors),
        })
    script = r'''
const fs = require('node:fs'), vm = require('node:vm');
const p = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(p.source, 'utf8');
const start = source.indexOf('function initKeyboardShortcuts()');
const end = source.indexOf('// 最近访问管理', start);
let handler, clicks=[], calls=[], messages=[], prevented=0;
const nodes=p.nodes.map(n=>({...n, disabled:'disabled' in n.attrs,
  getAttribute(k){return this.attrs[k] ?? null;},
  hasAttribute(k){return k in this.attrs;},
  getClientRects(){return this.hidden || p.invisible ? [] : [{}];},
  matches(s){return s === ':disabled' && (this.disabled || this.fieldsetDisabled);},
  closest(s){return this.modal || this.hidden || this.readonly ? {} : null;},
  click(){if(this.disabled || this.fieldsetDisabled)return; clicks.push(this.label);
    if(this.attrs.onclick)vm.runInContext(this.attrs.onclick,ctx);
    else calls.push(this.attrs.id || this.attrs['data-action'] || 'submit');}
}));
const content={querySelectorAll(){return nodes.filter(n=>'data-wms-save' in n.attrs);}};
const document={addEventListener(n,h){handler=h;},
  querySelector(s){
    if(s === '.embedded-content')return content;
    if(s.includes('.modal.show'))return p.openModal?{}:null;
    if(s.includes('[onclick*="submitForm"]'))return nodes.find(n=>(n.attrs.onclick||'').includes('submitForm') || n.attrs.type==='submit' || (n.attrs.class||[]).includes('btn-save')) || null;
    return null;
  }};
const ctx={document, showToast:(...args)=>messages.push(args),submitForm:(...args)=>calls.push(args),
  handleOtherOrderToolbar:(...args)=>calls.push(args),window:{getComputedStyle:()=>({visibility:p.cssHidden?'hidden':'visible'})}};
vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);ctx.initKeyboardShortcuts();
handler({target:{tagName:p.tag || 'BODY',isContentEditable:!!p.editable},
  ctrlKey:!p.meta,metaKey:!!p.meta,key:'s',altKey:false,shiftKey:false,
  defaultPrevented:!!p.defaultPrevented,isComposing:!!p.composing,keyCode:p.composing?229:83,
  repeat:!!p.repeat,preventDefault(){prevented++;}});
console.log(JSON.stringify({clicks,calls,messages,prevented}));
'''
    result = subprocess.run([node, '-e', script], input=json.dumps({
        'source': str(ROOT / 'app/static/js/app.js'), 'nodes': nodes, **options}),
        text=True, encoding='utf-8', capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('filename,context,expected', [
    ('purchase_order_add.html', {}, [False]),
    ('purchase_request_add.html', {}, []),
    ('in_order_add.html', {'business_type': '产品入库'}, [False, False]),
    ('out_order_add.html', {'is_sale_order': True}, []),
    ('out_order_add.html', {'is_purchase_return': True}, []),
    ('after_sale_out_add.html', {'can_edit_after_sale_out': True}, []),
    ('adjustment_add.html', {}, [False]),
    ('document_table_form.html', {'can_save': True, 'doc_type': 'transfer', 'complete_url': '/complete'}, [False]),
    ('document_table_form.html', {'can_save': True, 'doc_type': 'check'}, [False]),
])
def test_real_template_ctrl_s_uses_ordinary_save(filename, context, expected):
    result = _run(_header(filename, **context))
    assert result['calls'] == [expected]
    assert result['prevented'] == 1


@pytest.mark.parametrize('filename', ['sales_order_add.html', 'sales_order_edit.html'])
def test_sales_save_button_works_without_inline_handler(filename):
    assert _run(_header(filename))['calls'] == ['saveBtn']


@pytest.mark.parametrize('filename,context', [
    ('in_order_add.html', {'business_type': '采购入库'}),
    ('out_order_add.html', {}),
    ('document_table_form.html', {'can_save': True, 'doc_type': 'requisition', 'complete_url': '/complete'}),
    ('document_table_form.html', {'can_save': False, 'doc_type': 'transfer'}),
    ('adjustment_add.html', {'readonly': True}),
    ('after_sale_out_add.html', {'can_edit_after_sale_out': False}),
])
def test_combined_action_and_readonly_pages_do_not_submit(filename, context):
    result = _run(_header(filename, **context))
    assert result['calls'] == []
    assert result['prevented'] == 1


@pytest.mark.parametrize('mode', ['in', 'out'])
def test_other_order_toolbar_only_uses_save(mode):
    assert _run(_header('_other_order_toolbar.html', toolbar_mode=mode, has_complete_action=True))['calls'] == ['save']


@pytest.mark.parametrize('html,options', [
    ('<form><button type="submit">搜索</button></form>', {}),
    ('<div class="modal"><button data-wms-save onclick="submitForm()">保存</button></div>', {}),
    ('<div hidden><button data-wms-save onclick="submitForm()">保存</button></div>', {}),
    ('<div class="readonly-mask"><button data-wms-save onclick="submitForm()">保存</button></div>', {}),
    ('<fieldset disabled><button data-wms-save onclick="submitForm()">保存</button></fieldset>', {}),
    ('<button data-wms-save disabled onclick="submitForm()">保存</button>', {}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'openModal': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'invisible': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'cssHidden': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'defaultPrevented': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'composing': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'repeat': True}),
    ('<button data-wms-save onclick="submitForm()">保存</button>', {'editable': True}),
])
def test_ctrl_s_does_not_submit_unavailable_or_unrelated_actions(html, options):
    assert _run(html, **options)['calls'] == []


@pytest.mark.parametrize('tag', ['INPUT', 'TEXTAREA', 'SELECT', 'BODY'])
def test_explicit_save_works_while_editing_fields(tag):
    assert _run(_header('purchase_order_add.html'), tag=tag)['calls'] == [[False]]


def test_command_s_uses_the_same_ordinary_save():
    assert _run(_header('purchase_order_add.html'), meta=True)['calls'] == [[False]]


def test_markers_never_label_combined_actions():
    for path in (ROOT / 'app/templates').glob('*.html'):
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        for button in soup.select('[data-wms-save]'):
            assert '完成' not in button.get_text() and '新增' not in button.get_text() and '新建' not in button.get_text()
            assert not button.has_attr('data-wms-save-complete')
