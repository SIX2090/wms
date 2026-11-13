// Actual shared form functions + real money/decimal helpers, isolated Node VM.
'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict'), Module = require('node:module');
const load = Module._load;
Module._load = function(name, ...args) {
    if (/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name)) throw Error('external IO forbidden');
    return load.call(this, name, ...args);
};
const root = process.argv[2] || path.resolve(__dirname, '..');
const template = fs.readFileSync(path.join(root, 'app/templates/document_table_form.html'), 'utf8');
function block(name) {
    let start = template.indexOf('function ' + name + '(');
    if (start < 0) return ''; // Old source lacks the new BOM helper; old paths never use it.
    if (template.slice(start - 6, start) === 'async ') start -= 6;
    const opening = template.indexOf('{', template.indexOf(') {', start));
    let depth = 0;
    for (let end = opening; end < template.length; end++) {
        depth += (template[end] === '{') - (template[end] === '}');
        if (depth === 0) return template.slice(start, end + 1);
    }
    throw Error(name);
}
function setup(docType = 'bom') {
    const rows = [];
    const material = {id: 3, code: 'B-M', name: '合成子件', unit_id: 1, unit: {id: 1, name: '个'}, price: 1.2345};
    function input(selector) {
        let value = ''; const events = {};
        return {get value() {return value;}, set value(v) {value = String(v);}, style: {}, dataset: {},
            classList: {contains: name => selector === '.' + name}, focus() {},
            addEventListener: (name, fn) => {events[name] = fn;}, fire(name) {events[name]?.call(this, {});}};
    }
    function row() {
        const fields = {};
        for (const s of ['.material-code', '.material-brand', '.material-name', '.material-spec', '.material-unit', '.unit-id', '.material-stock', '.line-qty', '.line-price', '.line-amount', '.line-usage', '.line-remark', '.system-stock', '.actual-stock', '.line-area', '.line-reason', '.line-diff']) fields[s] = input(s);
        return {dataset: {}, fields, querySelector: s => fields[s] || null,
            querySelectorAll: s => s.startsWith('.line-qty,') ? [fields['.line-qty'], fields['.line-price'], fields['.actual-stock'], fields['.system-stock']] : []};
    }
    const table = {insertRow: () => {const r = row(); rows.push(r); return r;}, insertBefore() {}, rows};
    const context = {docType, readonly: false, hasCountedByCol: false, checkLocationRequired: false,
        document: {getElementById: () => table, querySelectorAll: () => rows},
        rowCells: () => '', findMaterialByCode: code => code === 'B-M' ? material : null,
        getMaterialUnitId: () => 1, calcTotal() {}, renumberRows() {}, materials: [material],
        WMS: {MaterialPicker: {bindEntryRow() {}}}};
    context.window = context; vm.createContext(context);
    for (const rel of ['app/static/js/decimal-input.js', 'app/static/js/money.js']) vm.runInContext(fs.readFileSync(path.join(root, rel), 'utf8'), context);
    vm.runInContext(['formatQty', 'getMaterialUnit', 'fillMaterialFields', 'bomRecordedFieldUnchanged', 'createRow', 'bindRowEvents', 'copyRowAfter', 'calcRow', 'updateCheckDiff', 'collectItems', 'findEmptyRow', 'parsePastedData'].map(block).join('\n'), context);
    const data = {line_id: 10, material_id: 3, code: 'B-M', unit_id: 1, quantity: 3.33,
        price: 1.2345, recorded_unit_cost: 1.2345, total_cost: 4.11, recorded_total_cost: 4.11};
    const r = context.createRow(data);
    return {context, rows, r, data, fields: r.fields, input, material};
}
let passed = 0, failed = 0;
function test(name, run) {
    try {run(); passed++; console.log('PASS ' + name);} catch (error) {failed++; console.error('FAIL ' + name + ': ' + error.message);}
}
test('open and blur keep full original unit cost', () => {
    const c = setup(); assert.equal(c.fields['.line-price'].value, '1.2345');
    c.fields['.line-price'].fire('blur'); assert.equal(c.fields['.line-price'].value, '1.2345');
    assert.equal(c.fields['.line-amount'].value, '4.11');
});
test('note/usage edit sends original identity and full finance', () => {
    const c = setup(); c.fields['.line-remark'].value = '只改备注'; c.fields['.line-usage'].value = '用途';
    const p = c.context.collectItems(); assert.equal(p.invalidRows.length, 0);
    assert.equal(p.items[0].line_id, 10); assert.equal(p.items[0].price, 1.2345); assert.equal(p.items[0].quantity, 3.33);
    assert.equal(p.items[0].remark, '只改备注'); assert.equal(p.items[0].usage, '用途');
});
test('explicit cost change to displayed two places is not swallowed', () => {
    const c = setup(); c.fields['.line-price'].value = '1.23'; c.fields['.line-price'].fire('blur');
    assert.equal(c.context.collectItems().items[0].price, 1.23); assert.equal(c.fields['.line-amount'].value, '4.10');
});
test('precise and tiny existing quantity survive blur and collect', () => {
    for (const quantity of [1.2345, .0001]) {
        const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, quantity});
        r.fields['.line-qty'].fire('blur'); assert.equal(c.context.collectItems().items[0].quantity, quantity);
    }
});
test('explicit precise quantity edit to two places takes effect', () => {
    const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, quantity: 1.2345});
    r.fields['.line-qty'].value = '1.23'; r.fields['.line-qty'].fire('blur');
    assert.equal(c.context.collectItems().items[0].quantity, 1.23); assert.equal(c.context.collectItems().items[0].price, 1.2345);
});
test('known zero and legacy divergent line money remain displayed', () => {
    for (const total of [0, 4.02, 7.77]) {
        const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, recorded_total_cost: total});
        c.context.calcRow(r); assert.equal(r.fields['.line-amount'].value, total.toFixed(2));
    }
});
test('known zero unit cost survives normalization', () => {
    const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, recorded_unit_cost: 0, recorded_total_cost: 0, price: 0});
    r.fields['.line-price'].fire('blur'); assert.equal(c.context.collectItems().items[0].price, 0);
});
test('new zero quantity still rejected', () => {
    const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, line_id: null, quantity: 0});
    assert.equal(c.context.collectItems().items.length, 0); assert.equal(c.context.collectItems().invalidRows.length, 1);
});
test('new rows retain two place quantity and price policy', () => {
    const c = setup(); c.rows.length = 0; c.context.createRow({...c.data, line_id: null, quantity: 1.2345});
    const p = c.context.collectItems(); assert.equal(p.items[0].quantity, 1.23); assert.equal(p.items[0].price, 1.23); assert.equal(p.items[0].line_id, undefined);
});
test('copied row is new and does not carry original identity/money', () => {
    const c = setup(); c.context.copyRowAfter(c.r); const p = c.context.collectItems();
    assert.equal(p.items.length, 2); assert.equal(p.items[0].line_id, 10); assert.equal(p.items[1].line_id, undefined);
    assert.equal(p.items[1].price, 1.23); assert.equal(p.items[1].quantity, 3.33);
});
test('same SKU duplicate rows retain distinct identities and amounts', () => {
    const c = setup(); const r = c.context.createRow({...c.data, line_id: 11, recorded_total_cost: 7.77});
    const p = c.context.collectItems(); assert.equal(p.items[0].line_id, 10); assert.equal(p.items[1].line_id, 11); assert.equal(r.fields['.line-amount'].value, '7.77');
});
test('large signed-64-bit line identity is transported as exact text', () => {
    const c = setup(); c.rows.length = 0;
    c.context.createRow({...c.data, line_id: '9223372036854775807'});
    assert.equal(c.context.collectItems().items[0].line_id, '9223372036854775807');
});
test('unknown NULL cost does not activate recorded finance preservation', () => {
    const c = setup(); c.rows.length = 0; const r = c.context.createRow({...c.data, recorded_unit_cost: null});
    assert.equal(r.fields['.line-price'].value, '1.23'); assert.equal(r.fields['.line-amount'].value, '4.10');
});
for (const type of ['transfer', 'requisition']) test(type + ' shared formatting and payload stay unchanged', () => {
    const c = setup(type); assert.equal(c.fields['.line-price'].value, '1.23');
    const p = c.context.collectItems(); assert.equal(p.items[0].price, 1.23); assert.equal(p.items[0].line_id, undefined);
});
test('check shared counted/uncounted payload stays unchanged', () => {
    const c = setup('check'); const p = c.context.collectItems();
    assert.equal(p.items[0].actual_stock, null); assert.equal(p.items[0].line_id, undefined);
});
(async () => {
    try {
        const c = setup(), notices = [], area = {value: 'B-M\t2.67\t粘贴备注', isConnected: true};
        const button = {disabled: false}; let closed = false;
        const originalGet = c.context.document.getElementById;
        c.context.document.getElementById = id => id === 'pasteArea' ? area : id === 'pasteModal' ? {remove() {closed = true;}} : originalGet(id);
        c.context.document.querySelector = () => button;
        c.context.WMS.materialCache = {warehouseFromForm: () => '', isRefreshing: () => false};
        c.context.showToast = (...args) => notices.push(args);
        c.context.URLSearchParams = URLSearchParams;
        await c.context.parsePastedData();
        const p = c.context.collectItems();
        assert.equal(p.invalidRows.length, 0); assert.equal(p.items.length, 2);
        assert.equal(p.items[0].price, 1.2345); assert.equal(p.items[0].line_id, 10);
        assert.equal(p.items[1].line_id, undefined); assert.equal(p.items[1].quantity, 2.67); assert.equal(p.items[1].price, 1.23);
        assert.equal(p.items[1].remark, '粘贴备注'); assert.equal(closed, true); assert.equal(notices.at(-1)[1], 'success');
        passed++; console.log('PASS paste adds a new normalized row without changing original finance');
    } catch (error) {failed++; console.error('FAIL paste: ' + error.message);}
    console.log(`TOTAL ${passed + failed} passed=${passed} failed=${failed}`);
    process.exitCode = failed ? 1 : 0;
})();
