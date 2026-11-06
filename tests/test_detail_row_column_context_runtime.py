"""Render real detail tables and run their row actions without an app or database."""
import json
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace

from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]


class TableParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.headers, self.rows = [], []
        self.row = self.cell = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.row = {'attrs': attrs, 'cells': []}
            self.rows.append(self.row)
        elif tag in ('td', 'th'):
            self.cell = {'attrs': attrs, 'text': ''}
            if tag == 'th':
                self.headers.append(self.cell)
            elif self.row:
                self.row['cells'].append(self.cell)

    def handle_data(self, text):
        if self.cell:
            self.cell['text'] += text

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            self.cell = None


def function(source, name):
    start = source.index('function ' + name + '(')
    return source[start:source.index('\n}', start) + 2]


@pytest.mark.parametrize('page,business,customer', [
    ('in', '采购入库', False), ('in', '产品入库', False),
    ('in', '其他入库', False), ('in', '其他入库', True),
    ('out', '领料出库', False), ('out', '销售出库', False),
    ('out', '其他出库', False), ('out', '采购退货出库', False),
])
@pytest.mark.parametrize('layout', ['default', 'saved-order', 'hidden-reordered'])
def test_detail_row_actions_keep_column_and_payload_meaning(page, business, customer, layout):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / f'app/templates/{page}_order_detail.html').read_text(encoding='utf-8')
    material = SimpleNamespace(code='M-01', brand='品牌', name='轴承', spec='6204', unit=SimpleNamespace(name='套'), stock=999)
    po = SimpleNamespace(id=8, order_no='PO-08')
    item = SimpleNamespace(id=9, material_id=11, material=material, quantity=2, price=0, amount=0,
                           remark='说明 & 中', contract_no='HT-01', project_name='工程一',
                           batch_no='B-01', expiry_date=date(2027, 1, 2),
                           is_customer_supplied=customer,
                           source_purchase_order_item=SimpleNamespace(id=10, purchase_order=po, quantity=7))
    order = SimpleNamespace(id=7, status='pending', business_type=business, items=[item], contract_no='HEAD', project_name='表头工程')
    env = Environment(autoescape=True)
    context = dict(order=order, warehouse_stock={11: 99}, purchase_order_execution={}, url_for=lambda *a, **kw: '/fixture')
    table_start = source.rindex('<table', 0, source.index('id="itemTable"'))
    table_end = source.index('</table>', table_start) + len('</table>')
    table = TableParser(env.from_string(source[table_start:table_end]).render(**context))
    functions = '\n'.join(function(source, name) for name in [
        'addInlineMaterialRow', 'copyDetailMaterialRow', 'calcInlineRowAmount',
        'renumberDetailRows', 'saveInlineMaterialRow',
    ])
    if page == 'out':
        functions += '\n' + function(source, 'bindInlineMaterialRow')
    registration = re.search(r'registerDetailRowActions\(\{[\s\S]*?\n    \}\);', source).group()
    scripts = env.from_string(functions + '\n' + registration).render(**context)
    original = next(row for row in table.rows if row['attrs'].get('data-id') == '9')
    payload = dict(page=page, business=business, customer=customer, layout=layout,
                   headers=table.headers, original=original, scripts=scripts)
    result = subprocess.run([node, '--max-old-space-size=64', str(ROOT / 'tests/frontend_detail_row_column_context.cjs')],
                            input=json.dumps(payload), cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
