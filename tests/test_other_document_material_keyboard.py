"""Execute the actual material-picker handlers across the remaining documents."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = [
    'document_table_form.html', 'after_sale_out_add.html',
    'purchase_request_add.html', 'purchase_order_add.html',
    'sales_order_add.html', 'sales_order_edit.html',
]


def _handler(template):
    source = (ROOT / 'app/templates' / template).read_text(encoding='utf-8')
    if template.startswith('sales_order_'):
        return re.search(r'function handleKeydown\(event, row\) \{.*?(?=\n    function )', source, re.S).group(0)
    binder = 'bindRowEvents' if template == 'document_table_form.html' else (
        'bindMaterialInput' if template == 'purchase_request_add.html' else 'bindRow')
    source = source[source.index('function ' + binder + '('):]
    return re.search(r"addEventListener\('keydown', (function\((?:event|e)\) \{.*?\n    \})\);", source, re.S).group(1)


def _run(template, scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for document keyboard runtime tests')
    payload = {'handler': _handler(template), 'scenario': scenario,
               'sales': template.startswith('sales_order_'),
               'helper': str(ROOT / 'app/static/js/material-picker-keyboard.js')}
    if template == 'after_sale_out_add.html':
        source = (ROOT / 'app/templates' / template).read_text(encoding='utf-8')
        payload['selector'] = re.search(r'function selectMaterial\(row, code\) \{.*?(?=\nfunction )', source, re.S).group(0)
    harness = r'''
const assert = require('node:assert/strict');
const data = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
global.window = global;
require(data.helper);
const WMS = window.WMS;
let selected = [], focusCount = 0, activeDropdown = null;
let activeMaterialIndex = 0;
const input = {value: 'M001', classList: {contains: c => c === 'material-code'}};
function item(code) {
    const classes = new Set();
    return {dataset: code ? {code} : {empty: '1'},
        classList: {contains: c => classes.has(c), add: c => classes.add(c),
                    remove: c => classes.delete(c), toggle: (c, v) => v ? classes.add(c) : classes.delete(c)},
        scrollIntoView() {}};
}
const options = [item(), item('M001'), item('M002')];
const dropdown = {style: {display: 'block'},
    querySelectorAll(s) {return options.filter(i => (!s.includes('[data-code]') || i.dataset.code) &&
        (!s.includes('data-empty') || i.dataset.empty !== '1'));},
    querySelector(s) {return this.querySelectorAll(s).find(i => !s.includes('.active') || i.classList.contains('active')) || null;}};
const qty = {focus() {focusCount++;}, select() {}};
const row = {querySelector: s => s === '.material-dropdown' ? dropdown : s === '.material-code' ? input : qty};
activeDropdown = dropdown;
function findMaterialByCode(code) {return code === 'M001' || code === 'M002' ? {code} : null;}
function fillMaterialFields(row, material) {selected.push(material.code);}
const materials = [{code: 'M001', name: '物料一'}, {code: 'M002', name: '物料二'}];
const selector = data.selector ? eval('(' + data.selector + ')') : null;
function calcAmount() {}
function selectMaterial(row, code) {
    selected.push(code);
    if (selector) selector(row, code);
    else { dropdown.style.display = 'none'; qty.focus(); }
}
function hideDropdown() {dropdown.style.display = 'none'; activeDropdown = null;}
function highlightMaterialDropdownItem(items) {items.forEach((i, n) => i.classList.toggle('active', n === activeMaterialIndex));}
function showDropdown() {throw Error('Unexpected dropdown search');}
function event(key, composing = false, keyCode = 0) {
    return {key, isComposing: composing, keyCode, target: input, prevented: false,
            preventDefault() {this.prevented = true;}};
}
const handler = eval('(' + data.handler + ')');
function invoke(e) {handler.call(input, e, row);}
if (data.scenario === 'composition') {
    for (const e of [event('Enter', true), event('ArrowDown', true), event('Enter', false, 229)]) {
        invoke(e);
        assert.equal(e.prevented, false);
        assert.deepEqual(selected, []);
        assert.equal(focusCount, 0);
        assert.equal(options.some(i => i.classList.contains('active')), false);
    }
} else {
    // The non-material notice must never be highlighted or selected.
    invoke(event('ArrowDown'));
    invoke(event('ArrowDown'));
    invoke(event('ArrowDown'));
    assert.equal(options[0].classList.contains('active'), false);
    assert.equal(options[2].classList.contains('active'), true);
    invoke(event('Enter'));
    assert.deepEqual(selected, ['M002']);
    assert.equal(focusCount, 1);
    assert.equal(dropdown.style.display, 'none');
    dropdown.style.display = 'block';
    options.forEach(i => i.classList.remove('active'));
    invoke(event('ArrowUp'));
    assert.equal(options[2].classList.contains('active'), true);
    invoke(event('ArrowUp'));
    invoke(event('ArrowUp'));
    assert.equal(options[1].classList.contains('active'), true);
    invoke(event('Escape'));
    assert.equal(dropdown.style.display, 'none');
    assert.equal(activeDropdown, null);
    // Hidden and empty pickers leave exact-code fallback to the page.
    assert.equal(WMS.MaterialPicker.handleKeydown(event('Enter'), dropdown, () => {throw Error('Hidden picker selected');}), false);
    dropdown.style.display = 'block';
    options.splice(1);
    assert.equal(WMS.MaterialPicker.handleKeydown(event('Enter'), dropdown, () => {throw Error('Notice selected');}), false);
}
'''
    result = subprocess.run([node, '-e', harness], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('template', TEMPLATES)
def test_chinese_composition_does_not_select_material(template):
    _run(template, 'composition')


@pytest.mark.parametrize('template', TEMPLATES[:2])
def test_shared_document_material_navigation(template):
    _run(template, 'navigation')
