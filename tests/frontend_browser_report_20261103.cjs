'use strict';
const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const root = process.argv[2], scenario = process.argv[3];
const app = fs.readFileSync(root + '/app/static/js/app.js', 'utf8');
function fn(source, name) {
    const start = source.indexOf('function ' + name + '(');
    assert(start >= 0, name);
    const end = source.indexOf('\n    }', start);
    return source.slice(start, end + 6);
}
if (scenario === 'selection-settings') {
    const checkbox = {tagName:'INPUT',type:'checkbox',classList:{contains:()=>false}};
    const tools = ['cb-col-resizer','wms-fill-down-btn'].map(k=>({classList:{contains:x=>x===k}}));
    const th = {dataset:{columnKey:'column_0',defaultLabel:'column_0'},children:[checkbox,...tools],childNodes:[],
        querySelector:()=>checkbox};
    const table = {querySelectorAll:()=>[th],querySelector:()=>th};
    const ctx = {rememberWmsColumnDefaults(){th.dataset.wmsDefaultColumnIndex='0';},
        localStorage:{getItem:()=>JSON.stringify({order:['column_0'],hidden:['column_0'],labels:{column_0:'column_0'}})},
        location:{pathname:'/warehouse'},CSS:{escape:x=>x}};
    vm.createContext(ctx);
    vm.runInContext(fn(app,'storageKey')+'\n'+fn(app,'columnsOf')+'\n'+fn(app,'readState'),ctx);
    const columns = ctx.columnsOf(table), state = ctx.readState(table,columns);
    assert.equal(columns[0].locked,true);
    assert.equal(state.hidden.length,0);
    assert.equal(state.labels.column_0,undefined);
} else if (scenario.endsWith('-click')) {
    const source=fs.readFileSync(root+'/app/templates/out_order_detail.html','utf8');
    const start=source.indexOf('function toggleColumnSettings()'), end=source.indexOf('// 列显示/隐藏映射',start);
    const listeners=[], operations=[], panel=scenario==='pending-click'?{classList:{remove:x=>operations.push(x),toggle:x=>operations.push(x)}}:null;
    const ctx={document:{getElementById:()=>panel,addEventListener:(event,cb)=>listeners.push(cb)}};
    vm.createContext(ctx);vm.runInContext(source.slice(start,end),ctx);
    ctx.toggleColumnSettings();listeners.forEach(cb=>cb({target:{closest:()=>null}}));
    assert.equal(operations.length,panel?2:0);
} else if (scenario === 'share-capabilities') {
    const start=app.indexOf('buttons = buttons.filter(function(item) { return item.key !== \'share\''),end=app.indexOf('// BUG-2026-08-27-001',start);
    for(const key of ['warehouse','material','purchase_order','in_order','out_order']) for(const id of [null,7]) {
        const ctx={buttons:[{key:'share'},{key:'add'}],module:{key},getCurrentRecordId:()=>id};
        vm.createContext(ctx);vm.runInContext(app.slice(start,end),ctx);
        assert.equal(ctx.buttons.some(b=>b.key==='share'),!!id&&['in_order','out_order'].includes(key));
        assert(ctx.buttons.some(b=>b.key==='add'));
    }
} else if (scenario === 'implemented-tabs') {
    const source=app.slice(app.indexOf('function ensureModal()'),app.indexOf('function renderRows('));
    assert(!source.includes('功能开发中'));
    assert(!source.includes('data-fs-tab="header"'));
    assert(!source.includes('data-fs-tab="footer"'));
    assert(source.includes('data-fs-tab="detail"'));
} else throw Error(scenario);
