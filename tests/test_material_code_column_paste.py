"""Excel 单列编码直接粘贴到领料明细，执行实际产品脚本。"""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', [
    'column', 'header', 'single', 'leading_zero', 'duplicates', 'append',
    'occupied', 'unknown', 'inactive', 'network', 'later_batch_failure',
    'many_codes', 'multiple_columns', 'missing_warehouse', 'refreshing',
    'switch_warehouse', 'switch_back', 'edit_during_lookup', 'removed',
    'locked_during_lookup', 'repeat', 'readonly',
])
def test_material_code_column_paste(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run(
        [node, str(ROOT / 'tests/frontend_material_code_column_paste.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf8', timeout=25)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('template,body,guard', [
    ('out_order_add.html', 'materialTableBody', '!isSaleOrder && !isPurchaseReturn'),
    ('document_table_form.html', 'docTableBody', "docType === 'requisition'"),
])
def test_material_code_paste_pages_bind_shared_handler(template, body, guard):
    source = (ROOT / 'app/templates' / template).read_text(encoding='utf8')
    assert "filename='js/material-code-paste.js'" in source
    assert 'WMS.bindMaterialCodePaste({' in source
    assert "bodyId: '" + body + "'" in source
    assert guard in source
    assert '数量留空' in source
