"""Render the shared pager and execute its actual change listener in Node."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app/templates'
PAGES = ['check', 'transfer', 'adjustment', 'requisition', 'subcontract',
         'subcontract_issue', 'subcontract_receive', 'stock_query']


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('old_size', [20, 100])
def test_page_size_change_keeps_filters_and_uses_selected_size(page, old_size):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (TEMPLATES / (page + '.html')).read_text(encoding='utf-8')
    assert 'pager(pagination,' in source
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)))
    env.globals['url_for'] = lambda endpoint, **kwargs: '/' + endpoint
    pagination = SimpleNamespace(total=150, per_page=old_size, page=3,
        has_prev=False, has_next=False, iter_pages=lambda **kw: [3])
    filters = dict(status='pending', search='轴承 & M8', warehouse_id=2,
                   contract_no='合同一', embedded='1', sort='date', order='desc')
    if page != 'stock_query':
        filters['per_page'] = old_size
    html = str(env.get_template('_list_macros.html').module.pager(
        pagination, page + '_list', base_kwargs=filters))
    select = re.search(r'<select\b[\s\S]*?</select>', html).group()
    base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    marker = base.index('// BUG-F02-07')
    start = base.index("document.addEventListener('DOMContentLoaded'", marker)
    listener = base[start:base.index('</script>', start)]
    payload = json.dumps(dict(select=select, listener=listener, page=page), ensure_ascii=False)
    script = r'''
const assert = require('node:assert/strict'), vm = require('node:vm');
const p = JSON.parse(process.argv[1]);
let onReady, onChange;
const classes = p.select.match(/class="([^"]+)"/)[1].split(/\s+/);
const decode = s => s.replace(/&#39;/g,"'").replace(/&quot;/g,'"').replace(/&amp;/g,'&');
const el = {value:'50', dataset:{baseKwargs:decode(p.select.match(/data-base-kwargs='([^']+)'/)[1])},
  addEventListener:(event,fn)=>{if(event==='change') onChange=fn;}};
const location = {href:'https://example.test/'+p.page+'?page=3&per_page=20&custom=keep', origin:'https://example.test'};
vm.runInNewContext(p.listener, {URL, window:{location}, document:{
  addEventListener:(event,fn)=>{onReady=fn;},
  querySelectorAll:selector=>selector==='.per-page-select' && classes.includes('per-page-select') ? [el] : []
}});
onReady(); assert.equal(typeof onChange,'function','pager must bind a change listener');
onChange.call(el);
const url = new URL(location.href);
assert.equal(url.searchParams.get('per_page'),'50');
assert.equal(url.searchParams.get('page'),'1');
assert.equal(url.pathname,'/'+p.page);
assert.equal(url.searchParams.get('search'),'轴承 & M8');
assert.equal(url.searchParams.get('warehouse_id'),'2');
assert.equal(url.searchParams.get('contract_no'),'合同一');
assert.equal(url.searchParams.get('embedded'),'1');
assert.equal(url.searchParams.get('sort'),'date');
assert.equal(url.searchParams.get('order'),'desc');
assert.equal(url.searchParams.get('custom'),'keep');
'''
    result = subprocess.run([node, '-e', script, payload], capture_output=True,
                            text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
