'use strict';
const vm = require('node:vm');
const assert = require('node:assert/strict');
const p = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
function attrs(text) {
    const result = {};
    for (const m of text.matchAll(/([\w-]+)(?:="([^"]*)")?/g)) result[m[1]] = m[2] === undefined ? '' : m[2];
    return result;
}
class Element {
    constructor(tag, a = {}, text = '') {
        this.tagName = tag.toUpperCase(); this.attrs = a; this.children = [];
        this.dataset = {}; this.style = {}; this.value = a.value || ''; this.textContent = text;
        this.classes = new Set((a.class || '').split(/\s+/)); this.parentNode = null;
        for (const [k, v] of Object.entries(a)) if (k.startsWith('data-')) this.dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = v;
        this.classList = {contains: c => this.classes.has(c), toggle: (c, enabled) => enabled ? this.classes.add(c) : this.classes.delete(c)};
    }
    set className(s) { this.classes = new Set(s.split(/\s+/)); }
    get className() { return [...this.classes].join(' '); }
    get cells() { return this.children; }
    get firstChild() { return this.children[0] || null; }
    get nextElementSibling() { return this.parentNode?.children[this.parentNode.children.indexOf(this) + 1] || null; }
    appendChild(node) { return this.insertBefore(node, null); }
    insertBefore(node, before) {
        if (node.parentNode) node.parentNode.children.splice(node.parentNode.children.indexOf(node), 1);
        const index = before ? this.children.indexOf(before) : -1;
        this.children.splice(index < 0 ? this.children.length : index, 0, node); node.parentNode = this; return node;
    }
    remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); }
    matches(s) {
        if (s.startsWith('.')) return this.classes.has(s.slice(1));
        const m = s.match(/^(?:\w+)?\[([^=]+)="([^"]+)"\]$/);
        return m ? this.attrs[m[1]] === m[2] || (m[1] === 'data-column-key' && this.dataset.columnKey === m[2]) : this.tagName === s.toUpperCase();
    }
    querySelectorAll(s) {
        if (s.startsWith('tr:not')) return this.children.filter(n => n.tagName === 'TR' && !n.classes.has(s.includes('new-item-row') ? 'new-item-row' : 'empty-row'));
        const found = []; for (const n of this.children) { if (n.matches(s)) found.push(n); found.push(...n.querySelectorAll(s)); } return found;
    }
    querySelector(s) { return this.querySelectorAll(s)[0] || null; }
    closest(s) { if (this.matches(s)) return this; return this.parentNode?.closest(s) || null; }
    addEventListener() {} focus() {} select() {} scrollIntoView() {}
    set innerHTML(html) {
        this.children = [];
        for (const m of html.matchAll(/<td\b([^>]*)>([\s\S]*?)<\/td>/g)) {
            const cell = new Element('td', attrs(m[1]), m[2].replace(/<[^>]*>/g, '').trim());
            for (const input of m[2].matchAll(/<(input|button|span)\b([^>]*)>/g)) cell.appendChild(new Element(input[1], attrs(input[2])));
            this.appendChild(cell);
        }
    }
}
const header = new Element('tr');
p.headers.forEach(h => header.appendChild(new Element('th', h.attrs, h.text.trim())));
const tbody = new Element('tbody');
const original = new Element('tr', p.original.attrs);
p.original.cells.forEach(c => original.appendChild(new Element('td', c.attrs, c.text.trim())));
tbody.appendChild(original);
// This is the actual post-preference DOM contract: both shared saved order and
// drag controls move existing cells along with their headers before row actions.
if (p.layout !== 'default') {
    const order = [...header.children];
    const codeIndex = order.findIndex(c => /^(colCode|material_code)$/.test(c.dataset.columnKey));
    const nameIndex = order.findIndex(c => /^(colName|material_name)$/.test(c.dataset.columnKey));
    [order[codeIndex], order[nameIndex]] = [order[nameIndex], order[codeIndex]];
    const oldHeaders = [...header.children], oldCells = [...original.children];
    order.forEach(h => { original.appendChild(oldCells[oldHeaders.indexOf(h)]); header.appendChild(h); });
}
if (p.layout === 'hidden-reordered') {
    const hidden = header.children.find(h => /^(colBrand|brand)$/.test(h.dataset.columnKey));
    hidden.classList.toggle('d-none', true); hidden.style.display = 'none';
    hidden.classList.toggle('wms-field-column-hidden', true);
}
let actions; const sent = [], messages = [];
class FormData { constructor() { this.fields = {}; } append(k, v) { this.fields[k] = String(v); } }
const ctx = {FormData, document: {
    querySelector: s => s === '#itemTable tbody' ? tbody : null,
    querySelectorAll: s => s.includes('thead th') ? header.children : s.includes('tbody tr') ? tbody.children : [],
    createElement: tag => new Element(tag),
}, bindMaterialQuickInput() {}, registerDetailRowActions(a) { actions = a; },
showToast: (m, t) => messages.push({m, t}), _showToast: (m, t) => messages.push({m, t}),
WMS: {api: {postRaw: (url, data) => { sent.push({url, fields: data.fields}); return Promise.resolve({status: 'error', msg: 'fixture'}); }}},
setTimeout() {}, location: {reload() { throw Error('no navigation'); }}};
vm.createContext(ctx); vm.runInContext(p.scripts, ctx);
const keys = () => header.children.map(c => c.dataset.columnKey);
function aligned(row) {
    assert.equal(row.children.length, header.children.length, 'one cell per actual rendered header');
    assert.deepEqual(row.children.map(c => c.dataset.columnKey), keys(), 'new row follows current saved/drag order');
    header.children.forEach((h, i) => {
        assert.equal(row.children[i].classList.contains('d-none'), h.classList.contains('d-none'), 'hidden column remains hidden');
        assert.equal(row.children[i].classList.contains('wms-field-column-hidden'), h.classList.contains('wms-field-column-hidden'), 'shared field preferences remain hidden');
        assert.equal(row.children[i].style.display || '', h.style.display || '');
    });
    const expected = {Code: 'material-code', Brand: 'material-brand', Name: 'material-name', Spec: 'material-spec', Unit: 'material-unit', Stock: 'material-stock', Qty: 'material-qty', Price: 'material-price', Amount: 'material-amount', Remark: 'material-remark'};
    const out = {material_code: 'Code', brand: 'Brand', material_name: 'Name', spec: 'Spec', unit: 'Unit', stock: 'Stock', quantity: 'Qty', price: 'Price', amount: 'Amount', remark: 'Remark'};
    row.children.forEach(cell => {
        const semantic = p.page === 'in' ? cell.dataset.columnKey.replace(/^col/, '') : out[cell.dataset.columnKey];
        if (expected[semantic]) assert(cell.querySelector('.' + expected[semantic] + '-field'), cell.dataset.columnKey + ' contains its own input');
    });
    if (p.page === 'in') {
        for (const key of ['colSourcePo', 'colSourceQty', 'colSourcePushed', 'colSourceCompleted', 'colSourceStatus']) {
            const cell = row.querySelector('[data-column-key="' + key + '"]'); assert.equal(cell.querySelectorAll('input').length, 0, 'source metadata stays read only');
        }
        assert(row.querySelector('[data-column-key="colSourcePo"]').textContent.includes('手工录入'));
        if (p.business === '其他入库') assert.equal(row.querySelector('[data-column-key="colCustomerSupplied"]').textContent, '否');
    }
}
actions.add(); let added = tbody.children[0]; aligned(added);
actions.insert(original); let inserted = tbody.children[tbody.children.indexOf(original) - 1]; aligned(inserted);
if (p.customer) {
    const count = tbody.children.length; actions.copy(original);
    assert.equal(tbody.children.length, count, 'customer supplied line must not become ordinary inventory');
    assert(messages.some(m => /客供/.test(m.m)), 'explain unsupported customer supplied copy');
    assert.equal(sent.length, 0);
} else {
    actions.copy(original); let copied = original.nextElementSibling; aligned(copied);
    const fields = {code: 'M-01', brand: '品牌', name: '轴承', spec: '6204', unit: '套', stock: '99.00', qty: '2', price: '0', remark: '说明 & 中'};
    for (const [k, value] of Object.entries(fields)) assert.equal(copied.querySelector('.material-' + k + '-field').value, value, k + ' keeps source semantics');
    assert.equal(copied.querySelector('.material-amount-field').value, '0.00');
    if (p.page === 'in') {
        assert.equal(copied.querySelector('.material-batch-field').value, 'B-01');
        assert.equal(copied.querySelector('.material-expiry-field').value, '2027-01-02');
    }
    actions.copy(copied); const second = copied.nextElementSibling; aligned(second);
    for (const [k, value] of Object.entries(fields)) assert.equal(second.querySelector('.material-' + k + '-field').value, value);
    const button = second.querySelector('button'); ctx.saveInlineMaterialRow(button);
    assert.equal(sent.length, 1); const body = sent[0].fields;
    assert.equal(body.material_code, 'M-01'); assert.equal(body.quantity, '2'); assert.equal(body.price, '0'); assert.equal(body.remark, '说明 & 中');
    assert.equal(body.contract_no, 'HT-01'); assert.equal(body.project_name, '工程一');
    if (p.page === 'in') { assert.equal(body.batch_no, 'B-01'); assert.equal(body.expiry_date, '2027-01-02'); }
    assert.equal(body.source_purchase_order_item_id, undefined, 'copy creates a manual line');
    assert.equal(body.is_customer_supplied, undefined);
}
