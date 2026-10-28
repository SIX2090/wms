const fs = require('fs'), vm = require('vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[2] + '/app/templates/report_view.html', 'utf8');
const scenario = process.argv[3];
const handlers = {}, summary = { focused: false, focus() { this.focused = true; } };
const menu = { open: true, contains(target) { return target.inside; },
  querySelector() { return summary; }, addEventListener(event, handler) { handlers[event] = handler; } };
const warehouse = { value: '5' }, status = { textContent: '' };
const error = { textContent: '', classList: { remove() {} } };
let opens = [];
const context = { URLSearchParams, printTemplatesReady: true,
  printableTemplateIds: new Set(['', '7']), templateSelect: { value: '7' }, reportType: 'warehouse_monthly',
  filterForm: { querySelector() { return warehouse; } },
  buildParams() { return new URLSearchParams('warehouse_id=5&start_month=2026-10'); },
  window: { open(...args) { opens.push(args); } },
  document: { getElementById(id) { return id === 'reportPrintMenu' ? menu : id === 'truncationAlert' ? error : status; },
    addEventListener(event, handler) { handlers['document:' + event] = handler; } },
  printBtn: { addEventListener(event, handler) { handlers.standard = handler; } },
  setLoading() {}, renderTruncation() {}, currentColumns: [],
  captureReportPrintContext() { return { params: new URLSearchParams('warehouse_id=5') }; },
  fetch: async () => { throw new Error('isolated network failure'); }
};
vm.createContext(context);
const first = source.indexOf('function openReportTemplateOutput(mode)');
const last = source.indexOf('\ntemplatePreviewBtn.addEventListener', first);
const key = source.indexOf("document.getElementById('reportPrintMenu').addEventListener('keydown'");
const keyEnd = source.indexOf('\nloadPrintTemplates();', key);
const standard = source.indexOf('const MAX_PRINT_ROWS = 10000;');
const standardEnd = source.indexOf('\nfunction captureReportPrintContext(', standard);
assert(first >= 0 && last > first && key >= 0 && keyEnd > key && standardEnd > standard);
vm.runInContext(source.slice(first, last) + '\n' + source.slice(key, keyEnd) + '\n' + source.slice(standard, standardEnd), context);
(async () => {
  if (['outside', 'inside', 'management'].includes(scenario)) {
    const target = { inside: scenario !== 'outside', closest() { return scenario === 'management' ? {} : null; } };
    assert.equal(typeof handlers['document:click'], 'function');
    handlers['document:click']({ target });
    assert.equal(menu.open, scenario === 'inside');
  } else if (scenario === 'escape') {
    handlers.keydown({ key: 'Escape', currentTarget: menu });
    assert.equal(menu.open, false); assert.equal(summary.focused, true);
  } else if (scenario === 'standard') {
    await handlers.standard(); assert.equal(menu.open, false);
    assert.match(error.textContent, /isolated network failure/);
  } else {
    if (scenario === 'missing') warehouse.value = '';
    if (scenario === 'invalid') context.templateSelect.value = '999';
    context.openReportTemplateOutput(scenario === 'download' ? 'download' : 'preview');
    if (['missing', 'invalid'].includes(scenario)) {
      assert.equal(opens.length, 0); assert.equal(menu.open, true); assert.ok(status.textContent);
    } else {
      assert.equal(menu.open, false); assert.equal(opens.length, 1);
      assert.match(opens[0][0], scenario === 'download' ? /print_excel/ : /print_preview/);
      assert.match(opens[0][0], /warehouse_id=5/);
    }
  }
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
