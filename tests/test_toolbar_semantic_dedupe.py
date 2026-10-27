"""Execute the real action-bar renderer with visible page-toolbar aliases."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _render_toolbar(own, **context):
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
    return {innerText: text, textContent: text, title: '', children: [], attrs: {},
        offsetParent: visible ? {} : null, classList: {add() {}, contains() {return false;}},
        setAttribute(k, v) {this.attrs[k] = String(v);},
        getAttribute(k) { return k === 'title' ? this.title : this.attrs[k] ?? null; },
        closest() {return inTable ? {} : null;}, contains(e) {return this === e || this.children.includes(e);},
        appendChild(e) {this.children.push(e);}, addEventListener() {}};
}
const own = data.own.map(o => element(o.text, o.visible !== false, !!o.inTable));
let rendered;
const content = {firstChild: null, insertBefore(bar) {rendered = bar;}};
const document = {body: element(), getElementById() {return null;},
    querySelector(s) {return s === '.embedded-content' ? content : null;}, querySelectorAll() {return own;}, createElement() {return element();}};
const window = {location: {pathname: data.path || '/purchase_order'}};
function isWmsEmbeddedPage() {return true;}
function getWmsActionModule() {return {listUrl:'/purchase_order',deleteUrl:'/purchase_order/batch_delete',printTemplateUrl:data.printTemplateUrl};}
function isWmsListPage() {return data.isList !== false;}
function isFormPage() {return !!data.isForm;}
function createDocumentNavigationGroup() {return null;}
function saveCurrentPage() {}
const code = ['escapeHtml','pageHasOwnButton','trimWmsActionbarDividers','pageHasOwnListAction','insertGlobalActionBar']
    .map(n=>extract(n,n==='pageHasOwnListAction')).join('\n');
eval(code);
insertGlobalActionBar();
console.log(JSON.stringify(rendered.children.filter(c=>c.title).map(c=>c.title)));
'''
    result = subprocess.run([node, '-e', script], input=json.dumps({
        'source': str(ROOT / 'app/static/js/app.js'), 'own': own, **context}),
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
    assert _render_toolbar([{'text': t} for t in labels]) == ['智能分享']


def test_missing_hidden_and_row_actions_do_not_remove_global_actions():
    expected = _render_toolbar([])
    assert '新增' in expected and '删除' in expected and '导入' in expected
    assert _render_toolbar([{'text':'新增采购单','visible':False},
                            {'text':'删除已选','inTable':True}]) == expected


def test_delete_all_and_batch_print_are_distinct_actions():
    result = _render_toolbar([{'text':'删除全部'}, {'text':'批量打印'}])
    assert '删除' in result and '打印' not in result


def test_sales_selection_has_one_contextual_toolbar():
    source = (ROOT / 'app/templates/sales_outbound_selection.html').read_text(encoding='utf-8')
    assert '{% block body_class %}wms-no-global-actionbar{% endblock %}' in source
    assert source.count('onclick="createSelectedOutbound()"') == 1


def test_read_only_detail_keeps_navigation_context_without_fake_save_or_duplicate_add():
    labels = _render_toolbar([{'text': '再建一张'}], path='/in_order/579',
                             isList=False, printTemplateUrl='/in_order_print_template')
    assert '保存' not in labels and '新增' not in labels
    assert '打印设置' in labels


def test_new_document_keeps_save_and_labels_print_settings_but_has_no_record_delete():
    labels = _render_toolbar([{'text': '字段设置'}], path='/in_order/add',
                             isList=False, isForm=True,
                             printTemplateUrl='/in_order_print_template')
    assert '保存' in labels and '新增' in labels
    assert '删除' not in labels and '打印设置' in labels


def test_editable_form_uses_own_save_and_column_settings_without_losing_other_actions():
    labels = _render_toolbar([{'text': '保存草稿'}, {'text': '字段设置'}],
                             path='/sales/12/edit', isList=False, isForm=True)
    assert '保存' not in labels and '设置' not in labels
    assert '新增' in labels and '导出' in labels
