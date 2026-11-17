'use strict';
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const root = path.resolve(process.argv[3] || path.join(__dirname, '..'));
const source = fs.readFileSync(path.join(root, 'app/templates/mobile_scan.html'), 'utf8');
const scenario = process.argv[2];
function extract(name) {
    const start = source.indexOf('    function ' + name + '(');
    const end = source.indexOf('\n    }', start) + '\n    }'.length;
    assert(start >= 0 && end > start, name);
    return source.slice(start, end);
}
function classes(hidden = false) {
    const values = new Set(hidden ? ['d-none'] : []);
    return {add: name => values.add(name), remove: name => values.delete(name), contains: name => values.has(name)};
}
const requests = [];
const selection = {value: '1', disabled: false, innerHTML: '', appendChild() {}};
const context = {
    mode: 'check', checkOrderSelect: selection, warehouseInput: {value: '合成甲仓'},
    checkProgressBox: {classList: classes()}, checkProgressText: {textContent: '旧仓库进度'},
    checkItemsList: {innerHTML: '旧仓库物料', classList: classes()},
    checkOrderTip: {textContent: '该仓库暂无进行中的盘点单', classList: classes(true)},
    checkOrdersRetry: {classList: classes(true)}, checkProgressVersion: 0,
    lastCheckWh: null, checkOrdersVersion: 0, CHECK_LIST_MAX: 30,
    document: {createElement: () => ({})},
    WMS: {api: {getRaw(url) {return new Promise((resolve, reject) => requests.push({url, resolve, reject}));}}}
};
vm.createContext(context);
const shared = fs.readFileSync(path.join(root, 'app/static/js/app.js'), 'utf8');
const escapeStart = shared.indexOf('function escapeHtml(');
const escapeEnd = shared.indexOf('\n}', escapeStart) + '\n}'.length;
assert(escapeStart >= 0 && escapeEnd > escapeStart);
vm.runInContext(shared.slice(escapeStart, escapeEnd), context);
vm.runInContext(extract('renderCheckItems') + '\n' + extract('refreshCheckProgress') + '\n' + extract('loadCheckOrders'), context);
const settle = () => new Promise(resolve => setImmediate(resolve));
const reply = {data: {total: 2, counted: 1, items: [{code: 'OLD', name: '旧仓物料', counted: false}]}};
(async () => {
    if (scenario === 'warehouse') {
        context.refreshCheckProgress();
        context.warehouseInput.value = '合成乙仓';
        selection.value = '';
        context.loadCheckOrders('合成乙仓');
        assert(context.checkProgressBox.classList.contains('d-none'), 'Switching warehouses must hide previous check progress immediately');
        requests[0].resolve(reply);
        await settle();
        assert(context.checkProgressBox.classList.contains('d-none'), 'Old warehouse response must not reopen progress');
    } else if (scenario === 'clear') {
        context.refreshCheckProgress();
        selection.value = '';
        context.refreshCheckProgress();
        requests[0].resolve({data: {total: 2, counted: 1, items: []}});
        await settle();
        assert(context.checkProgressBox.classList.contains('d-none'), 'Cleared check must stay hidden after an old response');
    } else if (scenario === 'selection') {
        context.refreshCheckProgress();
        selection.value = '2';
        context.refreshCheckProgress();
        requests[1].resolve({data: {total: 3, counted: 2, items: []}});
        await settle();
        requests[0].resolve(reply);
        await settle();
        assert.equal(context.checkProgressText.textContent, '已盘 2 / 共 3', 'Late old selection must not replace current progress');
    } else if (scenario === 'retry_empty') {
        selection.value = '';
        context.loadCheckOrders('合成甲仓');
        requests[0].reject(new Error('isolated network failure'));
        await settle();
        assert(context.checkOrderTip.textContent.includes('加载失败'));
        context.loadCheckOrders('合成甲仓');
        requests[1].resolve({data: {orders: []}});
        await settle();
        assert(context.checkOrderTip.textContent.includes('暂无进行中'), 'Successful empty retry must replace the earlier failure message');
        assert(!context.checkOrderTip.textContent.includes('加载失败'));
    } else if (scenario === 'empty_success') {
        context.refreshCheckProgress();
        requests[0].resolve({data: {total: 0, counted: 0, items: []}});
        await settle();
        assert(!context.checkProgressBox.classList.contains('d-none'));
        assert.equal(context.checkProgressText.textContent, '已盘 0 / 共 0');
    } else if (scenario === 'success') {
        context.refreshCheckProgress();
        requests[0].resolve(reply);
        await settle();
        assert(!context.checkProgressBox.classList.contains('d-none'));
        assert.equal(context.checkProgressText.textContent, '已盘 1 / 共 2');
        assert(context.checkItemsList.innerHTML.includes('OLD'));
    } else if (scenario === 'escape') {
        context.renderCheckItems([{code: '<img src=x onerror=attack()>', name: 'A&B', counted: false}]);
        assert(context.checkItemsList.innerHTML.includes('&lt;img src=x onerror=attack()&gt;'));
        assert(context.checkItemsList.innerHTML.includes('A&amp;B'));
        assert(!context.checkItemsList.innerHTML.includes('<img'));
    } else throw new Error('Unknown scenario: ' + scenario);
})().catch(error => {process.stderr.write(error.stack + '\n'); process.exitCode = 1;});
