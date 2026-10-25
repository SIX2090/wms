"""Execute the actual quick-select component across dismissal and owner changes."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.mark.skipif(NODE is None, reason='Node.js is required for actual component execution')
def test_quick_select_lifecycle_runtime():
    result = subprocess.run(
        [NODE, '--max-old-space-size=64',
         str(ROOT / 'tests/frontend_quick_select_lifecycle.cjs'),
         str(ROOT / 'app/static/js/quick-select.js')],
        cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    assert report['failed'] == 0
    assert report['passed'] == 34
