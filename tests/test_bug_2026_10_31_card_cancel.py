"""Execute shared fetch observation and card rendering against real source."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', [
    'abort', 'network', 'server', 'session', 'reject-identity', 'unhandled-abort', 'unhandled-network',
    'select', 'source-select', 'select-all', 'disabled-select',
    'image', 'image-click', 'find-image', 'actions', 'all-actions',
    'status-once', 'reinit', 'text', 'unique-ids', 'disabled-action',
    'desktop', 'entry-grid',
])
def test_shared_card_and_cancel_runtime(scenario):
    result = subprocess.run(
        [shutil.which('node'), str(ROOT / 'tests/frontend_card_cancel.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
