"""Real shell DOM and keyboard registration order must not turn Escape into a second action."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

from bs4 import BeautifulSoup
from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('save_fixture', ROOT / 'tests/test_keyboard_save_semantics.py')
save_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(save_fixture)


def markup(template='out_order_add.html', role='admin', **context):
    source = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    start = source.index('<nav class="sidebar"')
    sidebar = Environment().from_string(source[start:source.index('</nav>', start) + 6]).render(
        current_user=SimpleNamespace(role=role), url_for=lambda name, **kwargs: '/' + name, config={})
    return sidebar + '<div class="embedded-content">' + save_fixture._header(template, **context) + '</div>'


PROGRAM = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const source=require('node:fs').readFileSync(p.source,'utf8');
const start=source.indexOf('function initKeyboardShortcuts()');
const code=source.slice(start,source.indexOf('// 最近访问管理',start));
const listeners={wc:[],dc:[],db:[],wb:[]},trace=[],clicks=[];
let popupVisible=p.popupVisible!==false,sidebarOpen=!!p.mobile;
function element(data={}) {
 const attrs={...(data.attrs||{})};
 const e={...data,attrs,children:[],isConnected:true,innerHTML:'',title:'',
  classList:{contains:()=>false,add(){}},
  setAttribute(k,v){attrs[k]=String(v);},getAttribute:k=>attrs[k]??null,hasAttribute:k=>k in attrs,
  getClientRects(){return this.invisible?[]:[{}];},
  matches:s=>s===':disabled'&&('disabled' in attrs||!!e.fieldsetDisabled),
  closest(s){if(e.hidden)return {};if(s.includes('.modal')&&(e.dialog||e.readonly))return {};return null;},
  appendChild(child){child.content=true;this.children.push(child);},
  addEventListener(type,fn){if(type==='click')this.callback=fn;},
  click(){if(this.matches(':disabled'))return;clicks.push({href:attrs.href||'',label:this.label||this.title,content:!!this.content});if(this.callback)this.callback();}
 };return e;
}
const nodes=p.nodes.map(element),sidebar=element({});
const candidates=()=>nodes.concat(content.children.flatMap(n=>n.children));
const content={children:[],firstChild:null,
 insertBefore(n){this.children.unshift(n);},
 querySelectorAll(s){const attr=s.includes('data-wms-new')?'data-wms-new':s.includes('data-wms-back')?'data-wms-back':'data-wms-save';return candidates().filter(n=>n.content&&n.hasAttribute(attr));}};
const document={body:{classList:{contains:s=>s==='mobile-sidebar-open'&&sidebarOpen,add(){}}},
 addEventListener:(name,fn,capture)=>listeners[capture?'dc':'db'].push(fn),
 getElementById:id=>id==='appSidebar'?sidebar:null,
 querySelector(s){
  if(s==='.embedded-content')return p.noContent?null:content;
  if(s==='.modal.show, .cb-confirm-overlay.show'||s==='.modal.show')return p.popup==='.modal.show'&&popupVisible?{}:null;
  if(p.original[s]!==undefined)return nodes[p.original[s]];
  return null;
 },
 querySelectorAll(s){return p.popup&&s.split(',').map(x=>x.trim()).includes(p.popup)?[{closest:()=>null,getClientRects:()=>popupVisible?[{}]:[]}]:[];},
 createElement:()=>element()
};
const ctx={document,WeakSet,showToast(){},
 getComputedStyle:e=>({visibility:e.cssHidden?'hidden':'visible'}),
 addEventListener:(name,fn,capture)=>listeners[capture?'wc':'wb'].push(fn),
 location:{pathname:'/current/add'},openAdd:()=>trace.push('openAdd'),
 isWmsEmbeddedPage:()=>true,getWmsActionModule:()=>({listUrl:'/current',addUrl:'/current/add'}),
 isWmsListPage:()=>false,isFormPage:()=>true,pageHasOwnButton:()=>false,pageHasOwnListAction:()=>false,
 trimWmsActionbarDividers:x=>x,createDocumentNavigationGroup:()=>null,saveCurrentPage(){},escapeHtml:x=>x};
ctx.window=ctx;vm.createContext(ctx);
function extract(name){let a=source.indexOf('function '+name+'('),depth=0;assert(a>=0,name);for(let i=source.indexOf('{',a);i<source.length;i++){if(source[i]==='{')depth++;if(source[i]==='}'&&!--depth)return source.slice(a,i+1);}}
if(p.global){vm.runInContext(extract('insertGlobalActionBar'),ctx);ctx.insertGlobalActionBar();}
if(p.mobile){
 ctx.closeMobileSidebar=()=>{sidebarOpen=false;trace.push('sidebar closed');};
 const mobile=source.match(/document.addEventListener\('keydown', function\(event\) \{\s*if \(event.key === 'Escape'\) closeMobileSidebar\(\);\s*\}\);/);
 assert(mobile);vm.runInContext(mobile[0],ctx);
}
vm.runInContext(code,ctx);ctx.initKeyboardShortcuts();
if(typeof ctx.initNavigationShortcuts==='function')ctx.initNavigationShortcuts();
if(p.consumer) document.addEventListener('keydown',e=>{
 trace.push('component '+p.consumer);
 if(p.consumer==='prevent')e.preventDefault();
 if(p.consumer==='stop')e.stopPropagation();
 if(p.consumer==='close')popupVisible=false;
 if(p.consumer==='open')popupVisible=true;
},p.capture);
const event={key:p.key||'Escape',ctrlKey:!!p.ctrl,metaKey:!!p.meta,altKey:!!p.alt,shiftKey:!!p.shift,
 isComposing:!!p.composing,keyCode:p.legacyIme?229:27,repeat:!!p.repeat,defaultPrevented:!!p.handled,
 target:{tagName:p.tag||'BODY',isContentEditable:!!p.editable},
 preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.cancelBubble=true;},
 stopImmediatePropagation(){this.cancelBubble=true;this.immediate=true;}};
for(const phase of ['wc','dc','db','wb']){if(event.cancelBubble)break;for(const fn of listeners[phase]){fn(event);if(event.immediate)break;}}
process.stdout.write(JSON.stringify({clicks,trace,prevented:event.defaultPrevented,sidebarOpen}));
'''


def run(html, **options):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    soup = BeautifulSoup(html, 'html.parser')
    controls = soup.select('a, button')
    original = {}
    for selector in ['a[href*="/add"], .btn-add, [onclick*="addNewRow"]',
                     'a[href*="返回列表"], .btn-back, a[href$="/in_order"], a[href$="/requisition"]']:
        found = soup.select_one(selector)
        if found:
            original[selector] = controls.index(found)
    nodes = []
    for control in controls:
        parents = [control, *control.parents]
        content = any('embedded-content' in n.get('class', []) for n in parents)
        marked = content and any(key in control.attrs for key in ['data-wms-new', 'data-wms-back'])
        attrs = dict(control.attrs)
        if marked and options.get('disabled'):
            attrs['disabled'] = ''
        if marked and options.get('ariaDisabled'):
            attrs['aria-disabled'] = 'true'
        nodes.append(dict(attrs=attrs, label=control.get_text(' ', strip=True), content=content,
            hidden=marked and options.get('hidden', False), invisible=marked and options.get('invisible', False),
            cssHidden=marked and options.get('cssHidden', False), readonly=marked and options.get('readonly', False),
            fieldsetDisabled=marked and options.get('fieldsetDisabled', False), dialog=marked and options.get('dialog', False)))
    result = subprocess.run([node, '-e', PROGRAM], input=json.dumps(dict(options, source=str(ROOT / 'app/static/js/app.js'), nodes=nodes, original=original)),
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('template,context', [
    ('_other_order_toolbar.html', {'toolbar_mode': 'out'}),
    ('in_order_add.html', {'business_type': '采购入库'}),
    ('in_order_add.html', {'business_type': '其他入库', 'is_other_in': True}),
    ('out_order_add.html', {}), ('out_order_add.html', {'is_sale_order': True}),
    ('out_order_add.html', {'is_other_out': True}), ('out_order_add.html', {'is_purchase_return': True}),
    ('document_table_form.html', {'can_save': True, 'doc_type': 'requisition', 'list_url': '/requisition'}),
    ('purchase_order_add.html', {}), ('purchase_request_add.html', {}),
    ('after_sale_out_add.html', {'can_edit_after_sale_out': True}), ('adjustment_add.html', {}),
])
def test_escape_uses_only_actual_page_return_control(template, context):
    result = run(markup(template, **context))
    assert len(result['clicks']) == 1
    assert result['clicks'][0]['content']
    assert result['prevented']


@pytest.mark.parametrize('role', ['admin', 'warehouse', 'purchase', 'production', 'sales', 'viewer', 'finance', 'user'])
@pytest.mark.parametrize('key', ['n', 'Escape'])
def test_sidebar_never_supplies_an_action_when_page_has_none(role, key):
    html = markup(role=role).split('<div class="embedded-content">')[0] + '<div class="embedded-content"><button onclick="addNewRow()">新增行</button><button>保存并新增</button></div>'
    assert run(html, key=key, ctrl=key == 'n')['clicks'] == []


@pytest.mark.parametrize('global_bar', [False, True])
def test_ctrl_n_clicks_explicit_new_document_including_real_global_renderer(global_bar):
    result = run(markup('_other_order_toolbar.html', toolbar_mode='out') if not global_bar else markup(), key='n', ctrl=True, **{'global': global_bar})
    assert len(result['clicks']) == 1 and result['clicks'][0]['content']
    assert result['clicks'][0]['label'] == '新增'
    if global_bar:
        assert result['trace'] == ['openAdd']


@pytest.mark.parametrize('option,key', [(option, key)
    for option in ['disabled', 'ariaDisabled', 'hidden', 'invisible', 'cssHidden', 'readonly', 'fieldsetDisabled', 'dialog', 'noContent']
    for key in ['n', 'Escape'] if key == 'n' or option not in ['disabled', 'fieldsetDisabled']])
def test_unavailable_actions_are_not_clicked(option, key):
    assert run(markup('_other_order_toolbar.html', toolbar_mode='out'), key=key, ctrl=key == 'n', **{option: True})['clicks'] == []


@pytest.mark.parametrize('boundary', [{'composing': True}, {'legacyIme': True}, {'handled': True}, {'repeat': True},
    {'editable': True}, {'tag': 'INPUT'}, {'tag': 'TEXTAREA'}, {'tag': 'SELECT'}, {'shift': True}, {'alt': True}, {'meta': True}])
@pytest.mark.parametrize('key', ['n', 'Escape'])
def test_navigation_respects_keyboard_boundaries(boundary, key):
    assert run(markup('_other_order_toolbar.html', toolbar_mode='out'), key=key, ctrl=key == 'n', **boundary)['clicks'] == []


@pytest.mark.parametrize('consumer,capture', [('prevent', False), ('stop', False), ('prevent', True)])
def test_later_registered_component_can_consume_escape(consumer, capture):
    result = run(markup(), consumer=consumer, capture=capture)
    assert result['clicks'] == []
    assert result['trace'] == ['component ' + consumer]


POPUPS = ['.modal.show', '.offcanvas.show', '.offcanvas.showing', 'dialog[open]', '[role="dialog"]',
    '.cb-confirm-overlay.show', '.ai-assistant-panel.open', '.wms-row-context-menu.show', '.module-menu.open .module-flyout',
    '.dropdown-menu.show', '.wms-contract-dropdown', '.ks-menu', '.cb-column-panel.show',
    '.picker-dropdown', '.material-dropdown', '.supplier-dropdown', '#supplierDropdown', '#customerDropdown',
    '#projectNameDropdown', '#sourceInOrderDropdown', '.flatpickr-calendar.open']


@pytest.mark.parametrize('popup', POPUPS)
@pytest.mark.parametrize('consumer', [None, 'close'])
def test_visible_component_owns_escape_even_when_closed_before_window_bubbling(popup, consumer):
    assert run(markup(), popup=popup, consumer=consumer, tag='BUTTON')['clicks'] == []


@pytest.mark.parametrize('popup', POPUPS)
def test_hidden_component_does_not_disable_navigation(popup):
    result = run(markup(), popup=popup, popupVisible=False)
    assert len(result['clicks']) == 1 and result['clicks'][0]['content']


@pytest.mark.parametrize('popup', POPUPS)
def test_visible_component_also_blocks_ctrl_n_from_button_focus(popup):
    assert run(markup('_other_order_toolbar.html', toolbar_mode='out'), key='n', ctrl=True, tag='BUTTON', popup=popup)['clicks'] == []


def test_mobile_sidebar_closes_without_returning_on_the_same_escape():
    result = run(markup(), mobile=True)
    assert result['trace'] == ['sidebar closed'] and not result['sidebarOpen']
    assert result['clicks'] == []


def test_component_opened_by_an_earlier_handler_also_prevents_navigation():
    assert run(markup(), popup='.modal.show', popupVisible=False, consumer='open')['clicks'] == []
