const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const path = require('path'), root = process.argv[2], scenario = process.argv[3];
const source = fs.readFileSync(path.join(root, 'app/static/js/warehouse-monthly-report.js'), 'utf8');
const template = fs.readFileSync(path.join(root, 'app/templates/report_view.html'), 'utf8');
const nodes = {}, handlers = {};
const document = {getElementById(id) {return nodes[id] ||= {value:'',textContent:''};},
    querySelectorAll() {return ['current','previous','year'].map(kind=>({dataset:{monthRange:kind},addEventListener(_,fn){handlers[kind]=fn;}}));}};
const ctx = vm.createContext({window:{}, document, URLSearchParams, Date});
vm.runInContext(source,ctx);
const helper=ctx.window.WMSWarehouseMonthly;
if (scenario==='months') {
    helper.applyRange('previous',document,new Date(2026,0,15));
    assert.equal(nodes.start_month.value,'2025-12'); assert.equal(nodes.end_month.value,'2025-12');
    helper.applyRange('year',document,new Date(2026,9,26));
    assert.equal(nodes.start_month.value,'2026-01'); assert.equal(nodes.end_month.value,'2026-10');
} else if (scenario==='restore') {
    let calls=0;
    helper.initialise(document,'?start_month=2026-08&end_month=2026-09',()=>calls++);
    assert.equal(nodes.start_month.value,'2026-08'); assert.equal(nodes.end_month.value,'2026-09');
    helper.initialise(document,'?start_date=2026-08-20&end_date=2026-09-03',()=>calls++);
    assert.equal(nodes.start_month.value,'2026-08'); assert.equal(nodes.end_month.value,'2026-09');
    handlers.current(); assert.equal(calls,1); assert.equal(nodes.start_month.value,nodes.end_month.value);
} else if (scenario==='cards') {
    vm.runInContext(fs.readFileSync(path.join(root,'app/static/js/material-movement-report.js'),'utf8'),ctx);
    const a=template.indexOf('function renderSummary('),b=template.indexOf('\nfunction renderTable(',a);
    ctx.reportType='warehouse_monthly';
    vm.runInContext(template.slice(a,b),ctx);
    ctx.renderSummary({count:4,material_count:2,start_month:'2026-09',end_month:'2026-10',unit_totals:[
        {unit:'件',beginning_quantity:100,in_quantity:20,out_quantity:30,ending_quantity:90},
        {unit:'米',beginning_quantity:5,in_quantity:0,out_quantity:1,ending_quantity:4}]});
    assert.equal(nodes['summary-ending_quantity'].textContent,'90 件 / 4 米');
    assert(nodes.monthlyReportCount.textContent.includes('物料数：2'));
    ctx.renderSummary(null);
    for(const key of ['beginning_quantity','in_quantity','out_quantity','ending_quantity']) assert.equal(nodes['summary-'+key].textContent,'—');
} else throw Error(scenario);
