"""BUG-2026-10-25-009: run real column dialogs, controllers and report rendering."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = [
    'plain-reset-button', 'plain-reset-escape', 'plain-reset-backdrop',
    'plain-reset-ok', 'plain-move-ok', 'plain-edit-cancel', 'new-column-observer',
]
for startup in ['common-first', 'dynamic-first']:
    for preference in ['own', 'shared', 'malformed']:
        for action in ['reset-cancel', 'reset-ok', 'native-reset', 'drag-name-ok', 'move-ok']:
            SCENARIOS.append(f'dynamic-{startup}-{preference}-{action}-case')
    for result in ['rows', 'empty', 'new-column']:
        SCENARIOS.append(f'report-{startup}-{result}-case')


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_field_settings_reset_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run(
        [node, '--max-old-space-size=96', str(ROOT / 'tests/frontend_field_settings_runtime.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
