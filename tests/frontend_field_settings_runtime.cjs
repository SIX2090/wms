'use strict';
// Minimal DOM adapter; every column controller, dialog handler and report renderer
// under test is loaded verbatim from the production files.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = process.argv[2];
const scenario = process.argv[3];
const app = fs.readFileSync(root + '/app/static/js/app.js', 'utf8');
const report = fs.readFileSync(root + '/app/templates/report_view.html', 'utf8');
const common = app.slice(app.indexOf('// Unified document-grid field settings,'), app.indexOf('// Global fill-down controls'));
const dynamicSource = app.slice(app.indexOf('function setupDynamicDetailColumnControls('), app.indexOf('function autoSetupResizableTables('));
function fn(text, name) {
    const start = text.indexOf('function ' + name + '(');
    assert(start >= 0, name);
    return text.slice(start, text.indexOf('\n}', start) + 2);
}
const helpers = ['escapeHtml', 'rememberWmsColumnDefaults'].filter(name => app.includes('function ' + name + '(')).map(name => fn(app, name)).join('\n');
const clean = value => JSON.parse(JSON.stringify(value));

function fixture(options = {}) {
    const store = options.store || new Map();
    const writes = [], listeners = {}, observers = [];
    let host;
    const keys = options.keys || ['quantity', 'memo', 'price'];
    let document;
    class Element {
        constructor(tag) {
            this.tagName = tag.toUpperCase(); this.nodeType = 1;
            this.children = []; this.childNodes = []; this.parentElement = null;
            this.dataset = {}; this.attrs = {}; this.handlers = {}; this.style = {};
            this.hidden = false; this.value = ''; this.disabled = false; this.tabIndex = 0; this.isConnected = true;
            this.classes = new Set();
            this.classList = {contains: key => this.classes.has(key), add: key => this.classes.add(key), remove: key => this.classes.delete(key), toggle: (key, value) => value ? this.classes.add(key) : this.classes.delete(key)};
        }
        get cells() { return this.children; }
        get firstElementChild() { return this.children[0] || null; }
        appendChild(node) {
            if (node.fragment) { [...node.children].forEach(child => this.appendChild(child)); return node; }
            if (node.parentElement) {
                const index = node.parentElement.children.indexOf(node);
                if (index >= 0) node.parentElement.children.splice(index, 1);
            }
            this.children.push(node); node.parentElement = this; return node;
        }
        set innerHTML(html) {
            this.children = []; this.childNodes = [];
            if (this.tagName === 'TH') this.childNodes = [{nodeType: 3, textContent: html.split('<')[0]}];
            if (this.tagName === 'TBODY') {
                for (const rowMatch of html.matchAll(/<tr>([\s\S]*?)<\/tr>/g)) {
                    const row = new Element('tr');
                    for (const cellMatch of rowMatch[1].matchAll(/<td data-column-key="([^"]+)">([\s\S]*?)<\/td>/g)) row.appendChild(cell(cellMatch[1], cellMatch[2]));
                    this.appendChild(row);
                }
            }
        }
        addEventListener(type, handler) { (this.handlers[type] ||= []).push(handler); }
        setAttribute(key, value) { this.attrs[key] = value; }
        getAttribute(key) { return this.attrs[key]; }
        getClientRects() { return this.hidden ? [] : [{}]; }
        focus() { document.activeElement = this; (this.handlers.focusin || []).forEach(handler => handler({target: this})); }
        click() { (this.handlers.click || []).forEach(handler => handler({target: this})); }
        closest() { return null; }
        contains(node) { return this === node || this.children.some(child => child.contains && child.contains(node)); }
        matches(selector) { return selector === 'tr' && this.tagName === 'TR'; }
        scrollIntoView() {}
    }
    function cell(key, text = key) {
        const result = new Element('th'); result.dataset.columnKey = key;
        result.childNodes = [{nodeType: 3, textContent: text}]; return result;
    }
    const header = new Element('tr'), body = new Element('tbody'), table = new Element('table');
    keys.forEach(key => header.appendChild(cell(key)));
    function addRow(rowKeys = keys) { const row = new Element('tr'); rowKeys.forEach(key => row.appendChild(cell(key))); body.appendChild(row); return row; }
    addRow();
    table.id = options.report ? 'reportTable' : 'details'; table.tHead = {rows: [header]}; table.tBodies = [body];
    Object.defineProperty(table, 'rows', {get: () => [header, ...body.children]});
    table.querySelector = selector => selector === 'thead tr' ? header : selector === 'tbody' ? body : selector.startsWith('thead th[') ? header.children.find(item => item.dataset.columnKey === selector.match(/="([^"]+)"/)[1]) : null;
    table.querySelectorAll = selector => selector === 'thead th[data-column-key]' ? header.children : selector === 'tbody tr, tfoot tr' ? body.children : selector.startsWith('[data-column-key=') ? table.rows.flatMap(row => row.children).filter(item => item.dataset.columnKey === selector.match(/="([^"]+)"/)[1]) : [];
    const controls = {}, closeButtons = [new Element('button'), new Element('button')];
    for (const key of ['search', 'ok', 'reset', 'locate']) controls[key] = new Element(key === 'search' ? 'input' : 'button');
    controls.moveBox = new Element('div');
    const moves = ['top', 'up', 'down', 'bottom'].map(direction => { const button = new Element('button'); button.dataset.fsMove = direction; return button; });
    const tabs = ['header', 'detail', 'footer'].map(name => { const tab = new Element('button'); tab.dataset.fsTab = name; return tab; });
    const panels = ['header', 'detail', 'footer'].map(name => { const panel = new Element('div'); panel.dataset.fsPanel = name; return panel; });
    const settingsBody = new Element('tbody'); settingsBody.querySelectorAll = () => settingsBody.children;
    function settingsRow() {
        const row = new Element('tr'), text = new Element('input'), checkbox = new Element('input');
        Object.defineProperty(row, 'innerHTML', {set() { row.children = Array.from({length: 4}, () => new Element('td')); }});
        row.querySelector = selector => selector.includes('checkbox') ? checkbox : text;
        return row;
    }
    function makeHost() {
        const result = new Element('div');
        result.querySelector = selector => selector === '[data-fs-body]' ? settingsBody : selector === '[data-fs-tab="detail"]' ? tabs[1] : selector === '.wms-field-settings__move' ? controls.moveBox : selector.startsWith('[data-fs-body] tr[data-key=') ? settingsBody.children.find(row => row.dataset.key === selector.match(/="([^"]+)"/)[1]) : selector.includes('tr.selected') ? settingsBody.children.find(row => row.classes.has('selected')) : controls[(selector.match(/^\[data-fs-(.+)\]$/) || [])[1]];
        result.querySelectorAll = selector => selector === '[data-fs-close]' ? closeButtons : selector === '[data-fs-tab]' ? tabs : selector === '[data-fs-panel]' ? panels : selector === '[data-fs-move]' ? moves : [];
        return result;
    }
    document = {
        body: new Element('body'), activeElement: null,
        querySelectorAll: selector => selector === 'table' ? [table] : [],
        getElementById: id => id === 'wms-detail-column-style' ? {} : id === 'reportTable' ? table : host || null,
        createElement: tag => tag === 'tr' ? settingsRow() : tag === 'th' ? new Element('th') : (host = makeHost()),
        createDocumentFragment: () => Object.assign(new Element('fragment'), {fragment: true}),
        createTextNode: text => ({nodeType: 3, textContent: text}),
        addEventListener: (type, handler) => (listeners[type] ||= []).push(handler)
    };
    const ctx = {
        document, location: {pathname: '/isolated'}, CSS: {escape: value => value}, Node: {ELEMENT_NODE: 1}, console,
        localStorage: {
            getItem: key => store.has(key) ? store.get(key) : null,
            setItem(key, value) { writes.push({op: 'set', key, value}); store.set(key, value); },
            removeItem(key) { writes.push({op: 'remove', key}); store.delete(key); }
        },
        MutationObserver: class { constructor(handler) { this.handler = handler; } observe(target) { observers.push({handler: this.handler, target}); } }
    };
    ctx.window = ctx; vm.createContext(ctx); vm.runInContext(helpers + '\n' + dynamicSource + '\n' + common, ctx);
    const fieldKey = 'wms:field-settings:v3:/isolated:' + table.id;
    const scope = {querySelectorAll: () => [table]}, button = new Element('button');
    button.closest = selector => selector === '.modal.show' ? null : scope;
    const initialize = () => (listeners.DOMContentLoaded || []).forEach(handler => handler());
    const order = () => header.children.map(item => item.dataset.columnKey);
    const bodyOrder = () => body.children[0].children.map(item => item.dataset.columnKey);
    const labels = () => Object.fromEntries(header.children.map(item => [item.dataset.columnKey, item.childNodes[0]?.textContent]));
    const open = () => ctx.WmsFieldSettings.open(button);
    const reset = () => controls.reset.click();
    const ok = () => controls.ok.click();
    const cancel = type => type === 'escape' ? (listeners.keydown || []).forEach(handler => handler({key: 'Escape', preventDefault() {}, stopImmediatePropagation() {}})) : type === 'backdrop' ? host.handlers.click.forEach(handler => handler({target: host})) : closeButtons[1].click();
    const rowOf = key => settingsBody.children.find(row => row.dataset.key === key);
    function rename(key, value) { const input = rowOf(key).querySelector('input[type=text]'); input.value = value; input.handlers.input.forEach(handler => handler.call(input)); }
    function move(key, direction) { rowOf(key).click(); moves.find(button => button.dataset.fsMove === direction).click(); }
    const dynamic = () => ctx.setupDynamicDetailColumnControls({tableSelector: table, orderKey: 'own-order', widthKey: 'own-width', lockedColumns: options.locked || []});
    function flush(added = []) { for (const observer of observers) observer.handler([{type: 'childList', addedNodes: added}]); }
    return {ctx, store, writes, table, header, body, controls, fieldKey, initialize, order, bodyOrder, labels, open, reset, ok, cancel, rename, move, dynamic, flush, addRow, cell, rowOf};
}

function run() {
    const defaults = ['quantity', 'memo', 'price'];
    const sharedOrder = ['memo', 'price', 'quantity'];
    const ownOrder = ['price', 'quantity', 'memo'];
    const initial = {order: sharedOrder, hidden: ['memo'], labels: {memo: 'custom-memo'}};
    const widthBytes = '{"quantity":125,"memo":222,"price":88}';
    const f = fixture();
    f.store.set(f.fieldKey, JSON.stringify(initial));
    if (scenario.startsWith('plain-')) {
        f.initialize(); f.open();
        if (scenario === 'plain-move-ok') { f.move('quantity', 'top'); f.ok(); assert.deepEqual(f.order(), defaults); return; }
        if (scenario === 'plain-edit-cancel') { f.rename('memo', 'edited'); f.cancel('button'); assert.deepEqual(f.labels().memo, 'custom-memo'); return; }
        const before = f.store.get(f.fieldKey); f.reset();
        assert.equal(f.store.get(f.fieldKey), before, 'reset is draft-only');
        assert.deepEqual(f.order(), sharedOrder, 'reset cannot apply before OK');
        if (scenario.endsWith('-ok')) { f.ok(); f.flush(); assert.deepEqual(f.order(), defaults); assert.deepEqual(f.bodyOrder(), defaults); assert.equal(f.labels().memo, 'memo'); f.open(); f.reset(); f.ok(); assert.deepEqual(f.order(), defaults); }
        else { f.cancel(scenario.split('-').at(-1)); f.flush(); assert.equal(f.store.get(f.fieldKey), before); assert.deepEqual(f.order(), sharedOrder); assert.equal(f.labels().memo, 'custom-memo'); f.open(); f.ok(); assert.equal(f.store.get(f.fieldKey), before); }
        return;
    }
    if (scenario.startsWith('dynamic-')) {
        const commonFirst = scenario.includes('common-first');
        const hasOwn = scenario.includes('-own-');
        const malformed = scenario.includes('-malformed-');
        f.store.set('own-width', widthBytes);
        if (hasOwn) f.store.set('own-order', JSON.stringify(ownOrder));
        if (malformed) f.store.set('own-order', '{broken-json');
        let controller;
        if (commonFirst) { f.initialize(); controller = f.dynamic(); }
        else { controller = f.dynamic(); f.initialize(); }
        assert.deepEqual(f.order(), hasOwn ? ownOrder : sharedOrder, 'initial ordering honors own key or shared fallback in either startup order');
        const initialBytes = f.store.get(f.fieldKey), ownBytes = f.store.get('own-order');
        if (scenario.includes('-native-')) {
            controller.reset(); assert.deepEqual(f.order(), defaults); assert.equal(f.store.has('own-width'), false);
            const reload = fixture({store: f.store}); reload.dynamic(); reload.initialize(); assert.deepEqual(reload.order(), defaults, 'native reset survives reload despite retained common preference'); assert.equal(reload.store.has('own-width'), false); return;
        }
        if (scenario.includes('-drag-name-')) {
            controller.setOrder(ownOrder); f.open(); f.rename('memo', 'renamed-after-drag'); const count = f.writes.length; f.ok();
            assert.deepEqual(f.order(), ownOrder); assert.equal(f.labels().memo, 'renamed-after-drag'); assert(f.writes.slice(count).every(write => write.key !== 'own-order'), 'name-only OK cannot persist a stale order'); assert.equal(f.store.get('own-width'), widthBytes); return;
        }
        f.open();
        if (scenario.includes('-move-')) { f.move('quantity', 'top'); f.move('price', 'bottom'); } else f.reset();
        if (scenario.includes('-cancel-')) { f.cancel('button'); assert.equal(f.store.get(f.fieldKey), initialBytes); assert.equal(f.store.get('own-order'), ownBytes); }
        else { f.ok(); assert.deepEqual(f.order(), defaults); assert.deepEqual(f.bodyOrder(), defaults); assert.deepEqual(JSON.parse(f.store.get('own-order')), defaults); f.flush(); controller.applyOrder(); assert.deepEqual(f.order(), defaults); const reload = fixture({store: f.store}); reload.dynamic(); reload.initialize(); assert.deepEqual(reload.order(), defaults); }
        assert.equal(f.store.get('own-width'), widthBytes);
        assert.equal(f.header.children.find(item => item.dataset.columnKey === 'quantity').style.width, '125px');
        return;
    }
    if (scenario.startsWith('report-')) {
        const g = fixture({report: true, keys: []});
        Object.assign(g.ctx, {tableHeaderRow: g.header, tableBody: g.body, currentColumns: [], currentRows: [], currentSortField: '', currentSortOrder: 'asc', reportType: 'ledger', STATUS_LABELS: {}, STATUS_BADGES: {}, loadData() {}});
        const code = ['formatValue', 'renderTable', 'bindReportDocLinks', 'applyReportFieldSettings', '_defaultLedgerColumns'].map(name => fn(report, name)).join('\n');
        vm.runInContext(code, g.ctx);
        const columns = clean(g.ctx._defaultLedgerColumns()), originalOrder = columns.map(column => column.field);
        g.store.set(g.fieldKey, JSON.stringify({order: [...originalOrder].reverse(), hidden: ['remark'], labels: {remark: 'custom-remark'}}));
        const rows = scenario.includes('-empty-') ? [] : [Object.fromEntries(columns.map(column => [column.field, column.type === 'number' ? 3 : column.field]))];
        if (scenario.includes('-common-first-')) g.initialize();
        g.ctx.renderTable(columns, rows);
        if (!scenario.includes('-common-first-')) g.initialize();
        if (scenario.includes('-new-column-')) { columns.push({field: 'new_column', title: 'new-column-label'}); g.ctx.renderTable(columns, rows); }
        g.open(); g.reset(); g.ok();
        assert.deepEqual(g.order(), columns.map(column => column.field));
        assert.equal(g.labels().remark.trim(), columns.find(column => column.field === 'remark').title);
        if (scenario.includes('-new-column-')) assert.equal(g.labels().new_column.trim(), 'new-column-label');
        g.ctx.renderTable(columns, rows); g.flush(); assert.deepEqual(g.order(), columns.map(column => column.field));
        return;
    }
    if (scenario === 'new-column-observer') {
        f.initialize(); f.open(); f.reset(); f.ok();
        f.header.appendChild(f.cell('new_column', 'new-column-label'));
        const added = f.addRow([...defaults, 'new_column']); f.flush([added]);
        f.open(); f.reset(); f.ok(); f.flush(); assert.deepEqual(f.order(), [...defaults, 'new_column']); assert.equal(f.labels().new_column, 'new-column-label'); return;
    }
    throw Error('Unknown scenario ' + scenario);
}
run();
