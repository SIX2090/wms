"""Execute the real action-bar renderer with visible page-toolbar aliases."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _render_toolbar(own):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for toolbar runtime checks')
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(data.source, 'utf8');
function extract(name, optional = false) {
    const start = source.indexOf('function ' + name + '(');
    if (start < 0) { if (optional) return ''; throw Error('Missing ' + name); }
    let depth = 0;
    for (let i = source.indexOf('{', start); i < source.length; i++) {
        if (source[i] === '{') depth++;
        if (source[i] === '}' && --depth === 0) return source.slice(start, i + 1);
    }
    throw Error('Unbalanced function ' + name);
}
function element(text = '', visible = true, inTable = false) {
    return {innerText: text, textContent: text, title: '', children: [],
        offsetParent: visible ? {} : null, classList: {add() {}, contains() {return false;}},
        getAttribute(k) { return k === 'title' ? this.title : null; },
        closest() {return inTable ? {} : null;}, contains(e) {return this === e || this.children.includes(e);},
        appendChild(e) {this.children.push(e);}, addEventListener() {}};
}
const own = data.own.map(o => element(o.text, o.visible !== false, !!o.inTable));
let rendered;
const content = {firstChild: null, insertBefore(bar) {rendered = bar;}};
const document = {body: element(), getElementById() {return null;},
    querySelector() {return content;}, querySelectorAll() {return own;}, createElement() {return element();}};
const window = {location: {pathname: '/purchase_order'}};
function isWmsEmbeddedPage() {return true;}
function getWmsActionModule() {return {listUrl:'/purchase_order',deleteUrl:'/purchase_order/batch_delete'};}
function isWmsListPage() {return true;}
function isFormPage() {return false;}
function createDocumentNavigationGroup() {return null;}
function saveCurrentPage() {}
const code = ['pageHasOwnButton','trimWmsActionbarDividers','pageHasOwnListAction','insertGlobalActionBar']
    .map(n=>extract(n,n==='pageHasOwnListAction')).join('\n');
eval(code);
insertGlobalActionBar();
console.log(JSON.stringify(rendered.children.filter(c=>c.title).map(c=>c.title)));
'''
    result = subprocess.run([node, '-e', script], input=json.dumps({
        'source': str(ROOT / 'app/static/js/app.js'), 'own': own}),
        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('add_label', [
    '新增采购申请', '新增采购单', '新增销售单', '新增调拨单', '新增盘点单',
    '新增委外加工单', '新增供应商', '新增客户', '新增分类', '新增单位',
    '新增仓库', '新增部门', '新增员工', '新增单据', '新增领料单',
    '新增售后出库单', '新增其他出库', '新增采购退货出库',
    '新增工单领料单', '新增BOM清单', '新增合同',
])
def test_page_toolbar_aliases_keep_one_action(add_label):
    labels = [add_label, '删除已选', '字段设置', '批量导入', '导出', '下载模板']
    assert _render_toolbar([{'text': t} for t in labels]) == ['打印', '智能分享']


def test_missing_hidden_and_row_actions_do_not_remove_global_actions():
    expected = _render_toolbar([])
    assert '新增' in expected and '删除' in expected and '导入' in expected
    assert _render_toolbar([{'text':'新增采购单','visible':False},
                            {'text':'删除已选','inTable':True}]) == expected


def test_delete_all_and_batch_print_are_distinct_actions():
    result = _render_toolbar([{'text':'删除全部'}, {'text':'批量打印'}])
    assert '删除' in result and '打印' in result


def test_sales_selection_has_one_contextual_toolbar():
    source = (ROOT / 'app/templates/sales_outbound_selection.html').read_text(encoding='utf-8')
    assert '{% block body_class %}wms-no-global-actionbar{% endblock %}' in source
    assert source.count('onclick="createSelectedOutbound()"') == 1
