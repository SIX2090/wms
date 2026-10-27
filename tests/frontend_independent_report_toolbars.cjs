'use strict';
// Execute the shipped workbench script with pending HTTP and real control events.
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const rootPath = process.argv[2], scenario = process.argv[3];
const source = fs.readFileSync(rootPath + '/app/static/js/report-workbench.js', 'utf8');
class Control {
    constructor() { this.value = ''; this.disabled = false; this.hidden = false; this.children = []; this.textContent = ''; this.handlers = {}; this.attributes = {}; this.dataset = {}; this.classes = new Set(); this.classList = {toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name)}; }
    appendChild(child) { this.children.push(child); return child; }
    set innerHTML(value) { assert.equal(value, ''); this.children = []; }
    addEventListener(type, handler) { (this.handlers[type] ||= []).push(handler); }
    setAttribute(key, value) { this.attributes[key] = value; }
    async event(type) { if (type === 'click' && this.disabled) return; for (const handler of this.handlers[type] || []) await handler({preventDefault(){}, currentTarget: this}); }
    get options() { return this.children; }
}
const controls = Object.fromEntries(['select', 'preview', 'download', 'status', 'retry', 'manage', 'scope', 'refresh', 'export', 'menu'].map(key => [key, new Control()]));
const stock = scenario.startsWith('stock'), summary = scenario === 'scope' || scenario === 'stale';
controls.scope.value = 'customer';
const fields = {warehouse_id: scenario === 'stock_all' ? '0' : '2', search: '轴承', csrf_token: 'SECRET'};
const form = {}, calls = [], pending = [], opened = [];
let refreshes = 0, exportCount = 0;
const mapping = {'[data-report-template]': 'select', '[data-report-preview]': 'preview', '[data-report-download]': 'download', '[data-report-status]': 'status', '[data-report-retry]': 'retry', '[data-report-manage]': 'manage', '#refreshReportBtn': 'refresh', '#exportReportBtn': 'export', '#reportPrintMenu': 'menu'};
const root = {dataset: {reportKind: stock ? 'stock' : summary ? 'summary' : 'outflow', exportAction: 'legacyExport', exportUrl: '/legacy-export', warehouse: fields.warehouse_id},
    querySelector(selector) { if (selector === '[data-report-scope]') return summary ? controls.scope : null; if (selector === '[data-report-manage]' && stock) return null; assert(mapping[selector], selector); return controls[mapping[selector]]; }, querySelectorAll() { return []; }};
if (scenario === 'export_query') {
    root.dataset.exportAction = '';
    root.dataset.exportUrl = '/sales/reconciliation/export?warehouse_id=old&format=xlsx';
}
const context = {console, URL, URLSearchParams, Set,
    document: {readyState: 'complete', querySelectorAll(selector) { assert.equal(selector, '[data-report-workbench]'); return [root]; }, querySelector(selector) { assert.equal(selector, 'form[method="get"]'); return form; }, createElement(tag) { assert.equal(tag, 'option'); return new Control(); }},
    FormData: class {constructor(value) { assert.equal(value, form); } forEach(handler) { for (const [key, value] of Object.entries(fields)) handler(value, key); }},
    window: {location: {origin: 'http://isolated.test', search: '?warehouse_id=' + fields.warehouse_id + '&sort=code&order=desc&page=7&per_page=1&embedded=1&csrf_token=SECRET', reload(){refreshes++;}, assign(url){opened.push(new URL(url, 'http://isolated.test'));}},
        legacyExport(){exportCount++;}, open(url) {opened.push(new URL(url, 'http://isolated.test'));},
        WMS: {api: {get(url) { calls.push(url); return new Promise((resolve, reject) => pending.push({resolve, reject})); }}}},
};
vm.createContext(context); vm.runInContext(source, context);
const tick = () => new Promise(resolve => setImmediate(resolve));
function reply(index, templates) { pending[index].resolve({status: 'success', templates: templates || [
    {id: 11, name: '<自定义>', has_file: true}, {id: 22, name: '默认', is_default: true, has_file: true},
    {id: 99, name: '丢失', has_file: false},
]}); }
(async () => {
    assert.equal(calls.length, 1); assert.equal(controls.preview.disabled, true);
    assert.equal(controls.download.attributes['aria-disabled'], 'true');
    if (scenario === 'failure_retry') {
        pending[0].reject(new Error('目录不可用')); await tick();
        assert.equal(controls.retry.hidden, false); assert.equal(controls.preview.disabled, true);
        const retry = controls.retry.event('click'); reply(1); await retry;
        assert.equal(controls.select.value, '22'); assert.equal(controls.preview.disabled, false); return;
    }
    if (scenario === 'stale') {
        controls.scope.value = 'material'; const newer = controls.scope.event('change');
        reply(1, [{id: 33, name: '物料模板', is_default: true, has_file: true}]); await newer;
        reply(0); await tick(); assert.equal(controls.select.value, '33'); return;
    }
    reply(0, scenario === 'builtin' ? [] : scenario === 'all_missing' ? [{id: 9, name: '无文件', has_file: false}] : undefined); await tick();
    if (scenario === 'stock_all') {
        assert.equal(controls.preview.disabled, true); await controls.download.event('click');
        assert.equal(opened.length, 0); assert.match(controls.status.textContent, /具体仓库/); return;
    }
    assert.equal(controls.preview.disabled, false);
    if (scenario === 'builtin' || scenario === 'all_missing') {
        assert.equal(controls.select.value, ''); await controls.preview.event('click');
        assert.equal(opened[0].searchParams.has('template_id'), false); return;
    }
    assert.equal(controls.select.value, '22');
    assert.equal(controls.select.options.find(option => option.value === '99').disabled, true);
    assert.equal(controls.select.options.find(option => option.value === '11').textContent, '<自定义>');
    if (scenario === 'default') return;
    if (scenario === 'export_query') {
        await controls.export.event('click');
        assert.equal(opened[0].pathname, '/sales/reconciliation/export');
        assert.deepEqual(opened[0].searchParams.getAll('warehouse_id'), ['2']);
        assert.equal(opened[0].searchParams.get('format'), 'xlsx');
        assert.equal(opened[0].searchParams.get('search'), '轴承');
        assert.equal(opened[0].searchParams.get('sort'), 'code');
        for (const key of ['page', 'per_page', 'embedded', 'csrf_token']) assert.equal(opened[0].searchParams.has(key), false);
        return;
    }
    if (scenario === 'refresh') { await controls.refresh.event('click'); assert.equal(refreshes, 1); await controls.export.event('click'); assert.equal(exportCount, 1); return; }
    if (scenario === 'filters_changed') {
        fields.search = '未查询的新条件'; await controls.preview.event('click'); await controls.download.event('click'); await controls.export.event('click');
        assert.equal(opened.length, 0); assert.equal(exportCount, 0); assert.match(controls.status.textContent, /先点击查询或筛选/); return;
    }
    if (scenario === 'scope') {
        controls.scope.value = 'material'; const next = controls.scope.event('change');
        assert.equal(controls.preview.disabled, true); assert.match(calls[1], /report_sales_summary_material\.json$/);
        reply(1); await next; await controls.preview.event('click');
        assert.equal(opened[0].pathname, '/sales/summary/print_preview'); assert.equal(opened[0].searchParams.get('scope'), 'material'); return;
    }
    controls.select.value = '11'; await controls.preview.event('click'); await controls.download.event('click');
    assert.deepEqual(opened.map(url => url.pathname), stock ? ['/report/stock/print_preview', '/report/stock/print'] : ['/sales/outflow/print_preview', '/sales/outflow/print_excel']);
    if (stock) { assert.match(calls[0], /\/stock_query\.json$/); assert.equal(opened[1].searchParams.get('template_mode'), '1'); }
    for (const url of opened) {
        assert.equal(url.searchParams.get('template_id'), '11'); assert.equal(url.searchParams.get('warehouse_id'), '2');
        assert.equal(url.searchParams.get('search'), '轴承'); assert.equal(url.searchParams.get('sort'), 'code'); assert.equal(url.searchParams.get('order'), 'desc');
        for (const key of ['page', 'per_page', 'page_size', 'embedded', 'csrf_token']) assert.equal(url.searchParams.has(key), false, key);
    }
})().catch(error => { console.error(error); process.exit(1); });
