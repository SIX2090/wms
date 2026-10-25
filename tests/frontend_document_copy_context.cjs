const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const scenario = process.argv[2];
const populated = process.argv[3] === 'populated';
const contract = populated ? 'HT-001 "项目"' : '';
const project = populated ? '改造工程 & 二期' : '';
const remark = populated ? '随货补说明书；请核对' : '';
const read = name => fs.readFileSync(path.join(__dirname, '..', 'app', 'templates', name), 'utf8');
function segment(s, start, end) {
    const a = s.indexOf(start); assert(a >= 0, start);
    const b = s.indexOf(end, a + start.length); assert(b > a, end);
    return s.slice(a, b);
}
function node(value = '') {
    return {value, dataset: {}, textContent: '', style: {}, addEventListener() {}, focus() {}, select() {}};
}
function row(values = {}) {
    const nodes = {};
    Object.entries(values).forEach(([k, v]) => { nodes[k] = node(v); });
    return {nodes, nextElementSibling: null, querySelector(s) { return nodes[s] || (nodes[s] = node()); }, querySelectorAll() { return []; }};
}
const values = {'.material-code': 'M-01', '.material-name': '轴承', '.material-spec': '6204', '.material-unit': '套', '.material-qty': '2', '.material-price': '0', '.material-remark': remark, '.qty': '2', '.price': '0', '.tax-rate': '0', '.batch-no': 'B-1', '.serial-no': 'S-1', '.line-remark': remark, '.line-contract-no': contract, '.line-project-name': project};
if (scenario === 'purchase-copy') {
    const source = read('purchase_order_add.html'); const original = row(values);
    original.querySelector('.material-code').dataset.materialId = '11';
    const ctx = {}; vm.createContext(ctx);
    vm.runInContext(segment(source, 'function rowData(row)', 'function insertRowBefore(btn)'), ctx);
    const actual = ctx.rowData(original);
    assert.equal(actual.material_code, 'M-01'); assert.equal(actual.price, '0'); assert.equal(actual.quantity, '2');
    assert.equal(actual.remark, remark);
    assert.equal(actual.contract_no || '', contract); assert.equal(actual.project_name || '', project);
} else if (scenario === 'sales-add-copy') {
    const source = read('sales_order_add.html'); const original = row(values); let copied;
    const ctx = {document: {createElement() { return copied = row(); }}, body: {appendChild() {}}, fillRow() {}, findMaterial() { return {code: 'M-01'}; }, window: {}, renumber() {}, recalc() {}};
    vm.createContext(ctx); vm.runInContext(segment(source, 'function addRow(copyFrom)', 'function renumber()'), ctx);
    ctx.addRow(original);
    assert.equal(copied.querySelector('.material-code').value, 'M-01');
    assert.equal(copied.querySelector('.price').value, '0'); assert.equal(copied.querySelector('.tax-rate').value, '0');
    assert.equal(copied.querySelector('.line-remark').value, remark);
    assert.equal(copied.querySelector('.line-contract-no').value, contract); assert.equal(copied.querySelector('.line-project-name').value, project);
} else if (scenario.startsWith('sales-')) {
    const edit = scenario !== 'sales-add-template';
    const source = read(edit ? 'sales_order_edit.html' : 'sales_order_add.html');
    const handlers = {}; const original = row(values); const added = [];
    const template = {items: [{code: 'M-01', quantity: '2', price: '0', tax_rate: '0', batch_no: 'B-1', serial_no: 'S-1', remark, contract_no: contract, project_name: project}]};
    const ctx = {document: {getElementById(id) { return {addEventListener(type, fn) { handlers[id] = fn; }, textContent: ''}; }}, body: {querySelector() { return original; }, set innerHTML(value) {}}, localStorage: {getItem() { return JSON.stringify([template]); }}, SALES_TEMPLATE_KEY: 'qa', defaultTaxRate: .13, addRow(data) { const r = row(); added.push({data: data || {}, row: r}); return r; }, fillRow() {}, findMaterial() { return {}; }, ensureBlankRows() {}, renumber() {}, recalc() {}};
    vm.createContext(ctx);
    if (scenario === 'sales-edit-copy') {
        vm.runInContext(segment(source, "document.getElementById('copyRowBtn').addEventListener", "document.getElementById('pasteBtn').addEventListener"), ctx);
        handlers.copyRowBtn();
    } else {
        vm.runInContext(segment(source, "document.getElementById('templateSelect').addEventListener", "document.getElementById('refreshMaterialsBtn').addEventListener"), ctx);
        handlers.templateSelect.call({value: '0'});
    }
    assert.equal(added.length, 1);
    const result = added[0];
    if (edit) {
        assert.equal(result.data.code, 'M-01'); assert.equal(result.data.price, '0'); assert.equal(result.data.tax_rate, '0');
        assert.equal(result.data.remark, remark);
        assert.equal(result.data.contract_no || '', contract); assert.equal(result.data.project_name || '', project);
    } else {
        assert.equal(result.row.querySelector('.material-code').value, 'M-01'); assert.equal(result.row.querySelector('.price').value, '0');
        assert.equal(result.row.querySelector('.line-remark').value, remark);
        assert.equal(result.row.querySelector('.line-contract-no').value, contract); assert.equal(result.row.querySelector('.line-project-name').value, project);
    }
} else if (scenario === 'aftersale-copy') {
    const source = read('after_sale_out_add.html');
    function extract(name) { const a = source.indexOf('function ' + name + '('); assert(a >= 0); const b = source.indexOf('\nfunction ', a + 1); return source.slice(a, b < 0 ? source.length : b); }
    const original = row(values); const copied = row();
    const ctx = {addNewRow() { return copied; }, calcAmount() {}, document: {querySelectorAll() { return [copied]; }}};
    vm.createContext(ctx); vm.runInContext(extract('copyRowAfter') + '\n' + extract('collectAfterSaleOutRows'), ctx);
    ctx.copyRowAfter(original); const result = ctx.collectAfterSaleOutRows();
    assert.equal(result.items[0].code, 'M-01'); assert.equal(result.items[0].price, 0);
    assert.equal(result.items[0].remark, remark);
} else { throw new Error('Unknown scenario: ' + scenario); }
process.stdout.write(JSON.stringify({passed: true, scenario, populated}));
