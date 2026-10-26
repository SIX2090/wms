"""Run the real month controls and quantity card handlers."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['months', 'restore', 'cards'])
def test_warehouse_monthly_frontend_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for report runtime tests')
    result = subprocess.run([node, str(ROOT/'tests/frontend_warehouse_monthly.cjs'), str(ROOT), scenario],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
