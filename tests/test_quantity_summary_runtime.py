"""BUG-2026-10-29-020: quantity totals must be visible before saving."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['in_order_add', 'out_order_add', 'after_sale_out_add',
         'purchase_order_add', 'purchase_request_add', 'sales_order_add',
         'sales_order_edit', 'opening_stock', 'subcontract_issue',
         'subcontract_receive', 'subcontract_detail', 'in_order_detail', 'out_order_detail']


class SummaryParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.summaries = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-quantity-summary' in attrs:
            self.summaries.append(attrs)


@pytest.mark.parametrize('page', PAGES)
def test_actual_entry_summary_updates_without_save(page):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    source = (ROOT / f'app/templates/{page}.html').read_text(encoding='utf-8')
    summaries = SummaryParser(source).summaries
    assert len(summaries) == 1, 'Entry page needs its own quantity summary'
    summary = summaries[0]
    table = summary['data-quantity-summary']
    assert f'id="{table}"' in source
    assert 'data-quantity-value aria-live="polite"' in source
    if page in ['in_order_detail', 'out_order_detail']:
        assert '{% if order.items %}\n                <tfoot>' not in source
    else:
        assert source.index('data-quantity-summary') > source.index('</table>', source.index(f'id="{table}"'))
    base = (ROOT / 'app/templates/base.html').read_text(encoding='utf-8')
    assert base.index("filename='js/quantity-summary.js'") < base.index('{% block extra_js %}')
    # Import/restore/bulk edit assign .value directly. Their established calculation
    # entry point must refresh quantities even when no DOM input event fires.
    funcs = {'purchase_request_add': 'updateTotals', 'sales_order_add': 'recalc',
             'sales_order_edit': 'recalc', 'subcontract_detail': 'calcInlineProductAmount',
             'opening_stock': 'updateTotal', 'in_order_detail': 'calcInlineRowAmount',
             'out_order_detail': 'calcInlineRowAmount'}
    if page not in ['subcontract_issue', 'subcontract_receive']:
        runtime = source
        if page == 'opening_stock':
            runtime = (ROOT / 'app/static/js/pages/opening-stock.js').read_text(encoding='utf-8')
        name = funcs.get(page, 'calcTotal')
        body = re.search(r'function ' + name + r'\([^)]*\)\s*\{([\s\S]*?)\n\s*\}', runtime).group(1)
        assert f"refreshQuantityTotals('{table}')" in body
    result = subprocess.run([node, str(ROOT / 'tests/frontend_quantity_summary.cjs')],
                            input=json.dumps(summary), text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
