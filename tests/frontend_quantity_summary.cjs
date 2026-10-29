const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const config = JSON.parse(fs.readFileSync(0, 'utf8'));
const id = config['data-quantity-summary'];
let rows = [], observer;
const events = {}, formEvents = {};
const output = {textContent: '0.00'};
const body = {};
const table = {
    querySelectorAll(selector) { assert.equal(selector, 'tbody tr'); return rows; },
    querySelector(selector) { assert.equal(selector, 'tbody'); return body; },
    addEventListener(name, callback) { events[name] = callback; },
    closest() { return {addEventListener(name, callback) { formEvents[name] = callback; }}; }
};
const summary = {
    dataset: {quantitySummary: id, quantitySelector: config['data-quantity-selector'], materialSelector: config['data-material-selector']},
    querySelector() { return output; }
};
const document = {
    readyState: 'complete',
    querySelectorAll() { return [summary]; },
    getElementById(key) { return key === id ? table : null; }
};
const window = {setTimeout(callback) { callback(); }};
const context = {window, document, MutationObserver: class {
    constructor(callback) { observer = callback; }
    observe(target) { assert.equal(target, body); }
}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../app/static/js/quantity-summary.js'), 'utf8'), context);
function row(code, qty, saved = false) {
    const quantity = saved ? {textContent: qty} : {value: qty};
    const material = saved ? null : {value: code};
    return {quantity, material, querySelector(selector) {
        if (selector === config['data-quantity-selector']) return quantity;
        if (selector === config['data-material-selector']) return material;
        throw Error(selector);
    }};
}
assert.equal(output.textContent, '0.00');
rows = [row('', '1'), row('A', '2.5'), row('B', '1.25'), row('C', 'NaN')];
observer();
assert.equal(output.textContent, '3.75', 'blank default rows and invalid input excluded');
rows[1].quantity.value = '7.125'; events.input();
assert.equal(output.textContent, '8.375', 'typing is visible before blur/save');
rows.push(row('B', '1.25')); observer();
assert.equal(output.textContent, '9.625', 'copy/insert');
rows.splice(1, 1); observer();
assert.equal(output.textContent, '2.50', 'delete');
rows = [row('A', '0.0001'), row('B', '0.0002')];
window.WMS.refreshQuantityTotals(id);
assert.equal(output.textContent, '0.0003', 'programmatic import/restore retains four decimal places');
rows = [row('A', '1000.25', true), row('B', '2.5')]; observer();
assert.equal(output.textContent, '1,002.75', 'saved subcontract rows plus unsaved rows');
rows[1].material.value = ''; events.change();
assert.equal(output.textContent, '1,000.25', 'cleared identity excluded');
rows = [row('A', '2.50', true)];
rows[0].quantity.querySelector = () => ({value: '7.125'});
events.input();
assert.equal(output.textContent, '7.125', 'existing detail cell includes its unsaved editor value');
rows[0].quantity.querySelector = () => null;
rows[0].quantity.dataset = {value: '2.5'};
rows[0].quantity.textContent = '2.50 编辑';
observer();
assert.equal(output.textContent, '2.50', 'cancelled cell editor uses its restored value, excluding edit icons');
rows = []; formEvents.reset();
assert.equal(output.textContent, '0.00', 'reset/clear');
console.log('before-save quantity lifecycle passed: ' + id);
