const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'app/templates/print_routing.html'), 'utf8');
const start = source.indexOf('function loadKnownPrinters('), end = source.indexOf('function openAddPrinter(', start);
assert(start >= 0 && end > start);
const mode = process.argv[2];
const list = {children: [], innerHTML: '', appendChild(n) { this.children.push(n); }};
const hint = {textContent: ''}; const requests = [];
const names = mode === 'populated' ? ['QA 标签打印机', 'QA-printer-B'] : [];
const ctx = {FormData: class {}, document: {querySelector() { return null; }, getElementById(id) { return id === 'knownPrinterList' ? list : hint; }, createElement() { return {}; }}, fetch(url, options) {
    requests.push({url, method: options.method});
    if (mode === 'network') return Promise.reject(new Error('网络不可用'));
    return Promise.resolve({ok: mode !== 'http', status: mode === 'http' ? 503 : 200, json: async () => mode === 'business' ? {status: 'error', msg: '读取失败'} : {status: 'success', data: {workstation_id: 88, known_printers: names}}});
}};
ctx.window = ctx; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, 'app/static/js/api.js'), 'utf8'), ctx);
vm.runInContext(source.slice(start, end), ctx); ctx.loadKnownPrinters(88);
setImmediate(() => {
    assert.equal(requests.length, 1); assert.equal(requests[0].method, 'GET');
    assert.equal(requests[0].url, '/print_routing/workstations/88/printers/known');
    assert.deepStrictEqual(list.children.map(n => n.value), names);
    if (mode === 'populated') assert(hint.textContent.includes('下拉可选'));
    if (mode === 'empty') assert(hint.textContent.includes('暂未上报'));
    if (['network', 'http', 'business'].includes(mode)) assert(!hint.textContent.includes('正在读取'));
    console.log(JSON.stringify({passed: true, mode, options: list.children.map(n => n.value)}));
});
