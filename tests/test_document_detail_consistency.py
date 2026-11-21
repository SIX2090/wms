"""Shared consumers of BUG-2026-11-06-002 found during the document audit."""
from pathlib import Path
import json
import shutil
import subprocess
from types import SimpleNamespace as NS

from jinja2 import Environment
import pytest

from tests.test_detail_row_column_context_runtime import render_detail_table

ROOT = Path(__file__).resolve().parents[1]


def render(page, business, status, empty=False, push_source=None):
    material = NS(code='400001', name='成品', brand='品牌', spec='规格', unit=NS(name='台'))
    item = NS(id=1, material_id=1, material=material, quantity=2, price=5, amount=10,
              contract_no='行合同', project_name='行工程', remark='备注')
    order = NS(id=1, business_type=business, status=status, items=[] if empty else [item],
               contract_no='表头合同', project_name='表头工程', total_amount=0 if empty else 10)
    source = (ROOT / f'app/templates/{page}_detail.html').read_text(encoding='utf-8')
    env = Environment(autoescape=True)
    env.filters['quantity'] = lambda value: str(value)
    return render_detail_table(env, source, order=order, push_source=push_source,
                               warehouse_stock={1:2}, url_for=lambda *args, **kwargs: '/fixture')


@pytest.mark.parametrize('status,source,editable', [
    ('pending', None, True), ('pending', NS(source_document_no='IN-1'), False),
    ('completed', None, False), ('completed', NS(source_document_no='IN-1'), False),
])
def test_issue_detail_shows_edit_columns_only_for_editable_drafts(status, source, editable):
    table = render('out_order', '领料单', status, push_source=source)
    keys = [cell['attrs']['data-column-key'] for cell in table.headers]
    assert ('selection' in keys) == editable
    assert ('actions' in keys) == editable


@pytest.mark.parametrize('page,business', [('out_order','领料单'),('out_order','销售出库'),
    ('out_order','其他出库'),('out_order','采购退货出库'),('after_sale_out','售后出库')])
@pytest.mark.parametrize('status', ['pending','completed'])
def test_detail_footer_matches_real_columns_and_totals(page, business, status):
    table = render(page,business,status)
    headers = [cell['attrs']['data-column-key'] for cell in table.headers]
    footer = next(row for row in table.rows if 'total-row' in row['attrs'].get('class',''))
    assert [cell['attrs']['data-column-key'] for cell in footer['cells']] == headers
    assert next(cell['text'].strip() for cell in footer['cells'] if cell['attrs']['data-column-key']=='quantity') == '2.00'
    assert next(cell['text'].strip() for cell in footer['cells'] if cell['attrs']['data-column-key']=='amount') == '¥10.00'
    existing = next(row for row in table.rows if len(row['cells'])==len(headers))
    assert [cell['attrs']['data-column-key'] for cell in existing['cells']] == headers


@pytest.mark.parametrize('page,business', [('out_order','销售出库'),('after_sale_out','售后出库')])
@pytest.mark.parametrize('status', ['pending','completed'])
def test_empty_detail_spans_every_real_column(page,business,status):
    table = render(page,business,status,empty=True)
    empty = next(row for row in table.rows if any('暂无明细' in cell['text'] for cell in row['cells']))
    assert int(empty['cells'][0]['attrs']['colspan']) == len(table.headers)


@pytest.mark.parametrize('module_id,available,expected', [
    ('purchaseRequestTable',['trace','itemTable'],'itemTable'),
    ('purchaseOrderTable',['trace','itemTable'],'itemTable'),
    ('salesOrderTable',['itemTable','trace'],'itemTable'),
    ('checkTable',['trace','docTable'],'docTable'),
    ('purchaseOrderTable',['purchaseOrderTable'],'purchaseOrderTable'),
])
def test_global_column_button_targets_saved_document_grid(module_id,available,expected):
    node = shutil.which('node')
    if not node: pytest.skip('Node.js required')
    source = (ROOT/'app/static/js/app.js').read_text(encoding='utf-8')
    start = source.index('var settingsTable = module.tableId')
    end = source.index("if (settingsTable) btn.setAttribute('data-field-settings-table', settingsTable.id);",start)
    body = source[start:end]+source[end:source.index('\n',end)]
    program = '''const assert=require('node:assert/strict');
const moduleConfig=INPUT; const module=moduleConfig;
const tables=new Map(AVAILABLE.map(id=>[id,{id}]));
const document={getElementById:id=>tables.get(id)||null};
const btn={setAttribute:(key,value)=>{assert.equal(key,'data-field-settings-table');btn.target=value;}};
BODY
assert.equal(btn.target,EXPECTED);
'''.replace('INPUT',json.dumps({'tableId':module_id})).replace('AVAILABLE',json.dumps(available)).replace('EXPECTED',json.dumps(expected)).replace('BODY',body)
    result = subprocess.run([node,'-e',program],capture_output=True,text=True,encoding='utf-8')
    assert result.returncode==0,result.stdout+result.stderr
