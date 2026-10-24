"""Execute the actual template keyboard handlers, including notice rows and IME."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('template', ['in_order_add.html', 'out_order_add.html'])
def test_material_keyboard_navigation(template):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required to execute browser keyboard handlers')
    source = (ROOT / 'app/templates' / template).read_text(encoding='utf-8')
    handler = re.search(r'function handleKeydown\(event, row\) \{.*?(?=\nfunction )', source, re.S).group(0)
    if 'function cancelMaterialSearch(' in source:
        state = re.search(r'const materialSearchState = [^\n]+', source).group(0)
        cancel = re.search(r'function cancelMaterialSearch\(\) \{.*?\n\}', source, re.S).group(0)
        handler = state + '\n' + cancel + '\n' + handler
    harness = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const handler = JSON.parse(fs.readFileSync(0, 'utf8'));
let activeDropdown = null;
let selected = [], focused = 0;
function selectMaterial(row, code) { selected.push(code); row.menu.style.display = 'none'; }
function focusNextEditable() { focused++; }
function item(code) {
    const classes = new Set();
    return {dataset: code ? {code} : {},
        classList: {contains: c => classes.has(c), add: c => classes.add(c), remove: c => classes.delete(c)},
        scrollIntoView() {}};
}
function row() {
    const items = [item(), item('M001'), item('M002')];
    const menu = {style: {display: 'block'}, items,
        querySelectorAll(selector) {
            return items.filter(i => !selector.includes('[data-code]') || i.dataset.code);
        },
        querySelector(selector) {
            return this.querySelectorAll(selector).find(i => !selector.includes('.active') || i.classList.contains('active')) || null;
        }};
    return {menu, querySelector: () => menu};
}
function event(key, composing = false, keyCode = 0) {
    return {key, isComposing: composing, keyCode, prevented: false,
        target: {classList: {contains: c => c === 'material-code'}},
        preventDefault() { this.prevented = true; }};
}
eval(handler);
// IME confirmation must not choose a material or steal focus.
const imeRow = row();
const ime = event('Enter', true);
handleKeydown(ime, imeRow);
assert.equal(ime.prevented, false);
assert.deepEqual(selected, []);
assert.equal(focused, 0);
handleKeydown(event('Enter', false, 229), imeRow);
assert.deepEqual(selected, []);
// Notices are never candidates; Enter chooses the first real material.
handleKeydown(event('Enter'), row());
assert.deepEqual(selected, ['M001']);
selected = [];
const r = row(), other = row();
const down = event('ArrowDown');
handleKeydown(down, r);
assert.equal(down.prevented, true);
assert.equal(r.menu.items[0].classList.contains('active'), false);
assert.equal(r.menu.items[1].classList.contains('active'), true);
handleKeydown(event('ArrowDown'), r);
handleKeydown(event('ArrowDown'), r);
assert.equal(r.menu.items[2].classList.contains('active'), true);
assert.equal(other.menu.items.some(i => i.classList.contains('active')), false);
handleKeydown(event('Enter'), r);
assert.deepEqual(selected, ['M002']);
const upRow = row();
handleKeydown(event('ArrowUp'), upRow);
assert.equal(upRow.menu.items[2].classList.contains('active'), true);
handleKeydown(event('ArrowUp'), upRow);
handleKeydown(event('ArrowUp'), upRow);
assert.equal(upRow.menu.items[1].classList.contains('active'), true);
handleKeydown(event('Escape'), upRow);
assert.equal(upRow.menu.style.display, 'none');
handleKeydown(event('Enter'), upRow);
assert.equal(focused, 1);
assert.deepEqual(selected, ['M002']);
'''
    result = subprocess.run([node, '-e', harness], input=json.dumps(handler),
                            capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
