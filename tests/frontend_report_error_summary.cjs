const fs = require('fs'), vm = require('vm'), assert = require('assert');
const template=fs.readFileSync(require('path').join(__dirname,'..','app','templates','report_view.html'),'utf8');
function extract(name){const start=template.indexOf('function '+name+'(');const next=template.indexOf('\nfunction ',start+1);return template.slice(start,next);}
let src=extract('loadData'); // async keyword is immediately before function
src='async '+src;
const nodes={summaryCount:{textContent:''},summaryQuantity:{textContent:''},summaryAmount:{textContent:''},dateRangeError:{hidden:true}};
const fields={start_date:{value:''},end_date:{value:''},warehouse_id:{value:'1'}};
const ctx={console,URLSearchParams,reportType:'inventory',reportRequestId:0,summaryTypes:{},document:{getElementById:id=>nodes[id]},filterForm:{querySelector:selector=>fields[selector.slice(1)]},tableBody:{innerHTML:''},tableHeaderRow:{innerHTML:''},paginationNav:{innerHTML:''},pageTotal:{textContent:''},updateReportFilterSummary(){},syncReportFilterUrl(){},setLoading(){},buildParams(){return new URLSearchParams()},renderTable(){},renderPagination(n){ctx.pageTotal.textContent=String(n)},renderTruncation(){},escapeHtml:s=>s,fetch:async()=>({ok:true,json:async()=>({status:'success',summary:{count:2,quantity:100,amount:200},total:2})})};
vm.createContext(ctx);vm.runInContext(extract('formatValue')+'\n'+extract('renderSummary')+'\n'+src,ctx);
(async()=>{
 await vm.runInContext('loadData()',ctx);
 const before={count:nodes.summaryCount.textContent,quantity:nodes.summaryQuantity.textContent,amount:nodes.summaryAmount.textContent};
 fields.warehouse_id.value='2';
 const mode=process.argv[2];ctx.fetch=async()=>{if(mode==='network')throw new Error('Network failure');if(mode==='json')return {ok:true,json:async()=>{throw new Error('Invalid JSON')}};return {ok:mode!=='http',json:async()=>({status:'error',msg:'Query failed'})};};
 await vm.runInContext('loadData()',ctx);
 const after={count:nodes.summaryCount.textContent,quantity:nodes.summaryQuantity.textContent,amount:nodes.summaryAmount.textContent};
 assert.deepStrictEqual(before,{count:'2',quantity:'100',amount:'200'});
 assert.match(ctx.tableBody.innerHTML,/Network failure|Invalid JSON|Query failed/);assert.equal(ctx.pageTotal.textContent,'0');
 assert.deepStrictEqual(after,{count:'—',quantity:'—',amount:'—'});
 console.log(JSON.stringify({confirmed:true,scenario:'query warehouse1 success then query warehouse2 network failure',before,after,table:ctx.tableBody.innerHTML,pageTotal:ctx.pageTotal.textContent},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
