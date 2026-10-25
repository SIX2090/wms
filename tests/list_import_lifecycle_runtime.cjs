'use strict';
// Execute actual template handlers and api.js with synthetic files and no network.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const p = JSON.parse(fs.readFileSync(0, 'utf8'));
const fnName = p.page === 'purchase_order' ? 'submitImportForm' : p.page === 'purchase_request' ? 'submitPurchaseRequestImport' : 'submitDocumentImport';
const fn = p.html.match(new RegExp('^(?:async )?function ' + fnName + '\\([^\\n]*\\) \\{[\\s\\S]*?^\\}', 'm'));
assert(fn, 'real import function must exist');
const inputTag = [...p.html.matchAll(/<input\b[^>]*>/g)].find(m => m[0].includes('onchange="' + fnName + '('))[0];
const inputId = inputTag.match(/id="([^"]+)"/)[1];
const formTag = p.html.slice(0, p.html.indexOf(inputTag)).match(/<form\b[^>]*>/g).at(-1);
const formId = formTag.match(/id="([^"]+)"/)[1];
const buttonTag = [...p.html.matchAll(/<button\b[^>]*>/g)].find(m => m[0].includes("getElementById('" + inputId + "').click()"))[0];
const buttonId = (buttonTag.match(/id="([^"]+)"/) || [])[1];
let mode = p.scenario, selected = {name: 'A.xlsx'}, reloads = 0, sessionPrompts = 0;
const fileA = selected, fileB = {name: 'B.xlsx'}, requests = [], messages = [], timers = [], alerts = [];
const input = {disabled: mode === 'original-disabled', files: [selected], get value() {return selected ? selected.name : '';}, set value(v) {if (v === '') {selected = null; this.files = [];}}};
const button = {disabled: mode === 'button-original-disabled'};
const form = {action: '/fixture/' + p.page + '/import'};
const document = {getElementById: id => id === inputId ? input : id === formId ? form : buttonId && id === buttonId ? button : null, querySelector: () => ({content: 'fixture-token'})};
class FD {constructor(value) {assert.equal(value, form); if (mode === 'formdata-error') throw Error('fixture FormData failed'); this.file = input.disabled ? undefined : input.files[0];} get(key) {assert.equal(key, 'file'); return this.file;}}
const ctx = {document, FormData: FD, console, showToast: (...args) => messages.push(args), alert: msg => alerts.push(msg), confirm: () => {sessionPrompts++; return false;}, location: {reload: () => reloads++}, setTimeout: (fn, ms) => timers.push({fn, ms}), fetch: (url, options) => {if (mode === 'fetch-error') throw Error('fixture fetch failed'); return new Promise((resolve, reject) => requests.push({url, options, resolve, reject}));}};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(p.api, ctx);
vm.runInContext(fn[0], ctx);
const submit = () => ctx[fnName](formId, inputId);
const flush = async () => {for (let n = 0; n < 6; n++) await new Promise(setImmediate);};
const choose = file => {selected = file; input.files = file ? [file] : [];};
async function settle(kind = 'success') {
 if (kind === 'network') requests.at(-1).reject(Error('fixture offline'));
 else {
  const status = kind === 'http' ? 400 : kind === 'html' ? 502 : ['401', '419'].includes(kind) ? Number(kind) : 200;
  requests.at(-1).resolve({ok: status === 200, status, json: async () => {if (kind === 'html') throw SyntaxError('fixture HTML'); return kind === 'null' ? null : {status: kind === 'business' ? 'error' : 'success', msg: 'fixture server message'};}});
 }
 await flush();
}
function payload() {
 const req = requests.at(-1);
 assert.equal(req.url, p.page === 'purchase_order' ? '/purchase_order/import' : p.page === 'purchase_request' ? '/purchase_request/import' : form.action);
 assert.equal(req.options.method, 'POST'); assert.equal(req.options.credentials, 'same-origin');
 assert.equal(req.options.headers['X-CSRFToken'], 'fixture-token');
 assert.equal(req.options.headers['X-Requested-With'], 'XMLHttpRequest');
 assert.equal(req.options.headers['Content-Type'], undefined);
 assert(req.options.body instanceof FD); assert.equal(req.options.body.file, fileA, 'capture selected file before disabling');
}
(async () => {
 if (mode === 'empty' || mode === 'cancel-selection') {choose(null); await submit(); assert.equal(requests.length, 0); assert.equal(input.disabled, false); assert.equal(button.disabled, false); assert.equal(messages.length, 0); return;}
 if (mode === 'missing-input') {document.getElementById = id => id === inputId ? null : form; await submit(); assert.equal(requests.length, 0); return;}
 const first = submit();
 await flush();
 if (mode === 'formdata-error' || mode === 'fetch-error') {
  await first; assert.equal(requests.length, 0); assert.equal(input.disabled, false); assert.equal(button.disabled, false); assert.equal(messages.at(-1)[1], 'danger');
  assert(messages.at(-1)[0].includes(mode === 'formdata-error' ? 'FormData failed' : 'fetch failed'));
  mode = 'success'; choose(fileA); const retry = submit(); await flush(); assert.equal(requests.length, 1); payload(); await settle(); await retry; return;
 }
 assert.equal(requests.length, 1);
 if (mode !== 'original-disabled') payload();
 assert.equal(input.disabled, true, 'file input must lock during request');
 assert.equal(button.disabled, true, 'visible import button must lock during request');
 if (mode === 'stale-selection' || mode === 'failure-new-selection') choose(fileB);
 const second = submit(); await flush(); assert.equal(requests.length, 1, 'reentrant handler must not dispatch twice'); await second;
 const kind = mode.startsWith('failure-') && mode !== 'failure-new-selection' ? mode.slice(8) : ['original-disabled', 'button-original-disabled', 'failure-new-selection'].includes(mode) ? 'business' : 'success';
 await settle(kind); await first;
 if (kind !== 'success') {
  assert.equal(input.disabled, mode === 'original-disabled'); assert.equal(button.disabled, mode === 'button-original-disabled');
  assert.equal(messages.at(-1)[1], 'danger'); assert.equal(alerts.length, 0); assert(!timers.some(t => t.ms === 900));
  assert.equal(input.files[0], mode === 'failure-new-selection' ? fileB : undefined, 'old finally cannot clear newer file');
  if (['business', 'http'].includes(kind)) assert(messages.at(-1)[0].includes('fixture server message'));
  if (['401', '419'].includes(kind)) assert.equal(sessionPrompts, 1);
  input.disabled = false; button.disabled = false; choose(fileA); mode = 'success'; const retry = submit(); await flush(); assert.equal(requests.length, 2, 'manual retry must be available'); payload(); await settle(); await retry; return;
 }
 assert.equal(input.files[0], mode === 'stale-selection' ? fileB : undefined, 'old finally cannot clear newer file');
 assert.equal(input.disabled, true); assert.equal(button.disabled, true);
 assert.equal(reloads, 0); assert.equal(timers.filter(t => t.ms === 900).length, 1);
 if (p.page.startsWith('subcontract')) {assert.deepEqual(alerts, ['fixture server message']); assert.equal(messages.length, 0);} else {assert.equal(alerts.length, 0); assert.equal(messages.at(-1)[0], 'fixture server message'); assert.equal(messages.at(-1)[1], 'success');}
 choose(fileB); await submit(); assert.equal(requests.length, 1, 'success refresh window must remain locked');
 timers.find(t => t.ms === 900).fn(); assert.equal(reloads, 1);
})().catch(error => {process.stderr.write(error.stack); process.exitCode = 1;});
