"""Execute the real material summary helper and report handlers in Node."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['units', 'error', 'print', 'switch', 'ledger_change', 'date_scope'])
def test_material_movement_frontend_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for browser handler regression')
    result = subprocess.run([node, str(ROOT / 'tests/frontend_material_movement.cjs'), str(ROOT), scenario],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
