"""A closed or cancelled browser print dialog is not proof of paper output."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['closed', 'timeout', 'cancel', 'confirmed', 'two-copies', 'report-retry'])
def test_print_station_requires_output_confirmation(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run([node, '--max-old-space-size=96',
                             str(ROOT / 'tests/frontend_print_station_confirmation_runtime.cjs'),
                             str(ROOT), scenario], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
