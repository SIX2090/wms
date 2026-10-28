const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html = fs.readFileSync(process.argv[2] + '/app/templates/print_station.html', 'utf8');
const code = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const scenario = process.argv[3];
const nodes = new Map();
function node(id) {
    if (!nodes.has(id)) nodes.set(id, {id, hidden: true, disabled: false, textContent: '', handlers: {},
        addEventListener(event, fn) { this.handlers[event] = fn; },
        click() { if (!this.disabled && this.handlers.click) this.handlers.click(); }});
    return nodes.get(id);
}
let timers = new Map(), timerId = 0, polls = 0, printCalls = 0, rejectPost = false;
const posts = [], events = new Map();
const frame = node('printFrame');
frame.contentWindow = {document: {}, focus() {}, print() {printCalls++;},
    addEventListener(event, fn) {events.set(event, fn);},
    removeEventListener(event, fn) {if (events.get(event) === fn) events.delete(event);}};
function $(selector) {
    const e = typeof selector === 'string' ? node(selector.replace(/^#/, '')) : selector;
    const wrapper = {0:e, text(value) {e.textContent = String(value); return wrapper;},
        html(value) {e.innerHTML = value; return wrapper;}, append() {return wrapper;},
        empty() {return wrapper;}, scrollTop() {return wrapper;},
        removeClass() {return wrapper;}, addClass() {return wrapper;},
        off() {delete e.load; return wrapper;}, on(event, fn) {e.load = fn; return wrapper;},
        attr(name, value) {e[name] = value; return wrapper;}};
    return wrapper;
}
$.ajaxSetup = () => {};
const job = {id: 7, job_type: 'in_order', copies: scenario === 'two-copies' ? 2 : 1,
    print_url: '/in_order/3/print', lease_token: 'test-lease'};
$.getJSON = url => {
    const result = url.endsWith('/stats') ? {status:'success',stats:{pending:0,printing:1,done:0,failed:0}}
        : (++polls === 1 ? {status:'success',job} : {status:'empty'});
    const chain = {done(fn) {fn(result); return chain;}, fail() {return chain;},
        always(fn) {fn(); return chain;}};
    return chain;
};
const ctx = {$, Date, Promise, Error, document: {getElementById: node,
    querySelector: () => ({content:'test-csrf'})}, WMS:{api:{post(url, body) {
        posts.push({url,body});
        return rejectPost ? Promise.reject(new Error('打印队列忙，请稍后重试')) : Promise.resolve({status:'success'});
    }}}, setTimeout(fn, delay) {const id = ++timerId; timers.set(id, {fn,delay}); return id;},
    clearTimeout(id) {timers.delete(id);}};
ctx.window = ctx;
vm.runInNewContext(code, ctx);
function timer(delay) {
    const found = [...timers].find(([,v]) => v.delay === delay);
    assert(found, 'expected timer ' + delay); timers.delete(found[0]); found[1].fn();
}
function afterPrint() {const fn = events.get('afterprint'); if (fn) fn();}
const flush = () => new Promise(resolve => setImmediate(resolve));
async function run() {
    timer(500); frame.load.call(frame);
    assert.equal(printCalls, 1);
    if (scenario === 'timeout') timer(8000); else afterPrint();
    if (scenario === 'closed' || scenario === 'timeout') {
        // Closing/cancelling and the fallback timer cannot prove paper output.
        for (const [id,t] of [...timers]) if (t.delay === 300) {timers.delete(id);t.fn();}
        assert.equal(posts.length, 0, 'dialog closure or timeout must not complete the job');
        assert.equal(node('printResultPanel').hidden, false);
        return;
    }
    if (scenario === 'cancel') {
        node('notPrintedBtn').click(); await flush();
        assert.deepEqual(posts.map(p=>p.url), ['/print_queue/jobs/7/fail']);
        assert.equal(posts[0].body.lease_token, 'test-lease');
        assert.equal(node('printResultPanel').hidden, true);
        return;
    }
    if (scenario === 'two-copies') {
        assert.equal(printCalls, 1); assert.equal(posts.length, 0);
        node('confirmPrintedBtn').click(); await flush();
        assert.equal(printCalls, 2); assert.equal(posts.length, 0);
        afterPrint(); node('confirmPrintedBtn').click(); await flush();
        assert.deepEqual(posts.map(p=>p.url), ['/print_queue/jobs/7/complete']);
        return;
    }
    if (scenario === 'report-retry') {
        rejectPost = true; node('confirmPrintedBtn').click(); await flush();
        assert.equal(node('printResultPanel').hidden, false, 'failed report must retain the current job');
        assert.equal(node('confirmPrintedBtn').disabled, true, 'retry is rate limited');
        const before = polls; timer(3000); assert.equal(polls, before, 'must not claim another job');
        // The retry delay is a separate timer from polling.
        for (const [id,t] of [...timers]) if (t.delay === 3000) {timers.delete(id); t.fn();}
        rejectPost = false; node('confirmPrintedBtn').click(); await flush();
        assert.equal(posts.length, 2);
        assert(posts.every(p=>p.body.lease_token === 'test-lease'));
        assert.equal(node('printResultPanel').hidden, true);
        return;
    }
    assert.equal(scenario, 'confirmed');
    afterPrint(); node('confirmPrintedBtn').click(); node('confirmPrintedBtn').click(); await flush();
    assert.deepEqual(posts.map(p=>p.url), ['/print_queue/jobs/7/complete']);
    assert.equal(posts[0].body.lease_token, 'test-lease');
}
run().catch(error => {process.stderr.write(error.stack); process.exitCode=1;});
