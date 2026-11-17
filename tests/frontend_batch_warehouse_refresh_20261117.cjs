const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('assert');
for (const name of ['in_order_add.html', 'out_order_add.html']) {
    const source = fs.readFileSync(path.join(__dirname, '../app/templates', name), 'utf8');
    const start = source.indexOf('function applyBatchUpdate()');
    const end = Math.min(...[source.indexOf('\nfunction ', start + 1), source.indexOf('</script>', start)].filter(n => n >= 0));
    const select = {value: '1', dispatchEvent(event) { assert.equal(event.type, 'change'); assert.equal(this.value, '2'); this.refreshed = true; }};
    const nodes = {batchUpdateField: {value: 'warehouse'}, batchUpdateValue: {value: ''}, batchUpdateWarehouse: {value: '2'}, batchUpdateModal: {remove() {}}};
    const context = {document: {getElementById: id => nodes[id], querySelector: selector => selector.includes('warehouse_id') ? select : null, querySelectorAll: () => []}, showToast() {}, Event: class {constructor(type, options) {this.type = type; this.bubbles = options.bubbles;}}};
    vm.createContext(context);
    vm.runInContext(source.slice(start, end), context);
    vm.runInContext('applyBatchUpdate()', context);
    assert.equal(select.refreshed, true, name + ': switching the header warehouse must refresh dependent stock');
}
