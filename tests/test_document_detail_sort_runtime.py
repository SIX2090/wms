"""Whole-row sorting must retain document line identities and edit controls."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['natural', 'numbers', 'keyboard', 'reordered', 'unkeyed',
    'live-input', 'blank-last', 'stable', 'summary', 'dynamic', 'resize', 'identity', 'idempotent', 'decimals'])
def test_setupDetailRowSorting_runtime(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    result = subprocess.run([node, '--max-old-space-size=64', str(ROOT/'tests/frontend_document_detail_sort.cjs'),
        str(ROOT), scenario], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
