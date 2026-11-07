"""05-B list migration: rendered policy, labels and actual event dispatch."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import runpy

import app as w
import pytest

ROOT = Path(__file__).resolve().parents[1]
ROUTES = ['/in_order', '/other_in_order', '/out_order', '/other_out_order', '/after_sale_out']


def test_batch_limit_verifier_reads_actual_split_routes_and_linked_assets(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'scripts'))
    module = runpy.run_path(str(ROOT / 'scripts/verify_batch_limit.py'), run_name='import_only')
    module['check_backend_batch_limit']()
    module['check_frontend_batch_limit']()
    assert module['FAILURES'] == []


class Nodes(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.nodes = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.nodes.append((tag, dict(attrs)))


@pytest.fixture
def list_client(monkeypatch):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'SESSION_COOKIE_SECURE', False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove(); w.db.drop_all(); w.db.create_all()
        admin = w.User(username='phase05-list-only', password_hash='unused', role='admin', must_change_password=False)
        warehouse = w.Warehouse(code='P5-LIST', name='列表合成仓', is_default=True)
        w.db.session.add_all([admin, warehouse]); w.db.session.commit()
        identity, warehouse_id = admin.id, warehouse.id
    client = w.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(identity); session['_fresh'] = True
    yield client, warehouse_id
    with w.app.app_context():
        w.db.session.remove(); w.db.drop_all()


@pytest.mark.parametrize('path', ROUTES)
@pytest.mark.parametrize('embedded', [False, True])
def test_list_aliases_use_strict_policy_without_inline_handlers(list_client, path, embedded):
    client, warehouse = list_client
    response = client.get(path, query_string=dict(warehouse_id=warehouse, embedded='1' if embedded else '0'))
    assert response.status_code == 200
    assert any("script-src-attr 'none'" in value for value in response.headers.getlist('Content-Security-Policy'))
    nodes = Nodes(response.get_data(as_text=True)).nodes
    assert not [(tag, key) for tag, attrs in nodes for key in attrs if key.startswith('on')]
    scripts = [attrs.get('src', '') for tag, attrs in nodes if tag == 'script']
    assert any('/js/pages/document-list-actions.js' in src for src in scripts)


@pytest.mark.parametrize('path', ['/in_order', '/out_order', '/after_sale_out'])
def test_list_filter_controls_have_real_labels(list_client, path):
    client, warehouse = list_client
    response = client.get(path, query_string=dict(warehouse_id=warehouse))
    assert response.status_code == 200
    nodes = Nodes(response.get_data(as_text=True)).nodes
    labels = {attrs.get('for') for tag, attrs in nodes if tag == 'label' and attrs.get('for')}
    names = {'warehouse_id', 'status', 'supplier_name', 'date_start', 'date_end', 'search', 'contract_no', 'project_name'}
    controls = [attrs for tag, attrs in nodes if tag in {'input', 'select'}
                and attrs.get('type') != 'hidden'
                and (attrs.get('name') in names or attrs.get('type') in {'checkbox', 'file'})]
    assert len(controls) >= 6
    assert not [attrs for attrs in controls if not attrs.get('aria-label') and attrs.get('id') not in labels]


@pytest.mark.parametrize('path,prefix', [('/in_order', 'inOrder'), ('/out_order', 'outOrder')])
def test_sort_configuration_is_inert_json(list_client, path, prefix):
    client, warehouse = list_client
    html = client.get(path, query_string=dict(warehouse_id=warehouse)).get_data(as_text=True)
    block = re.search(r'<script id="' + prefix + r'ListConfig" type="application/json">(.*?)</script>', html, re.S)
    assert block
    data = json.loads(block[1])
    assert set(data) == {'sortBy', 'sortOrder'}
    assert all(isinstance(value, str) and value for value in data.values())


def test_fixed_click_change_and_visible_date_bindings_execute():
    node = shutil.which('node')
    assert node, 'Node required for actual event dispatch'
    script = (ROOT / 'app/static/js/pages/document-list-actions.js').read_text(encoding='utf-8')
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const events={},calls=[];let prevented=0;
const visible={setAttribute(k,v){this[k]=v;}},label={textContent:'开始日期',htmlFor:'dateField'};
const hiddenDate={id:'dateField',type:'hidden',_flatpickr:{altInput:visible}};
const ctx={document:{addEventListener(n,f){events[n]=f;},getElementById(id){return {click(){calls.push(['file',id]);}};},
querySelectorAll(selector){return selector==='input[id]'?[hiddenDate]:[];},querySelector(selector){return selector==='label[for="dateField"]'?label:null;}}};
for(const name of ['batchInOrderAction','batchOutOrderAction','singleOutOrderAction','copyInOrder','completeOrder','deleteOrder','revertOrder','printAfterSaleOutList','changePerPage','submitDocumentImport','toggleAll'])ctx[name]=(...args)=>calls.push([name,...args]);
let businessLabel='领料单';ctx.outOrderBusinessLabel=()=>businessLabel;
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.script,ctx);
const expected=[
['in-order-batch-complete','batchInOrderAction','/in_order/batch_complete'],
['in-order-batch-print','batchInOrderAction','/in_order/batch_print'],
['in-order-batch-export','batchInOrderAction','/in_order/batch_export'],
['in-order-batch-delete','batchInOrderAction','/in_order/batch_delete'],
['in-order-choose-import','file','inOrderImportFile'],['in-order-copyInOrder','copyInOrder','7'],
['out-order-batch-delete','batchOutOrderAction','/out_order/batch_delete'],
['out-order-batch-complete','batchOutOrderAction','/out_order/batch_complete'],
['out-order-choose-import','file','outOrderImportFile'],
['out-order-complete','singleOutOrderAction','/out_order/7/complete'],
['out-order-delete','singleOutOrderAction','/out_order/7/delete'],
['out-order-revert','singleOutOrderAction','/out_order/7/revert'],
['after-sale-out-choose-import','file','afterSaleOutImportFile'],
['after-sale-out-print','printAfterSaleOutList'],
['after-sale-out-completeOrder','completeOrder','7'],
['after-sale-out-deleteOrder','deleteOrder','7'],
['after-sale-out-revertOrder','revertOrder','7']];
function click(action,id='7',disabled=false){const button={disabled,getAttribute(k){return k==='data-document-list-action'?action:id;}};events.click({target:{closest(){return button;}},preventDefault(){prevented++;}});}
for(const [action,...args] of expected){click(action);assert.deepEqual(calls.at(-1).slice(0,args.length),args,action);}
assert.equal(calls.length,17);assert.equal(prevented,17);
for(const [action] of expected.filter(e=>['copyInOrder','singleOutOrderAction','completeOrder','deleteOrder','revertOrder'].includes(e[1])))click(action,'7/complete');
click('unreviewed-action');click('in-order-batch-delete','7',true);assert.equal(calls.length,17);
events.change({target:{value:'50',getAttribute(){return 'page-size';}}});assert.deepEqual(calls.at(-1),['changePerPage','50']);
events.change({target:{id:'inOrderImportFile',form:{id:'inOrderImportForm'},getAttribute(){return 'import';}}});assert.deepEqual(calls.at(-1),['submitDocumentImport','inOrderImportForm','inOrderImportFile']);
events.change({target:{checked:true,getAttribute(){return 'select-all';}},preventDefault(){throw Error('checkbox default must be preserved');}});assert.deepEqual(calls.at(-1),['toggleAll']);
for(const label of ['领料单','销售出库单','其他出库单','采购退货出库单']){
businessLabel=label;
click('out-order-batch-delete');assert.deepEqual(calls.at(-1),['batchOutOrderAction','/out_order/batch_delete','请选择要删除的'+label,'确认删除选中的'+label+'？']);
click('out-order-batch-complete');assert.deepEqual(calls.at(-1),['batchOutOrderAction','/out_order/batch_complete','请选择要完成的'+label,'确认完成选中的'+label+'？完成后会扣减库存。']);
click('out-order-complete');assert.equal(calls.at(-1)[2],'确认完成该'+label+'？完成后会扣减库存。');
click('out-order-delete');assert.equal(calls.at(-1)[2],'确认删除该'+label+'？');
click('out-order-revert');assert.equal(calls.at(-1)[2],'确认反提交该'+label+'？反提交后库存将恢复。');
}
events.DOMContentLoaded();assert.equal(visible.id,'dateFieldDisplay');assert.equal(label.htmlFor,visible.id);assert.equal(visible['aria-label'],'开始日期');
'''
    result = subprocess.run([node, '-e', program], input=json.dumps(dict(script=script)),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_after_sale_list_print_keeps_selection_notice_and_unified_template_flow():
    from tests.test_frontend_remaining_page_transport import callback
    source = callback('after_sale_out', 'function printAfterSaleOutList(')
    program = r"""
const vm=require('node:vm'),assert=require('node:assert/strict'),source=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
let ids=[],opened=[],messages=[];
const ctx={document:{addEventListener(){},querySelectorAll(selector){assert.equal(selector,'.order-check:checked');return ids.map(value=>({value}));}},
showToast:(...args)=>messages.push(args),window:{open:(...args)=>opened.push(args)}};
vm.createContext(ctx);vm.runInContext(source,ctx);
ctx.printAfterSaleOutList();assert.equal(opened.length,0);assert.equal(messages.at(-1)[1],'warning');
ids=['7'];ctx.printAfterSaleOutList();assert.deepEqual(opened.at(-1),['/after_sale_out/7/print_options','_blank']);
ids=['8','9'];ctx.printAfterSaleOutList();assert.deepEqual(opened.at(-1),['/after_sale_out/8/print_options','_blank']);assert.equal(opened.length,2);
assert.equal(messages.at(-1)[0],'当前仅支持逐单打印，已打开第一张');assert.equal(messages.at(-1)[1],'info');
"""
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(source),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
