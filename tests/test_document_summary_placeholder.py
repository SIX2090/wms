"""Unused summary placeholders must not appear as document operations."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['entry', 'existing', 'settings'])
def test_summary_placeholder_not_rendered(scenario):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const source = fs.readFileSync(process.argv[1], 'utf8');
const scenario = process.argv[2];
function extract(startText, endText) {
    const start = source.indexOf(startText);
    assert.ok(start >= 0);
    return source.slice(start, source.indexOf(endText, start));
}
function element() {
    return {children: [], classList: {contains: c => c === 'wms-doc-tabs'},
        setAttribute() {}, appendChild(e) {this.children.push(e);},
        addEventListener() {}, querySelectorAll() {return [];},
        querySelector() {return {addEventListener() {}};}};
}
const document = {createElement: element, getElementById() {return null;}, body: element()};
if (scenario === 'settings') {
    const code = extract('    function ensureModal() {', '\n    function renderRows(');
    const host = eval('(' + code.trim() + ')')();
    assert.ok(host.innerHTML.includes('data-fs-tab="detail"'));
    assert.ok(host.innerHTML.includes('data-fs-body'));
    assert.ok(!host.innerHTML.includes('data-fs-tab="summary"'));
    assert.ok(!host.innerHTML.includes('data-fs-panel="summary"'));
} else {
    const code = extract('    function ensureTabs(wrapper) {', '\n    function markToolbar(');
    let inserted;
    const wrapper = {parentNode: {insertBefore(e) {inserted = e;}},
        previousElementSibling: scenario === 'existing' ? element() : null};
    eval('(' + code.trim() + ')')(wrapper);
    if (scenario === 'existing') assert.equal(inserted, undefined);
    else {
        assert.deepEqual(inserted.children.map(e => e.textContent), ['明细']);
        assert.equal(inserted.children[0].type, 'button');
    }
}
'''
    result = subprocess.run([node, '-e', script, str(ROOT / 'app/static/js/app.js'), scenario],
        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
