const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const root = process.argv[2], scenario = process.argv[3];
const tpl = fs.readFileSync(root + '/app/templates/report_view.html', 'utf8');
const helper = fs.readFileSync(root + '/app/static/js/material-movement-report.js', 'utf8');
const shared = fs.readFileSync(root + '/app/static/js/app.js', 'utf8');
function slice(start, end) {
    const a = tpl.indexOf(start), b = tpl.indexOf(end, a + start.length);
    assert(a >= 0 && b > a); return tpl.slice(a, b);
}
const nodes = Object.fromEntries(['opening_quantity', 'in_quantity', 'out_quantity', 'balance_quantity'].map(k => ['summary-' + k, { textContent: 'OLD' }]));
nodes.materialMovementCount = { textContent: 'OLD' }; nodes.printArea = { innerHTML: '' };
const ctx = { window: {}, reportType: 'material_movement', reportTitle: '物料收发存',
    document: { getElementById(id) { return nodes[id] || null; } }, URL, URLSearchParams };
vm.createContext(ctx); vm.runInContext(helper, ctx);
const data = { count: 2, unit_totals: [
    { unit: '件', opening_quantity: 10, in_quantity: 3, out_quantity: 2, balance_quantity: 11 },
    { unit: '米<&>', opening_quantity: 20, in_quantity: 0, out_quantity: 5, balance_quantity: 15 }
] };
if (scenario === 'units' || scenario === 'error') {
    vm.runInContext(slice('function renderSummary(', '\nfunction renderTable('), ctx);
    ctx.renderSummary(data);
    assert.equal(nodes['summary-balance_quantity'].textContent, '11 件 / 15 米<&>');
    assert.equal(nodes.materialMovementCount.textContent, '物料数：2');
    if (scenario === 'error') {
        ctx.renderSummary(null);
        assert.equal(nodes.materialMovementCount.textContent, '物料数：—');
        for (const key of ['opening_quantity', 'in_quantity', 'out_quantity', 'balance_quantity'])
            assert.equal(nodes['summary-' + key].textContent, '—');
    }
} else if (scenario === 'print') {
    const start = shared.indexOf('function escapeHtml('), end = shared.indexOf('\nfunction openAdd(', start);
    assert(start >= 0 && end > start);
    vm.runInContext(shared.slice(start, end) + '\n' + slice('function formatValue(', '\nfunction renderSummary(') + '\n' + slice('function renderPrintArea(', '\nfunction buildParams('), ctx);
    ctx.renderPrintArea([{ field: 'material_name', title: '物料名称' }], [{ material_name: '<img onerror=bad>' }], false,
        { metaParts: [], summary: data, summaryLabels: { count: '物料数', opening_quantity: '期初', in_quantity: '入库', out_quantity: '出库', balance_quantity: '结存' }, summaryTypes: { count: 'number' } });
    const html = nodes.printArea.innerHTML;
    assert(html.includes('结存 11 件 / 15 米&lt;&amp;&gt;'));
    assert(html.includes('物料数 2')); assert(!html.includes('<img onerror=bad>'));
} else if (['switch', 'embedded_switch', 'embedded_all_switch'].includes(scenario)) {
    let clicked, assigned;
    const documentHandlers = [];
    const link = { href: 'http://qa.test/report/view/summary?summary_view=daily',
        addEventListener(_, fn) { clicked = fn; }, getAttribute(name) { assert.equal(name, 'href'); return this.href; }, hasAttribute() { return false; } };
    ctx.document.querySelectorAll = selector => { assert.equal(selector, '[data-summary-view]'); return [link]; };
    ctx.window.location = { origin: 'http://qa.test', search: '?embedded=1',
        get href() { return 'http://qa.test/report/view/summary?embedded=1'; },
        set href(value) { assigned = new URL(value, this.origin); }, assign(url) { assigned = new URL(url); } };
    ctx.buildParams = () => new URLSearchParams('warehouse_id=4&material_code=A%26B&page=8&status=pending&' +
        (scenario === 'embedded_all_switch' ? 'date_scope=all' : 'start_date=2026-10-01&end_date=2026-10-20&date_scope=period'));
    if (scenario !== 'switch') {
        // Run the real document delegate after the real link handler, as the browser does.
        ctx.document.addEventListener = (_, fn) => documentHandlers.push(fn);
        const a = shared.indexOf("document.addEventListener('click', function(event) {", shared.indexOf('// 嵌入页面链接处理'));
        const b = shared.indexOf('\n        });', a) + '\n        });'.length;
        const helperStart = shared.indexOf('function withEmbeddedParam('), helperEnd = shared.indexOf('\nfunction isMobileViewport(', helperStart);
        assert(a >= 0 && b > a && helperEnd > helperStart);
        vm.runInContext(shared.slice(helperStart, helperEnd) + '\n' + shared.slice(a, b), ctx);
    }
    vm.runInContext(slice("document.querySelectorAll('[data-summary-view]')", "\nif (reportType === 'ledger')"), ctx);
    const event = { target: { closest() { return link; } }, preventDefault() {}, stopPropagation() { this.stopped = true; } };
    clicked(event);
    if (!event.stopped) documentHandlers.forEach(fn => fn(event));
    assert.equal(assigned.searchParams.get('summary_view'), 'daily');
    assert.equal(assigned.searchParams.get('warehouse_id'), '4');
    assert.equal(assigned.searchParams.get('material_code'), 'A&B');
    assert.equal(assigned.searchParams.get('embedded'), '1');
    assert(!assigned.searchParams.has('status') && !assigned.searchParams.has('page'));
    if (scenario === 'embedded_all_switch') {
        assert.equal(assigned.searchParams.get('date_scope'), 'all');
        assert(!assigned.searchParams.has('start_date') && !assigned.searchParams.has('end_date'));
    }
} else if (scenario === 'ledger_change') {
    const handlers = {};
    nodes.ledgerMaterialId = { value: '42' };
    nodes.material_code = { value: 'MV-A', addEventListener(name, fn) { handlers[name] = fn; } };
    ctx.reportType = 'ledger';
    vm.runInContext(slice("if (reportType === 'ledger') {\n    const linkedMaterialId", '\nrestoreReportFilters();'), ctx);
    handlers.input(); assert.equal(nodes.ledgerMaterialId.value, '');
    nodes.ledgerMaterialId.value = '42'; handlers.change(); assert.equal(nodes.ledgerMaterialId.value, '');
} else if (scenario === 'date_scope') {
    let changed = [];
    ctx.window.location = { search: '?warehouse_id=4&date_scope=all' };
    ctx.reportDateRange = () => ['2026-10-01', '2026-10-26'];
    ctx.setReportDate = (_, value) => changed.push(value);
    const initial = tpl.slice(tpl.indexOf("\nif (reportType === 'material_movement')", tpl.indexOf('\nrestoreReportFilters();')),
                              tpl.indexOf('\nloadData();', tpl.indexOf('\nrestoreReportFilters();')));
    vm.runInContext(initial, ctx); assert.equal(changed.length, 0);
    ctx.window.location.search = '?warehouse_id=4';
    vm.runInContext(initial, ctx); assert.deepEqual(changed, ['2026-10-01', '2026-10-26']);
} else throw new Error('Unknown scenario');
