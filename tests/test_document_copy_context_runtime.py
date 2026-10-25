"""Copy/template round trips must preserve project context and explicit zero prices."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.mark.skipif(NODE is None, reason='Node.js is required for actual page script execution')
@pytest.mark.parametrize('scenario', [
    'purchase-copy', 'sales-add-copy', 'sales-edit-copy',
    'sales-add-template', 'sales-edit-template', 'aftersale-copy',
])
@pytest.mark.parametrize('context', ['populated', 'empty'])
def test_copy_context_round_trip(scenario, context):
    result = subprocess.run(
        [NODE, str(ROOT / 'tests/frontend_document_copy_context.cjs'), scenario, context],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
