"""Actual shell/report scripts must preserve tabs and clear stale failed-query totals."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which('node')


@pytest.mark.skipif(NODE is None, reason='Node.js required for actual page scripts')
@pytest.mark.parametrize('count', [1, 8, 9, 15])
def test_restore_all_supported_tabs(count):
    result = subprocess.run([NODE, str(ROOT / 'tests/frontend_tabs_restore_capacity.cjs'), str(count)],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.skipif(NODE is None, reason='Node.js required for actual page scripts')
@pytest.mark.parametrize('failure', ['network', 'http', 'business', 'json'])
def test_report_failed_query_clears_previous_warehouse_summary(failure):
    result = subprocess.run([NODE, str(ROOT / 'tests/frontend_report_error_summary.cjs'), failure],
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
