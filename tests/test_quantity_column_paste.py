"""Exercise the actual desktop quantity-column paste handler and page bindings."""
from pathlib import Path
import subprocess

from jinja2 import Template
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_quantity_column_runtime():
    subprocess.run(['node', str(ROOT / 'tests/frontend_quantity_column_paste.cjs')], check=True, timeout=30)


@pytest.mark.parametrize('page,context,expected', [
    ('in_order_add', {'business_type': '采购入库'}, True),
    ('in_order_add', {'business_type': '产品入库'}, False),
    ('out_order_add', {}, True),
    ('out_order_add', {'is_other_out': True}, False),
    ('out_order_add', {'is_sale_order': True}, False),
    ('out_order_add', {'is_purchase_return': True}, False),
    ('document_table_form', {'doc_type': 'check', 'can_save': True}, True),
    ('document_table_form', {'doc_type': 'requisition', 'can_save': True}, True),
    ('document_table_form', {'doc_type': 'check', 'readonly': True}, False),
    ('document_table_form', {'doc_type': 'transfer', 'can_save': True}, False),
])
def test_paste_script_matches_editable_document(page, context, expected):
    source = (ROOT / 'app/templates' / (page + '.html')).read_text(encoding='utf8')
    includes = source.split('{% block extra_js %}', 1)[1]
    includes = includes.split('<script type="application/json"', 1)[0].split('<script>', 1)[0]
    scripts = Template(includes).render(config={}, url_for=lambda _, filename: filename, **context)
    assert ('js/quantity-column-paste.js' in scripts) is expected
