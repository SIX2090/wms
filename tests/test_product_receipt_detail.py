"""BUG-2026-11-06-002: finished-goods detail layout, fields and view sorting."""
from datetime import date, datetime
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace as NS

from jinja2 import Environment
import pytest

from tests.test_detail_row_column_context_runtime import TableParser

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'app/templates/in_order_detail.html'
SOURCE_KEYS = {'colSourcePo', 'colSourceQty', 'colSourcePushed', 'colSourceCompleted', 'colSourceStatus'}


def order_case(business='产品入库', status='completed', empty=False):
    material = NS(code='400001', name='配电柜', spec='800*675*2345', brand='', unit=NS(name='台'))
    items = [NS(id=i, material_id=1, material=material, box_no=box, quantity=qty,
                price=10, amount=qty*10, remark='箱体'+box, contract_no='', project_name='',
                batch_no='', expiry_date=None, source_purchase_order_item=None,
                is_customer_supplied=False)
             for i, (box, qty) in enumerate([('PA03-LP10', 10), ('PA03-LP2', 2), ('PA03-LP1', 1)], 1)]
    return NS(id=1, business_type=business, status=status, items=[] if empty else items,
              order_no='PI-TEST', date=date(2026, 11, 6), customer=NS(name='产品客户'),
              supplier=None, customer_id=1, supplier_id=None, purpose='生产完工入库',
              contract_no='HT-01', project_name='成品工程', warehouse='成品仓', location='',
              source_purchase_order=None, operator=NS(username='fixture'), remark='',
              created_at=datetime(2026, 11, 6, 12))


def render_table(order):
    source = TEMPLATE.read_text(encoding='utf-8')
    start = source.rindex('<table', 0, source.index('id="itemTable"'))
    end = source.index('</table>', start) + len('</table>')
    return TableParser(Environment(autoescape=True).from_string(source[start:end]).render(
        order=order, warehouse_stock={1: 13}, purchase_order_execution={},
        url_for=lambda *args, **kwargs: '/fixture'))


@pytest.mark.parametrize('business', ['产品入库', '采购入库', '其他入库', '销售退货入库'])
@pytest.mark.parametrize('status', ['pending', 'completed'])
def test_rendered_columns_preserve_business_meaning_and_summary_alignment(business, status):
    table = render_table(order_case(business, status))
    keys = [cell['attrs']['data-column-key'] for cell in table.headers]
    assert len(keys) == len(set(keys))
    rows = [row for row in table.rows if row['attrs'].get('data-id')]
    assert len(rows) == 3
    for row in rows:
        assert [cell['attrs']['data-column-key'] for cell in row['cells']] == keys
    if business == '产品入库':
        assert keys[1 if status == 'completed' else 2] == 'colBoxNo'
        assert not SOURCE_KEYS.intersection(keys), 'finished goods do not use purchase-execution columns'
        assert [next(cell['text'].strip() for cell in row['cells'] if cell['attrs']['data-column-key'] == 'colBoxNo') for row in rows] == ['PA03-LP10', 'PA03-LP2', 'PA03-LP1']
    else:
        assert 'colBoxNo' not in keys
        assert SOURCE_KEYS <= set(keys), 'keep existing purchasing/source traceability for other receipts'
    footer = next(row for row in table.rows if row['attrs'].get('class') == 'total-row')
    assert [cell['attrs'].get('data-column-key') for cell in footer['cells']] == keys
    assert next(cell['text'].strip() for cell in footer['cells'] if cell['attrs'].get('data-column-key') == 'colQty') == '13.00'


@pytest.mark.parametrize('business', ['产品入库', '采购入库', '其他入库', '销售退货入库'])
@pytest.mark.parametrize('status', ['pending', 'completed'])
def test_empty_detail_covers_the_actual_columns(business, status):
    table = render_table(order_case(business, status, empty=True))
    empty = next(cell for row in table.rows for cell in row['cells'] if cell['attrs'].get('class') == 'empty-state')
    assert int(empty['attrs']['colspan']) == len(table.headers)


@pytest.mark.parametrize('business', ['产品入库', '采购入库'])
def test_finished_goods_header_does_not_claim_a_purchase_source(business):
    source = TEMPLATE.read_text(encoding='utf-8')
    section = source[source.index('<!-- 单据信息 -->'):source.index('<!-- 工具栏 -->')]
    html = Environment(autoescape=True).from_string(section).render(order=order_case(business), url_for=lambda *a, **kw: '/fixture')
    if business == '产品入库':
        assert '客户名称' in html and '成品工程' in html and '生产完工入库' in html
        assert '来源采购单' not in html and '供应商' not in html
    else:
        assert '来源采购单' in html and '供应商' in html and '单据联查' in html


@pytest.mark.parametrize('page,target', [('in_order_detail', 'itemTable'), ('in_order_add', 'materialTable'), ('report_view', 'reportTable')])
def test_field_dialog_targets_the_business_table_not_the_first_table(page, target):
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    button = re.search(r'<button\b[^>]*id="columnSettingsBtn"[^>]*>', source).group()
    assert f'data-field-settings-table="{target}"' in button


def test_product_column_preferences_do_not_reuse_purchase_layout():
    source = TEMPLATE.read_text(encoding='utf-8')
    setup = re.search(r'window\.setupDynamicDetailColumnControls\(\{[\s\S]*?\n        \}\);', source).group()
    env = Environment()
    product = env.from_string(setup).render(order=order_case())
    purchase = env.from_string(setup).render(order=order_case('采购入库'))
    assert "orderKey: 'product_in_order_detail_col_order_v1'" in product
    assert "widthKey: 'product_in_order_detail_col_widths_v1'" in product
    assert "orderKey: 'in_order_detail_col_order_v1'" in purchase


@pytest.mark.parametrize('scenario', ['boxes', 'quantities', 'reordered-columns', 'live-input', 'keyboard', 'resize', 'stable-and-new-row', 'other-receipt'])
def test_real_detail_sort_preserves_whole_rows_and_numeric_values(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run([node, '--max-old-space-size=64', str(ROOT/'tests/frontend_product_receipt_detail.cjs'), str(ROOT), scenario],
                            capture_output=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
