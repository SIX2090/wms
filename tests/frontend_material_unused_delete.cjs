const fs = require('fs'), path = require('path'), vm = require('vm'), assert = require('node:assert/strict');
const root = process.argv[2];
const html = fs.readFileSync(path.join(root, 'app/static/js/pages/material-list.js'), 'utf8');
const start = html.indexOf('var materialDeleteBusy = false;');
const end = html.indexOf('// 2026-09-25：物料停用', start);
assert(start >= 0 && end > start);
const source = html.slice(start, end).replace('{{ url_for("delete_material") }}', '/material/delete');

function fixture() {
    const nodes = new Map(), calls = [], pending = [], confirmations = [], notices = [];
    let reloads = 0;
    class Element {
        constructor(tag) { this.tagName = tag; this.children = []; this.handlers = {}; this.disabled = false; this.checked = false; this.value = ''; this.textContent = ''; }
        appendChild(node) { this.children.push(node); }
        replaceChildren() { this.children = []; }
        addEventListener(event, fn) { (this.handlers[event] ||= []).push(fn); }
        dispatch(event, target = this) { for (const fn of this.handlers[event] || []) fn({target}); }
        set innerHTML(_) { throw Error('Dynamic cleanup results must use textContent'); }
    }
    for (const id of ['toolbarEditBtn','toolbarCopyBtn','toolbarPrintBtn','toolbarRemotePrintBtn',
        'toolbarFindImageBtn','toolbarDeleteBtn','toolbarMergeBtn','materialTable','checkAll',
        'materialDeleteResultModal','materialDeleteResults','materialDeleteSummary']) nodes.set(id, new Element('div'));
    const checks = [1,2,3].map(id => Object.assign(new Element('input'), {value:String(id), classList:{contains(name){return name === 'check-item';}}}));
    const document = {
        getElementById(id) { return nodes.get(id); },
        querySelectorAll(selector) { assert.equal(selector, '#materialTable .check-item:checked'); return checks.filter(x=>x.checked); },
        querySelector(selector) { return selector.includes('csrf-token') ? {content:'synthetic-csrf'} : null; },
        createElement(tag) { return new Element(tag); },
    };
    const modal = { visible:false, show(){this.visible=true;}, hide(){this.visible=false;nodes.get('materialDeleteResultModal').dispatch('hidden.bs.modal');} };
    const ctx = {materialPageData:{urls:{delete:'/material/delete'}},document, console, FormData:class{}, Promise, Error, JSON, URLSearchParams,
        setTimeout, showToast(...args){notices.push(args);},
        showConfirm(message, options){return new Promise(resolve=>confirmations.push({message,options,resolve}));},
        location:{reload(){reloads++;}},
        bootstrap:{Modal:class{constructor(){return modal;}static getInstance(){return modal;}}},
        fetch(url, options){calls.push({url,options});return new Promise((resolve,reject)=>pending.push({resolve(data,status=200){resolve({ok:status>=200&&status<300,status,json:()=>Promise.resolve(data)});},reject}));},
    };
    ctx.window=ctx;vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(path.join(root,'app/static/js/api.js'),'utf8'),ctx);
    vm.runInContext(source,ctx);
    ctx.initToolbarActions();
    function select(ids){checks.forEach((node,i)=>node.checked=ids.includes(i+1));nodes.get('materialTable').dispatch('change',checks[0]);}
    async function flush(){for(let i=0;i<25;i++)await Promise.resolve();}
    return {ctx,nodes,checks,calls,pending,confirmations,notices,modal,select,flush,get reloads(){return reloads;}};
}
const receipt = (deleted=1,skipped=1,failed=0) => ({selected_count:deleted+skipped+failed,deleted_count:deleted,skipped_count:skipped,failed_count:failed,
    items:[{id:1,code:'M-1',name:'unused',status:'deleted',reason:'未使用，已删除'}, {id:2,code:'M-2',name:'used',status:'skipped',reason:'存在业务引用'}]});
const tests=[];function test(name,fn){tests.push({name,fn});}
test('multi-selection enables delete but single-record actions stay disabled',async()=>{const f=fixture();assert(f.nodes.get('toolbarDeleteBtn').disabled);f.select([1,2,3]);assert(!f.nodes.get('toolbarDeleteBtn').disabled);assert(f.nodes.get('toolbarEditBtn').disabled);assert(f.nodes.get('toolbarCopyBtn').disabled);assert(f.nodes.get('toolbarFindImageBtn').disabled);f.select([]);assert(f.nodes.get('toolbarDeleteBtn').disabled);});
test('no selection never confirms or posts',async()=>{const f=fixture();await f.ctx.toolbarDelete();assert.equal(f.confirmations.length,0);assert.equal(f.calls.length,0);assert.equal(f.notices.length,1);});
test('cancel preserves all selection and restores button',async()=>{const f=fixture();f.select([1,2]);const action=f.ctx.toolbarDelete();assert(f.nodes.get('toolbarDeleteBtn').disabled);f.confirmations[0].resolve(false);await action;assert.equal(f.calls.length,0);assert.equal(f.checks.filter(x=>x.checked).length,2);assert(!f.nodes.get('toolbarDeleteBtn').disabled);});
test('confirmed batch freezes exact selected IDs and uses real API CSRF',async()=>{const f=fixture();f.select([1,2]);const action=f.ctx.toolbarDelete();f.select([3]);assert(f.nodes.get('toolbarDeleteBtn').disabled);assert.match(f.confirmations[0].message,/2 条/);assert.match(f.confirmations[0].message,/自动保留/);f.confirmations[0].resolve(true);await f.flush();assert.equal(f.calls.length,1);assert.equal(f.calls[0].url,'/material/delete');assert.deepEqual(JSON.parse(f.calls[0].options.body),{ids:['1','2']});assert.equal(f.calls[0].options.headers['X-CSRFToken'],'synthetic-csrf');f.pending[0].resolve({status:'success',data:receipt()});await action;assert(f.modal.visible);assert.equal(f.reloads,0);assert.match(f.nodes.get('materialDeleteSummary').textContent,/已删除 1 条，保留 1 条，失败 0 条/);f.modal.hide();assert.equal(f.reloads,1);f.modal.hide();assert.equal(f.reloads,1);});
test('double click during confirmation or request does not post twice',async()=>{const f=fixture();f.select([1]);const action=f.ctx.toolbarDelete();await f.ctx.toolbarDelete();assert.equal(f.confirmations.length,1);f.confirmations[0].resolve(true);await f.flush();await f.ctx.toolbarDelete();assert.equal(f.calls.length,1);f.pending[0].resolve({status:'success',data:receipt(1,0)});await action;});
test('all-protected 400 displays receipt and does not reload',async()=>{const f=fixture();f.select([1,2]);const action=f.ctx.toolbarDelete();f.confirmations[0].resolve(true);await f.flush();const data=receipt(0,2);data.items.forEach(x=>x.status='skipped');f.pending[0].resolve({status:'error',msg:'没有物料被删除',data},400);await action;assert(f.modal.visible);assert.match(f.nodes.get('materialDeleteSummary').textContent,/已删除 0 条，保留 2 条/);f.modal.hide();assert.equal(f.reloads,0);assert(!f.nodes.get('toolbarDeleteBtn').disabled);});
test('mixed failure results persist until user closes',async()=>{const f=fixture();f.select([1,2,3]);const action=f.ctx.toolbarDelete();f.confirmations[0].resolve(true);await f.flush();const data=receipt(1,1,1);data.items.push({id:3,code:'M-3',name:'failed',status:'failed',reason:'删除失败，已保留'});f.pending[0].resolve({status:'success',data});await action;assert.equal(f.nodes.get('materialDeleteResults').children.length,3);assert.equal(f.nodes.get('materialDeleteResults').children[2].children[2].textContent,'失败，已保留');assert.equal(f.reloads,0);});
for(const failure of ['network','check503','badjson'])test('failure never reloads and restores retry '+failure,async()=>{const f=fixture();f.select([1]);const action=f.ctx.toolbarDelete();f.confirmations[0].resolve(true);await f.flush();if(failure==='network')f.pending[0].reject(Error('synthetic timeout'));else f.pending[0].resolve({status:'error',msg:'本次未删除任何物料'},failure==='check503'?503:400);await action;assert.equal(f.reloads,0);assert(!f.modal.visible);assert(!f.nodes.get('toolbarDeleteBtn').disabled);assert.equal(f.notices.length,1);});
test('result values remain inert text and previous results clear',async()=>{const f=fixture();const data=receipt();data.items[0].name='<img src=x onerror=throw(1)>';f.ctx.showMaterialDeleteResult(data);assert.equal(f.nodes.get('materialDeleteResults').children[0].children[1].textContent,data.items[0].name);f.ctx.showMaterialDeleteResult({selected_count:1,deleted_count:0,skipped_count:1,failed_count:0,items:[data.items[1]]});assert.equal(f.nodes.get('materialDeleteResults').children.length,1);f.modal.hide();assert.equal(f.reloads,0);});
(async()=>{const results=[];for(const {name,fn} of tests){try{await fn();results.push({name,ok:true});}catch(e){results.push({name,ok:false,error:e.stack});}}const failed=results.filter(x=>!x.ok);process.stdout.write(JSON.stringify({passed:results.length-failed.length,failed:failed.length,results},null,2));if(failed.length)process.exitCode=1;})();
