const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert/strict');
const root = process.argv[2], scenario = process.argv[3];
const handlers = {}, documentHandlers = {}, calls = [], messages = [];
let revisionHook = () => {}, locked = false, refreshing = scenario === 'refreshing';
let warehouse = scenario === 'missing_warehouse' ? '' : '甲仓';
const body = {
    rows: [], isConnected: true,
    addEventListener(type, handler) { handlers[type] = handler; },
    contains(row) { return this.rows.includes(row); },
    insertBefore(row, next) { this.rows.splice(this.rows.indexOf(row), 1); this.rows.splice(this.rows.indexOf(next), 0, row); },
};
function createRow() {
    const fields = Object.fromEntries(['material-code', 'material-qty', 'material-name', 'material-stock', 'material-price', 'remark'].map(key => [key, {
        value: '', readOnly: ['material-name', 'material-stock'].includes(key), disabled: false,
        classList: {contains(value) { return value === key; }}, focus() {},
    }]));
    const row = {
        fields, dataset: {}, isConnected: true,
        querySelector(selector) { return fields[selector.slice(1)]; },
        querySelectorAll() { return Object.values(fields); },
        closest() { return this; },
        get nextElementSibling() { return body.rows[body.rows.indexOf(this) + 1] || null; },
    };
    Object.values(fields).forEach(field => { field.closest = () => row; field.isConnected = true; });
    body.rows.push(row); return row;
}
for (let i = 0; i < 3; i++) createRow();
let target = body.rows[0].fields['material-code'];
if (scenario === 'append') {
    body.rows[0].fields['material-code'].value = 'EXISTING';
    body.rows[0].fields['material-qty'].value = '7';
    body.rows[2].fields['material-code'].value = 'KEEP';
    body.rows[2].fields['material-qty'].value = '9';
    target = body.rows[1].fields['material-code'];
}
if (scenario === 'occupied') body.rows[0].fields['remark'].value = '保留备注';
if (scenario === 'readonly') target.readOnly = true;
const document = {
    getElementById() { return body; },
    addEventListener(type, fn) { documentHandlers[type] = fn; },
};
const materials = [];
const WMS = {
    materialCache: {warehouseFromForm() { return warehouse; }, isRefreshing() { return refreshing; }},
    api: {async get(url) {
        calls.push(url); await Promise.resolve();
        if (scenario === 'network' || scenario === 'later_batch_failure' && calls.length === 2) throw Error('模拟查询失败');
        if (scenario === 'switch_warehouse' || scenario === 'switch_back') {
            warehouse = '乙仓'; documentHandlers.change?.();
            if (scenario === 'switch_back') { warehouse = '甲仓'; documentHandlers.change?.(); }
        }
        if (scenario === 'edit_during_lookup') { body.rows[0].fields.remark.value = '正在编辑'; documentHandlers.input?.(); }
        if (scenario === 'removed') { body.rows[0].isConnected = false; body.rows.splice(0, 1); }
        if (scenario === 'locked_during_lookup') locked = true;
        return new URL('http://fixture' + url).searchParams.getAll('code')
            .filter(code => !['UNKNOWN', 'INACTIVE'].includes(code))
            .map(code => ({id: code, code, name: '物料' + code, stock: 12, price: 3}));
    }},
};
const ctx = vm.createContext({window: {WMS}, document, URLSearchParams, Map, Set,
    showToast(message) { messages.push(message); }, console});
const file = path.join(root, 'app/static/js/material-code-paste.js');
if (fs.existsSync(file)) vm.runInContext(fs.readFileSync(file, 'utf8'), ctx);
if (WMS.bindMaterialCodePaste) WMS.bindMaterialCodePaste({
    bodyId: 'grid', materials, enabled: () => !locked,
    createRow,
    fillRow(row, material) {
        row.fields['material-code'].value = material.code;
        row.fields['material-name'].value = material.name;
        row.fields['material-stock'].value = String(material.stock);
        row.fields['material-price'].value = String(material.price);
    },
    renumberRows() {}, quantitySelector: '.material-qty',
});
let text = '206065\r\n207012\r\n112012\r\n';
if (scenario === 'header') text = '\ufeff物料编码\r\n206065\r\n\r\n207012\r\n';
if (scenario === 'single') text = '206065';
if (scenario === 'leading_zero') text = '000065\n000012';
if (scenario === 'duplicates') text = '206065\n206065';
if (scenario === 'unknown') text = '206065\nUNKNOWN';
if (scenario === 'inactive') text = '206065\nINACTIVE';
if (scenario === 'multiple_columns') text = '206065\t名称\n207012\t名称';
if (scenario === 'many_codes' || scenario === 'later_batch_failure') text = Array.from({length: 401}, (_, i) => 'C' + String(i).padStart(5, '0')).join('\n');
const event = {target, clipboardData: {getData() { return text; }}, prevented: false,
    preventDefault() { this.prevented = true; }};
async function run() {
    const first = handlers.paste?.(event);
    if (scenario === 'repeat') await handlers.paste?.({...event});
    await first;
    const filled = body.rows.filter(row => row.fields['material-code'].value);
    const blocked = ['occupied', 'unknown', 'inactive', 'network', 'later_batch_failure', 'multiple_columns', 'missing_warehouse',
        'refreshing', 'switch_warehouse', 'switch_back', 'edit_during_lookup', 'removed', 'locked_during_lookup', 'readonly'].includes(scenario);
    if (blocked) {
        assert.equal(filled.length, 0, '异常/状态变化不得填入部分明细');
        assert.equal(materials.length, 0, '失败不得污染物料缓存');
        if (scenario !== 'readonly') assert(messages.length > 0, '错误须有中文提示');
        if (scenario === 'occupied') assert.equal(body.rows[0].fields.remark.value, '保留备注');
        if (scenario === 'edit_during_lookup') assert.equal(body.rows[0].fields.remark.value, '正在编辑');
    } else {
        assert(event.prevented, '编码列须拦截浏览器默认粘贴并逐行填入');
        const wanted = text.replace(/^\ufeff/, '').split(/\r?\n/).map(s => s.trim()).filter(s => s && s !== '物料编码');
        const actual = filled.filter(row => !['EXISTING', 'KEEP'].includes(row.fields['material-code'].value));
        assert.deepEqual(actual.map(row => row.fields['material-code'].value), wanted);
        assert(actual.every(row => row.fields['material-qty'].value === ''), '编码粘贴不得推断领料数量');
        assert(actual.every(row => row.fields['material-name'].value && row.fields['material-stock'].value === '12'));
        if (scenario === 'many_codes') assert.deepEqual(calls.map(url => new URL('http://fixture' + url).searchParams.getAll('code').length), [200, 200, 1]);
        if (scenario === 'repeat') assert.equal(calls.length, 1);
        if (scenario === 'append') assert.deepEqual(filled.map(row => [row.fields['material-code'].value, row.fields['material-qty'].value]),
            [['EXISTING', '7'], ['206065', ''], ['207012', ''], ['112012', ''], ['KEEP', '9']]);
        assert(calls.every(url => new URL('http://fixture' + url).searchParams.get('warehouse') === '甲仓'));
    }
}
run().catch(error => { console.error(error); process.exitCode = 1; });
