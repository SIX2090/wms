"""Empty grid hints must not conceal values or change form payloads."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['empty', 'filled', 'events', 'invalid', 'outside',
                                     'dynamic', 'idempotent', 'consumer'])
def test_refreshWmsEntryCellHints_runtime(scenario):
    node = shutil.which('node')
    assert node, 'Node.js required for grid interaction regression'
    result = subprocess.run([node, '--max-old-space-size=64',
        str(ROOT/'tests/frontend_empty_entry_cell_hints.cjs'), str(ROOT), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_empty_hint_styles_preserve_focus_and_scope():
    css = (ROOT/'app/static/css/custom.css').read_text(encoding='utf-8')
    assert '.wms-entry-grid tbody td input:not(:focus)::placeholder' in css
    assert '.wms-entry-grid tbody td textarea:not(:focus)::placeholder' in css
    assert '.wms-entry-grid tbody td input[type="date"].wms-entry-cell-empty:not(:focus)' in css
    assert '.wms-entry-grid tbody td select.wms-entry-cell-empty:not(:focus)' in css
    start = css.index('.wms-entry-grid tbody td input[type="date"].wms-entry-cell-empty:not(:focus)')
    rule = css[start:css.index('}',start)]
    assert 'opacity: 0 !important' in rule
    assert 'pointer-events' not in rule and 'display: none' not in rule and 'visibility: hidden' not in rule
