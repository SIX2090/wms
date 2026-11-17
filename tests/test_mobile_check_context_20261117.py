"""Execute real stocktake context callbacks, including delayed old responses."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('scenario', ['warehouse', 'clear', 'selection', 'retry_empty', 'success', 'empty_success', 'escape'])
def test_mobile_check_context_20261117(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for real callback execution')
    script = Path(__file__).with_name('frontend_mobile_check_context_20261117.cjs')
    result = subprocess.run([node, str(script), scenario], capture_output=True,
                            text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
