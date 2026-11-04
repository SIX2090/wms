"""Execute actual toolbar handlers with the actual WMS API client."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


def test_material_unused_delete_runtime():
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js is required for toolbar behavior execution')
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([node, str(root/'tests/frontend_material_unused_delete.cjs'), str(root)],
                            capture_output=True, text=True, encoding='utf8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['failed'] == 0
    assert report['passed'] == 11
