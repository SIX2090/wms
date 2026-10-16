"""Exercise Enter navigation without submitting a document or changing row data."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['quantity', 'price', 'last', 'no_price', 'hidden',
    'readonly', 'disabled', 'composition', 'legacy_composition', 'ctrl', 'shift', 'alt',
    'meta', 'tab', 'handled', 'reordered', 'other_focus'])
def test_document_entry_navigation(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const assert = require('node:assert/strict');
global.window = global;
require(process.argv[1]);
const scenario = process.argv[2];
let focused = '', selected = '', added = 0;
let frame;
const doc = {body: {}, activeElement: null};
window.requestAnimationFrame = fn => {frame = fn;};
function field(name) {
    return {value: name === 'price' ? '0.00' : '6', disabled: false, readOnly: false,
        handlers: {}, getClientRects: () => [1],
        addEventListener(k, fn) {this.handlers[k] = fn;},
        ownerDocument: doc, isConnected: true,
        focus() {focused = name; doc.activeElement = this;}, select() {selected = name;}};
}
const qty = field('qty'), price = field('price'), code = field('code');
const fields = {'.qty': qty, '.price': price};
if (scenario === 'no_price') delete fields['.price'];
if (scenario === 'hidden') price.getClientRects = () => [];
if (scenario === 'readonly') qty.readOnly = true;
if (scenario === 'disabled') qty.disabled = true;
const row = {querySelector: s => fields[s] || null};
WMS.MaterialPicker.bindEntryRow(row, ['.qty', '.price'], () => {
    if (scenario === 'last') added++;
    return code;
});
const e = {key: scenario === 'tab' ? 'Tab' : 'Enter', defaultPrevented: scenario === 'handled',
    isComposing: scenario === 'composition', keyCode: scenario === 'legacy_composition' ? 229 : 13,
    ctrlKey: scenario === 'ctrl', shiftKey: scenario === 'shift', altKey: scenario === 'alt',
    metaKey: scenario === 'meta', preventDefault() {this.defaultPrevented = true;}};
(['price', 'last', 'reordered', 'other_focus'].includes(scenario) ? price : qty).handlers.keydown(e);
const skip = ['readonly','disabled','composition','legacy_composition','ctrl','shift','alt','meta','tab','handled'].includes(scenario);
assert.equal(focused, skip ? '' : scenario === 'quantity' ? 'price' : 'code');
assert.equal(selected, focused);
assert.equal(added, scenario === 'last' ? 1 : 0);
assert.equal(qty.value, '6'); assert.equal(price.value, '0.00');
assert.equal(e.defaultPrevented, !skip || scenario === 'handled');
if (scenario === 'reordered') {
    focused = ''; doc.activeElement = doc.body;
    frame(); assert.equal(focused, 'code'); assert.equal(doc.activeElement, code);
} else if (scenario === 'other_focus') {
    focused = ''; const other = {}; doc.activeElement = other;
    frame(); assert.equal(focused, ''); assert.equal(doc.activeElement, other);
}
'''
    result = subprocess.run([node, '-e', script,
        str(ROOT / 'app/static/js/material-picker-keyboard.js'), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('template', ['document_table_form.html', 'after_sale_out_add.html'])
def test_navigation_bound_to_document_rows(template):
    source = (ROOT / 'app/templates' / template).read_text(encoding='utf-8')
    assert 'WMS.MaterialPicker.bindEntryRow(row,' in source
    assert "return next.querySelector('.material-code');" in source
    if template == 'document_table_form.html':
        assert source.index('if (readonly) return;', source.index('function bindRowEvents')) < source.index('WMS.MaterialPicker.bindEntryRow')
