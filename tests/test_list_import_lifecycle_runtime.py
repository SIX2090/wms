"""Real local list import handlers and API, synthetic files and controlled fetch only."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = 'in_order out_order after_sale_out transfer check adjustment subcontract subcontract_issue subcontract_receive purchase_order purchase_request'.split()
SCENARIOS = [
    'success', 'stale-selection', 'failure-new-selection', 'empty', 'cancel-selection',
    'missing-input', 'failure-business', 'failure-http', 'failure-html', 'failure-null',
    'failure-network', 'failure-401', 'failure-419', 'formdata-error', 'fetch-error',
    'original-disabled', 'button-original-disabled',
]


@pytest.mark.parametrize('page', PAGES)
@pytest.mark.parametrize('scenario', SCENARIOS)
def test_list_import_lifecycle_preserves_file_and_single_dispatch(page, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for real template import runtime')
    template_dir = ROOT / 'app/templates'
    payload = {
        'page': page,
        'scenario': scenario,
        'html': (template_dir / f'{page}.html').read_text(encoding='utf-8'),
        'api': (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'),
    }
    result = subprocess.run(
        [node, str(Path(__file__).with_name('list_import_lifecycle_runtime.cjs'))],
        input=json.dumps(payload), encoding='utf-8', capture_output=True, timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
