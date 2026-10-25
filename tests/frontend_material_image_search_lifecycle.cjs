const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const root = process.argv[2] || path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'app/templates/material.html'), 'utf8');
let start = html.indexOf('    var materialImageRequestGeneration = 0;');
if (start < 0) start = html.indexOf('    window.findMaterialImage = function(id) {');
const end = html.indexOf('    // 修复空分类/单位', start);
assert(start >= 0 && end > start);
const source = html.slice(start, end);
function fixture() {
    const nodes = new Map(), calls = [], pending = [], notices = [], timers = [];
    class Element {
        constructor(tag='div') { this.tagName=tag; this.children=[]; this.listeners={}; this.dataset={}; this.parent=null; this.connected=true; this.textContent=''; this.className=''; this.disabled=false; }
        get isConnected() { return this.connected && (!this.parent || this.parent.isConnected); }
        addEventListener(type, fn) { (this.listeners[type] ||= []).push(fn); }
        dispatch(type) { for (const fn of this.listeners[type] || []) fn.call(this, {type,target:this}); }
        appendChild(child) { child.parent=this; this.children.push(child); return child; }
        set innerHTML(value) { this.html=value; for(const c of this.children) c.connected=false; this.children=[]; }
        get innerHTML() { return this.html || ''; }
    }
    for (const id of ['materialImageModal','materialImageStatus','materialImageGrid','materialImageQuery']) nodes.set(id,new Element());
    const document={getElementById(id){return nodes.get(id)||null;},createElement(tag){return new Element(tag);},querySelector(sel){return sel.includes('csrf-token')?{content:'test-csrf'}:null;}};
    const modal={visible:false,hides:0,show(){this.visible=true;},hide(){nodes.get('materialImageModal').dispatch('hide.bs.modal');this.visible=false;this.hides++;nodes.get('materialImageModal').dispatch('hidden.bs.modal');}};
    let reloads=0, confirms=0;
    const ctx={document,FormData:class{},Promise,Error,JSON,console,setTimeout(fn){timers.push(fn);},showToast(...args){notices.push(args);},confirm(){confirms++;return false;},location:{reload(){reloads++;}},bootstrap:{Modal:class {constructor(){return modal;}static getInstance(){return modal;}}},fetch(url,options){calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve(data,status=200){resolve({ok:status>=200&&status<300,status,json:()=>Promise.resolve(data)});},reject}));}};
    ctx.window=ctx; vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(path.join(root,'app/static/js/api.js'),'utf8'),ctx);
    vm.runInContext(source,ctx);
    async function flush(){for(let i=0;i<20;i++)await Promise.resolve();}
    function open(id=101){ctx.findMaterialImage(id);}
    async function answer(index=0,title='A',count=2){pending[index].resolve({status:'success',query:title,candidates:Array.from({length:count},(_,i)=>({title:title+i,image_url:'https://example.invalid/'+title+i+'.jpg'}))});await flush();}
    function buttons(){return nodes.get('materialImageGrid').children.map(card=>card.children[1].children[1]);}
    function titles(){return nodes.get('materialImageGrid').children.map(card=>card.children[1].children[0].textContent);}
    return {ctx,nodes,calls,pending,notices,timers,modal,open,answer,buttons,titles,flush,get reloads(){return reloads;},get confirms(){return confirms;},replace(id){const old=nodes.get(id);old.connected=false;nodes.set(id,new Element());}};
}
const cases=[]; const test=(name,run)=>cases.push({name,run});
test('normal-search-and-explicit-selection-payload',async()=>{const f=fixture();f.open();assert.equal(f.calls.length,1);await f.answer();assert.deepEqual(f.titles(),['A0','A1']);assert.equal(f.calls.length,1);f.buttons()[1].dispatch('click');assert.equal(f.calls.length,2);assert.equal(f.calls[1].url,'/material/101/image_select');assert.equal(JSON.parse(f.calls[1].options.body).image_url,'https://example.invalid/A1.jpg');assert.equal(f.calls[1].options.headers['X-CSRFToken'],'test-csrf');});
for(const order of ['AB','BA'])test('late-search-cannot-mix-closed-A-with-B-'+order,async()=>{const f=fixture();f.open();f.modal.hide();f.open(202);for(const key of order)await f.answer(key==='A'?0:1,key);assert.deepEqual(f.titles(),['B0','B1']);assert.equal(f.nodes.get('materialImageQuery').textContent,'搜索词：B');f.buttons()[0].dispatch('click');assert.equal(f.calls.at(-1).url,'/material/202/image_select');});
for(const event of ['hide.bs.modal','hidden.bs.modal'])for(const outcome of ['success','business','network'])test('closed-search-'+event+'-'+outcome,async()=>{const f=fixture();f.open();f.nodes.get('materialImageModal').dispatch(event);const before=f.nodes.get('materialImageStatus').textContent;if(outcome==='success')await f.answer();else {outcome==='network'?f.pending[0].reject(Error('old failure')):f.pending[0].resolve({status:'error',msg:'old failure'});await f.flush();}assert.equal(f.titles().length,0);assert.equal(f.nodes.get('materialImageStatus').textContent,before);});
for(const outcome of ['business','network'])test('old-search-failure-cannot-overwrite-B-'+outcome,async()=>{const f=fixture();f.open();f.modal.hide();f.open(202);await f.answer(1,'B');const before=f.nodes.get('materialImageStatus').textContent;outcome==='network'?f.pending[0].reject(Error('old failure')):f.pending[0].resolve({status:'error',msg:'old failure'});await f.flush();assert.equal(f.nodes.get('materialImageStatus').textContent,before);assert.deepEqual(f.titles(),['B0','B1']);});
for(const id of ['materialImageModal','materialImageStatus','materialImageGrid','materialImageQuery'])test('search-DOM-identity-'+id,async()=>{const f=fixture();f.open();const old=f.nodes.get('materialImageGrid');f.replace(id);await f.answer();assert.equal(old.children.length,0);});
test('detached-modal-search-is-inert',async()=>{const f=fixture();f.open();f.nodes.get('materialImageModal').connected=false;await f.answer();assert.equal(f.titles().length,0);});
test('old-candidate-click-is-inert-after-reopen',async()=>{const f=fixture();f.open();await f.answer();const old=f.buttons()[0];f.modal.hide();f.open(202);await f.answer(1,'B');old.dispatch('click');assert.equal(f.calls.length,2);});
test('same-modal-candidate-saves-are-single-flight',async()=>{const f=fixture();f.open();await f.answer();const buttons=f.buttons();buttons[0].dispatch('click');buttons[1].dispatch('click');buttons[0].dispatch('click');assert.equal(f.calls.length,2);assert(buttons.every(b=>b.disabled));});
for(const outcome of ['success','business','network'])test('old-save-cannot-close-refresh-or-notify-B-'+outcome,async()=>{const f=fixture();f.open();await f.answer();f.buttons()[0].dispatch('click');f.modal.hide();f.open(202);await f.answer(2,'B');const hides=f.modal.hides;outcome==='network'?f.pending[1].reject(Error('old save')):f.pending[1].resolve({status:outcome==='success'?'success':'error',msg:'old save'});await f.flush();for(const fn of f.timers)fn();assert.equal(f.modal.hides,hides);assert.equal(f.reloads,0);assert.equal(f.notices.length,0);assert(f.buttons().every(b=>!b.disabled));});
for(const outcome of ['business','network'])test('current-save-failure-unlocks-all-for-retry-'+outcome,async()=>{const f=fixture();f.open();await f.answer();f.buttons()[0].dispatch('click');outcome==='network'?f.pending[1].reject(Error('save failure')):f.pending[1].resolve({status:'error',msg:'save failure'});await f.flush();assert(f.buttons().every(b=>!b.disabled));assert.equal(f.notices.length,1);f.buttons()[1].dispatch('click');assert.equal(f.calls.length,3);});
test('current-save-success-reloads-once-and-stays-locked',async()=>{const f=fixture();f.open();await f.answer();const buttons=f.buttons();buttons[0].dispatch('click');f.pending[1].resolve({status:'success'});await f.flush();buttons[1].dispatch('click');assert.equal(f.calls.length,2);assert.equal(f.modal.hides,1);assert.equal(f.notices.length,1);for(const fn of f.timers)fn();assert.equal(f.reloads,1);});
test('success-delayed-navigation-cannot-refresh-reopened-B',async()=>{const f=fixture();f.open();await f.answer();f.buttons()[0].dispatch('click');f.pending[1].resolve({status:'success'});await f.flush();f.open(202);await f.answer(2,'B');for(const fn of f.timers)fn();assert.equal(f.reloads,0);assert(f.modal.visible);});
for(const id of ['materialImageModal','materialImageStatus','materialImageGrid','materialImageQuery'])test('save-DOM-identity-'+id,async()=>{const f=fixture();f.open();await f.answer();f.buttons()[0].dispatch('click');f.replace(id);f.pending[1].resolve({status:'success'});await f.flush();for(const fn of f.timers)fn();assert.equal(f.notices.length,0);assert.equal(f.reloads,0);assert.equal(f.modal.hides,0);});
test('empty-search-keeps-manual-upload-guidance',async()=>{const f=fixture();f.open();await f.answer(0,'A',0);assert.match(f.nodes.get('materialImageStatus').textContent,/手动上传/);assert.equal(f.titles().length,0);});
test('current-search-business-error-is-visible',async()=>{const f=fixture();f.open();f.pending[0].resolve({status:'error',msg:'搜索失败原因'});await f.flush();assert.equal(f.nodes.get('materialImageStatus').textContent,'搜索失败原因');});
test('shared-api-session-expiry-still-handled',async()=>{const f=fixture();f.open();f.modal.hide();f.pending[0].resolve({},401);await f.flush();assert.equal(f.confirms,1);assert.equal(f.titles().length,0);});
(async()=>{const results=[];for(const c of cases){try{await c.run();results.push({name:c.name,status:'passed'});}catch(e){results.push({name:c.name,status:'failed',message:e.message,stack:e.stack});}}console.log(JSON.stringify({total:results.length,passed:results.filter(r=>r.status==='passed').length,failed:results.filter(r=>r.status==='failed').length,results},null,2));process.exitCode=results.some(r=>r.status==='failed')?1:0;})();
