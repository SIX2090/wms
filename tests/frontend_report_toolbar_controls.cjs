'use strict';
// Execute the real production template-selection and output handlers.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = process.argv[2], scenario = process.argv[3];
const source = fs.readFileSync(root + '/app/templates/report_view.html', 'utf8');
assert(source.includes('function openReportTemplateOutput('), 'report template preview/output handler missing');
const begin = source.indexOf('const templateSelect ='), end = source.indexOf('const MAX_PRINT_ROWS', begin);
assert(begin >= 0 && end > begin, 'template controls must precede the legacy standard print handler');
const nodes = {};
class Element {
    constructor(id = '') { this.id = id; this.children = []; this.value = ''; this.disabled = false; this.hidden = false; this.textContent = ''; this.handlers = {}; this.dataset = {}; this.attributes = {}; this.classList = {add(){}, remove(){}, toggle(){}}; }
    appendChild(child) { this.children.push(child); if (child.selected || (this.children.length === 1 && !this.value)) this.value = child.value; return child; }
    replaceChildren(...children) { this.children = []; this.value = ''; children.forEach(child => this.appendChild(child)); }
    set innerHTML(value) { this.children = []; this.value = ''; for (const match of value.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)) { const option = new Element(); option.value = match[1]; option.textContent = match[2]; this.appendChild(option); } }
    get options() { return this.children; }
    get selectedOptions() { return this.children.filter(child => child.value === this.value); }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    removeAttribute(name) { delete this.attributes[name]; }
    addEventListener(type, fn) { (this.handlers[type] ||= []).push(fn); }
    async click() { if (!this.disabled) for (const fn of this.handlers.click || []) await fn({preventDefault(){}}); }
    querySelector(selector) { assert.equal(selector, 'summary'); return this.summary ||= new Element(); }
    focus() { this.focused = true; }
}
function node(id) { return nodes[id] ||= new Element(id); }
const warehouse = node('warehouse_id'); warehouse.value = '2';
const requests = [], pending = [], opened = [], notices = [];
let refreshes = 0;
const context = {
    console, URLSearchParams, URL, reportType: 'out_detail',
    filterForm: {querySelector(selector) { return selector === '#warehouse_id' ? warehouse : null; }},
    document: {getElementById: node, createElement: () => new Element()},
    window: {open(url, target) { opened.push({url: new URL(url, 'http://isolated.test'), target}); return {}; }},
    buildParams(exported) { const params = new URLSearchParams({warehouse_id: warehouse.value, material_code: 'M-1', start_date: '2026-10-01', sort_field: 'quantity', sort_order: 'desc', page: '3', page_size: '20'}); if (exported) params.set('export', 'excel'); return params; },
    showToast(message) { notices.push(message); }, renderTruncation(){}, loadData(){refreshes++;},
    fetch(url) { requests.push(url); return new Promise((resolve, reject) => pending.push({resolve, reject})); },
};
context.window.showToast = context.showToast;
vm.createContext(context);
vm.runInContext(source.slice(begin, end), context);
const tick = () => new Promise(resolve => setImmediate(resolve));
const good = [
    {id: 5, name: '<自定义模板>', is_default: false, has_file: true},
    {id: 9, name: '默认版式', is_default: true, has_file: true},
    {id: 12, name: '文件丢失', is_default: false, has_file: false},
];
function reply(index, templates = good) { pending[index].resolve({ok: true, json: async () => ({status: 'success', templates})}); }
async function output(mode) { await context.openReportTemplateOutput(mode); }
(async () => {
    assert.equal(requests.length, 1, 'templates load on startup');
    assert.match(requests[0], /\/doc_print_templates\/report_out_detail\.json$/);
    assert(node('templatePreviewBtn').disabled && node('templatePrintBtn').disabled, 'loading cannot launch a stale template');
    if (scenario === 'loading') { await output('preview'); assert.equal(opened.length, 0); reply(0); await tick(); return; }
    if (scenario.startsWith('failure_')) {
        const payload = scenario === 'failure_malformed' ? {status: 'success', templates: {unexpected: true}} : {status: scenario === 'failure_business' ? 'error' : 'success', templates: good, msg: '请求失败'};
        pending[0].resolve({ok: scenario !== 'failure_http', json: async () => payload}); await tick();
        assert(node('templatePreviewBtn').disabled && node('templatePrintBtn').disabled);
        assert.equal(node('retryPrintTemplatesBtn').hidden, false); await output('preview'); assert.equal(opened.length, 0); return;
    }
    if (scenario === 'error_retry') {
        pending[0].reject(new Error('network unavailable')); await tick();
        assert(node('templatePreviewBtn').disabled && node('templatePrintBtn').disabled);
        assert.equal(node('retryPrintTemplatesBtn').hidden, false);
        const retry = node('retryPrintTemplatesBtn').click(); await tick();
        assert.equal(requests.length, 2); reply(1); await retry; await tick();
        assert.equal(node('templatePreviewBtn').disabled, false);
        assert.equal(node('templateSelect').value, '9'); return;
    }
    if (scenario === 'late_catalog') {
        const newer = context.loadPrintTemplates(); reply(1); await newer;
        reply(0, [{id: 99, name: '过期目录', has_file: true, is_default: true}]); await tick();
        assert.equal(node('templateSelect').value, '9'); assert.equal(node('templatePreviewBtn').disabled, false); return;
    }
    reply(0, scenario === 'builtin' ? [] : scenario === 'all_missing' ? good.map(item => ({...item, has_file: false})) : good); await tick();
    if (scenario === 'builtin' || scenario === 'all_missing') {
        assert.equal(node('templateSelect').value, ''); assert.equal(node('templatePreviewBtn').disabled, false);
        assert(node('templateSelect').options.filter(item => item.value !== '').every(item => item.disabled));
        await output('preview'); assert.equal(opened.length, 1); assert.equal(opened[0].url.searchParams.has('template_id'), false); return;
    }
    assert.equal(node('templateSelect').value, '9');
    assert.equal(node('templateSelect').options.find(option => String(option.value) === '12').disabled, true);
    assert.equal(node('templateSelect').options.find(option => String(option.value) === '5').textContent.includes('<自定义模板>'), true);
    if (scenario === 'defaults') return;
    if (scenario === 'refresh_escape') {
        await node('refreshReportBtn').click(); assert.equal(refreshes, 1);
        const menu = node('reportPrintMenu'); menu.open = true;
        menu.handlers.keydown.forEach(fn => fn({key: 'Escape', currentTarget: menu}));
        assert.equal(menu.open, false); assert.equal(menu.querySelector('summary').focused, true); return;
    }
    if (scenario === 'missing_warehouse') {
        warehouse.value = ''; await output('preview'); await output('download'); assert.equal(opened.length, 0);
        const visibleText = Object.values(nodes).map(item => item.textContent).join(' ') + notices.join(' ');
        assert.match(visibleText, /仓库/); return;
    }
    if (scenario === 'invalid_choice') {
        for (const unavailable of ['12', '9999']) {
            node('templateSelect').value = unavailable; await output('preview'); await output('download');
        }
        assert.equal(opened.length, 0); assert.match(node('reportPrintStatus').textContent, /不可用/); return;
    }
    node('templateSelect').value = '5'; await output('preview'); await output('download');
    assert.deepEqual(opened.map(item => item.url.pathname), ['/report/out_detail/print_preview', '/report/out_detail/print_excel']);
    for (const {url} of opened) {
        assert.equal(url.searchParams.get('template_id'), '5'); assert.equal(url.searchParams.get('warehouse_id'), '2');
        assert.equal(url.searchParams.get('material_code'), 'M-1'); assert.equal(url.searchParams.get('sort_field'), 'quantity');
        assert.equal(url.searchParams.get('sort_order'), 'desc'); assert.equal(url.searchParams.has('export'), false);
        assert.equal(url.searchParams.has('csrf_token'), false);
    }
})().catch(error => { console.error(error); process.exit(1); });
