"""Execute the shell navigation script and verify its real cacheable loading."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

import app as app_module
from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]
ASSET = 'js/pages/shell-navigation.js'


def render_shell(role='viewer'):
    return Environment(autoescape=True).from_string(
        (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    ).render(current_user=SimpleNamespace(is_authenticated=True, role=role, username='fixture', id=1),
             csrf_token=lambda: 'fixture-token', config={'STATIC_VERSION': 'nav-test-v1'},
             request=SimpleNamespace(args={}),
             url_for=lambda endpoint, **values: '/static/' + values['filename'] if endpoint == 'static' else '/' + endpoint)


@pytest.mark.parametrize('role', ['viewer', 'warehouse', 'admin'])
def test_navigation_loads_once_in_its_original_execution_position(role):
    class Scripts(HTMLParser):
        def __init__(self):
            super().__init__()
            self.sources = []

        def handle_starttag(self, tag, attrs):
            if tag == 'script':
                self.sources.append(dict(attrs))

    html = render_shell(role)
    parser = Scripts()
    parser.feed(html)
    matches = [attrs for attrs in parser.sources if attrs.get('src') == '/static/' + ASSET + '?v=nav-test-v1']
    assert len(matches) == 1
    assert not {'async', 'defer', 'type'} & matches[0].keys()
    assert html.index('css/shell.css') < html.index(ASSET) < html.index('function refreshCsrfToken')
    assert 'function closeModuleMenus' not in html
    assert 'function toggleModuleMenu' not in html


def test_navigation_extraction_preserves_original_script_bytes():
    source = (ROOT / 'app/static' / ASSET).read_text(encoding='utf-8').encode('utf-8')
    # Entire original script, including comments, whitespace and execution order.
    assert hashlib.sha256(source).hexdigest() == '7c1980c6162a90fba5092a81504ad5fa0d7109598d1ca0dc7daedab6716e417a'
    assert b'{{' not in source and b'{%' not in source


def test_navigation_response_supports_browser_cache_and_etag():
    client = app_module.app.test_client()
    response = client.get('/static/' + ASSET + '?v=nav-test-v1')
    assert response.status_code == 200
    assert response.mimetype in {'text/javascript', 'application/javascript'}
    assert response.data == (ROOT / 'app/static' / ASSET).read_bytes()
    assert response.cache_control.public and response.cache_control.max_age == 31536000
    assert response.headers['ETag']
    assert client.get('/static/' + ASSET, headers={'If-None-Match': response.headers['ETag']}).status_code == 304


@pytest.mark.parametrize('path,query,expected', [
    ('/in_order', '?type=purchase_in', '采购管理'),
    ('/in_order', '?type=product_in', '产品管理'),
    ('/in_order', '?type=product_in&embedded=1', '产品管理'),
    ('/in_order/7/edit', '', '采购管理'),
    ('/', '', None), ('/unlisted', '', None),
])
def test_actual_script_preserves_menu_breadcrumb_date_and_touch_behavior(path, query, expected):
    # Resolve the script from the actual template; old inline source is also runnable
    # during the rollback check so behavior controls do not fail on a missing file.
    template = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    if "filename='" + ASSET + "'" in template:
        source = (ROOT / 'app/static' / ASSET).read_text(encoding='utf-8')
    else:
        source = next(body for body in re.findall(r'<script>(.*?)</script>', template, re.S) if 'function closeModuleMenus' in body)
    node = shutil.which('node')
    assert node, 'Node.js required for shell navigation behavior'
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const listeners={},timers=[];let hover=null;
function element(){const classes=new Set();return {attrs:{},dataset:{},children:[],style:{},textContent:'',hidden:true,
 classList:{contains:k=>classes.has(k),add:k=>classes.add(k),remove:k=>classes.delete(k),toggle(k,on){if(on)classes.add(k);else classes.delete(k);}},
 setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k]??null;},appendChild(child){this.children.push(child);},
 addEventListener(name,fn){this[name]=fn;}};}
const menus=[element(),element()],buttons=[element(),element()];
menus.forEach((menu,i)=>{menu.querySelector=()=>buttons[i];buttons[i].closest=()=>menu;});
const sidebar=element(),date=element(),nav=element(),list=element();date.value='2026-10-24';
function link(href,module){const node=element();node.attrs.href=href;node.textContent='menu';
 node.closest=()=>({querySelector:()=>({textContent:module})});return node;}
const links=[link('/in_order?type=purchase_in','采购管理'),link('/in_order?type=product_in','产品管理')];
const document={title:'明细 <原样显示>',
 addEventListener(name,fn,options){(listeners[name]??=[]).push({fn,options});},
 querySelectorAll(s){if(s==='.module-menu.open')return menus.filter(m=>m.classList.contains('open'));
 if(s==='input[type="date"]')return [date];if(s==='.sidebar .flyout-link[href]')return links;throw Error(s);},
 querySelector(s){if(s==='.sidebar')return sidebar;if(s==='.module-menu:hover')return hover;
 if(s==='.module-menu.open')return menus.find(m=>m.classList.contains('open'))||null;throw Error(s);},
 getElementById:id=>id==='wmsBreadcrumb'?nav:id==='wmsBreadcrumbList'?list:null,
 createElement(tag){const node=element();if(tag==='a')Object.defineProperty(node,'href',{set(value){const u=new URL(value,'https://wms.test');node.pathname=u.pathname;node.search=u.search;}});return node;}};
const ctx={document,Date,URLSearchParams,window:{location:{pathname:p.path,search:p.query},setTimeout:(fn,delay)=>timers.push({fn,delay})}};
vm.createContext(ctx);vm.runInContext(p.source,ctx);
assert.equal(date.attrs.lang,undefined,'initializers must wait for DOM readiness');
for(const item of listeners.DOMContentLoaded)item.fn();
assert.equal(date.attrs.placeholder,'YYYY-MM-DD');assert.equal(date.attrs.lang,'zh-CN');assert.equal(date.style.fontVariantNumeric,'tabular-nums');
if(p.expected){assert.equal(nav.hidden,false);assert.equal(list.children.length,3);
 assert.equal(list.children[0].children[0].textContent,'首页');assert.equal(list.children[1].textContent,p.expected);
 assert.equal(list.children[2].textContent,document.title);assert.equal(list.children[2].attrs['aria-current'],'page');}
else {assert.equal(nav.hidden,true);assert.equal(list.children.length,0);}
ctx.toggleModuleMenu(buttons[0]);assert(menus[0].classList.contains('open'));assert.equal(buttons[0].attrs['aria-expanded'],'true');
listeners.mouseover[0].fn({target:{closest:()=>menus[1]}});
assert(!menus[0].classList.contains('open'));assert.equal(buttons[0].attrs['aria-expanded'],'false');assert(menus[1].classList.contains('open'));
assert.equal(menus[1].dataset.openedByHover,'true');ctx.toggleModuleMenu(buttons[1]);assert(menus[1].classList.contains('open'));
ctx.toggleModuleMenu(buttons[1]);assert(!menus[1].classList.contains('open'));assert.equal(buttons[1].attrs['aria-expanded'],'false');
ctx.toggleModuleMenu(buttons[0]);listeners.click[0].fn({target:{closest:s=>s==='.module-menu'?menus[0]:null}});assert(menus[0].classList.contains('open'));
listeners.click[0].fn({target:{closest:()=>null}});assert(!menus[0].classList.contains('open'));
ctx.toggleModuleMenu(buttons[0]);listeners.click[0].fn({target:{closest:s=>s.includes('flyout-link')?links[0]:menus[0]}});assert(!menus[0].classList.contains('open'));
ctx.toggleModuleMenu(buttons[0]);sidebar.mouseleave();assert.equal(timers[0].delay,120);hover=menus[0];timers.shift().fn();assert(menus[0].classList.contains('open'));
sidebar.mouseleave();hover=null;timers.shift().fn();assert(!menus[0].classList.contains('open'));
let prevented=0;const event={touches:[{},{}],preventDefault:()=>prevented++};
assert.equal(listeners.touchstart[0].options.passive,false);listeners.touchstart[0].fn(event);assert.equal(prevented,1);
event.touches=[{}];listeners.touchstart[0].fn(event);assert.equal(prevented,1);
listeners.wheel[0].fn({...event,ctrlKey:false});assert.equal(prevented,1);listeners.wheel[0].fn({...event,ctrlKey:true});assert.equal(prevented,2);
listeners.dblclick[0].fn(event);assert.equal(prevented,3);
'''
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(source=source, path=path, query=query, expected=expected)),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
