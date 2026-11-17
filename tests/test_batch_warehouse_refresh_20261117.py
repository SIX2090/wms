"""Execute the real batch-warehouse branches without importing the application."""
from pathlib import Path
import shutil
import subprocess
import pytest


def test_batch_warehouse_refreshes_dependent_stock():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = Path(__file__).with_name('frontend_batch_warehouse_refresh_20261117.cjs')
    result = subprocess.run([node, str(script)], capture_output=True, text=True,
                            encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
