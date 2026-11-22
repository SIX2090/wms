const assert = require('node:assert/strict');
const {resolve} = require('node:path');

let onPaste, message, locked;
const rows = Array.from({length: 6}, (_, i) => {
    const row = {code: 'M' + i, source: 'PO-' + i};
    row.quantity = {
        value: '9', changes: 0,
        matches: selector => selector === '.quantity',
        closest: () => row,
        dispatchEvent(event) {
            assert.equal(event.type, 'input');
            assert.equal(event.bubbles, true);
            this.changes++;
        }
    };
    row.querySelector = selector => selector === '.material-code' ? {value: row.code} : row.quantity;
    return row;
});
global.document = {getElementById: () => ({rows, addEventListener: (_, handler) => {onPaste = handler;}})};
global.window = {WMS: {}};
global.showToast = text => {message = text;};
require(resolve(__dirname, '../app/static/js/quantity-column-paste.js'));

function bind(stocktake) {
    window.WMS.bindQuantityColumnPaste('body', '.quantity', () => !locked, stocktake);
}
function paste(text) {
    let prevented = false;
    message = '';
    onPaste({target: rows[1].quantity, clipboardData: {getData: () => text},
        preventDefault: () => {prevented = true;}});
    return prevented;
}
function snapshot() {
    return rows.map(r => [r.code, r.source, r.quantity.value, r.quantity.changes]);
}
bind(true);
assert.ok(paste('5\r\n\r\n0\r\n8\r\n'));
assert.deepEqual(rows.map(r => r.quantity.value), ['9', '5', '', '0', '8', '9']);
assert.deepEqual(rows.map(r => r.quantity.changes), [0, 1, 1, 1, 1, 0]);
assert.ok(rows.every((r, i) => r.code === 'M' + i && r.source === 'PO-' + i));
bind(false);
for (const invalid of ['1\n0', '1\n\n3', '1\n-1', '2\n3.456', '1\t2', '1\nabc', '1\n2\n3\n4\n5\n6']) {
    const before = snapshot();
    assert.ok(paste(invalid));
    assert.deepEqual(snapshot(), before);
    assert.ok(message);
}
for (const state of ['locked', 'readonly', 'disabled', 'empty']) {
    locked = state === 'locked';
    rows[2].quantity.readOnly = state === 'readonly';
    rows[2].quantity.disabled = state === 'disabled';
    rows[2].code = state === 'empty' ? '' : 'M2';
    const before = snapshot();
    assert.ok(paste('2\n3'));
    assert.deepEqual(snapshot(), before);
}
rows[2].code = 'M2';
assert.ok(paste('12.50\n.75'));
assert.deepEqual(rows.slice(1, 3).map(r => Number(r.quantity.value)), [12.5, .75]);
assert.equal(paste('3'), false); // A normal single-cell paste belongs to the browser.
