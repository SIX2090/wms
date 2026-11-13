"""Run actual edit JS with a synthetic DOM and a captured, non-network API."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(marker)


PROGRAM = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),Module=require('module');
const originalLoad=Module._load;
Module._load=function(name,...args){
 if(/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))
   throw new Error('network and child modules forbidden');
 return originalLoad.call(this,name,...args);
};
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},handlers={},captured=[];
function element(value='') {
 let current=String(value);
 return {get value(){return current;},set value(value){current=String(value);},
  textContent:'',style:{},dataset:{},validity:{badInput:false},focus(){},select(){},
  addEventListener(){},querySelectorAll(){return [];}};
}
function makeRow(){
 const fields={},row={dataset:{},querySelector:s=>fields[s],
  querySelectorAll:s=>s==='input'?Object.values(fields).filter(x=>x.isInput):[],
  remove(){rows.splice(rows.indexOf(row),1);}};
 Object.defineProperty(row,'innerHTML',{set(html){
  for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)){
   const classes=m[2].match(/class="([^"]*)"/);if(!classes)continue;
   const value=m[2].match(/\bvalue="([^"]*)"/),n=element(value?value[1]:'');
   n.isInput=m[1]==='input';for(const c of classes[1].split(' '))fields['.'+c]=n;
  }
 }});return row;
}
const body={appendChild:r=>rows.push(r),
 querySelectorAll:s=>s==='tr'?rows:s==='.row-no'?rows.map(r=>r.querySelector(s)):[],
 querySelector:s=>s==='tr:last-child'?rows.at(-1):s==='tr'?rows[0]:null};
const material={code:'B-M',name:'Synthetic material',price:3.5,unit:'PCS'},remark=element('original note');
const item={line_id:10,code:'B-M',material,quantity:p.case==='small'?.0001:1.2345,
 price:p.case.includes('missing-price')?null:3.56789,tax_rate:.13,amount:'4.02',untaxed_amount:'3.50',tax_amount:'.52',batch_no:'B'};
const ctx={body,defaultTaxRate:.13,activeDropdown:null,materials:[material],
 existingItems:p.case==='new-zero'?[]:[item],
 originalFinancialHeader:{included:'9.99',untaxed:'3.50',tax:'.52'},
 formFields:['customer_id','remark'],editUrl:'/synthetic-capture-only',
 escAttr:value=>String(value),handleKeydown(){},showDropdown(){},
 document:{createElement:()=>makeRow(),querySelector:s=>s==='[name="remark"]'?remark:element('1'),
  querySelectorAll:()=>[],getElementById:id=>{
   if(id==='copyRowBtn')return {addEventListener:(event,fn)=>handlers.copy=fn};
   return totals[id]??=element();}},window:{},
 WMS:{api:{postRaw:async(url,payload)=>{assert.equal(url,'/synthetic-capture-only');
  captured.push(JSON.parse(JSON.stringify(payload)));return {status:'error',msg:'synthetic capture complete'};}}}};
vm.createContext(ctx);vm.runInContext(p.money,ctx,{timeout:1000});vm.runInContext(p.script,ctx,{timeout:1000});
(async()=>{
 let row;
 if(p.case==='new-zero'){
  row=ctx.addRow({code:'B-M',quantity:0,price:3.5,tax_rate:.13});
  row.querySelector('.qty').value='0';ctx.recalc();await ctx.save();
  assert.equal(captured.length,0,'zero new quantity must not call save');
  assert.match(totals.entryStatus.textContent,/有效销售明细/);return;
 }
 row=ctx.addRow(item);
 assert.equal(row.querySelector('.qty').value,p.case==='small'?'0.0001':'1.2345','opening edit must keep stored input precision');
 assert.equal(row.querySelector('.price').value,p.case.includes('missing-price')?'':'3.56789');
 assert.equal(row.querySelector('.included').textContent,'4.02','unmodified row must display stored money');
 assert.equal(totals.totalIncluded.textContent,'9.99','unmodified header discrepancy must remain visible');
 if(p.case==='remark') {remark.value='only header remark changed';row.querySelector('.line-remark').value='line note changed';ctx.recalc();}
 if(p.case==='quantity') {row.querySelector('.qty').value='1.23';ctx.recalc();
  assert.equal(row.querySelector('.included').textContent,'4.39','actual quantity edit recalculates money');
  assert.equal(totals.totalIncluded.textContent,'4.39');}
 if(p.case==='set-missing-price') {row.querySelector('.price').value='3.5';ctx.recalc();
  assert.equal(row.querySelector('.included').textContent,'4.32');
  assert.equal(totals.totalIncluded.textContent,'4.32');}
 if(p.case==='copy') {handlers.copy();const copy=rows.at(-1);
  assert.equal(copy.dataset.salesLineId,'','copied row cannot inherit source identity');
  assert.equal(copy._salesSnapshot,null,'copied row cannot inherit saved financial snapshot');
  const values=ctx.collect().items;assert.equal(values[0].line_id,'10');assert.equal(values[1].line_id,null);
  return;}
 await ctx.save();assert.equal(captured.length,1);
 const sent=captured[0].items[0];assert.equal(sent.line_id,'10');
 assert.equal(sent.price,p.case==='set-missing-price'?'3.5':p.case==='missing-price'?'':'3.56789');
 assert.equal(sent.quantity,p.case==='quantity'?'1.23':p.case==='small'?'0.0001':'1.2345');
 assert.equal(Object.hasOwn(sent,'saved_amount'),false,'saved money is server-owned');
 if(p.case!=='quantity'&&p.case!=='set-missing-price'){
  assert.equal(row.querySelector('.included').textContent,'4.02');
  assert.equal(totals.totalIncluded.textContent,'9.99');}
 if(p.case==='remark')assert.equal(captured[0].remark,'only header remark changed');
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


class SalesEditHistoryFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        if not cls.node:
            raise unittest.SkipTest('Node required for actual edit interaction')
        source = (ROOT / 'app/templates/sales_order_edit.html').read_text(encoding='utf-8-sig')
        markers = ('var unitName = function(', 'var findMaterial = function(', 'function recalcRow(',
                   'function recalc(', 'function fillRow(', 'function selectMaterial(',
                   'function addRow(', 'function renumber(', 'function collect(', 'async function save(')
        cls.script = 'var salesSaveBusy = false;\n' + '\n'.join(block(source, marker) + ';' for marker in markers)
        start = source.index("document.getElementById('copyRowBtn').addEventListener")
        end = source.index("document.getElementById('pasteBtn').addEventListener", start)
        cls.script += '\n' + source[start:end]
        cls.money = (ROOT / 'app/static/js/money.js').read_text(encoding='utf-8-sig')

    def check(self, case):
        result = subprocess.run([self.node, '-e', PROGRAM], input=json.dumps({
            'script': self.script, 'money': self.money, 'case': case}),
            encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opening_preserves_exact_inputs_and_recorded_money(self):
        self.check('load')

    def test_only_remarks_keep_exact_inputs_and_money(self):
        self.check('remark')

    def test_explicit_quantity_change_to_two_decimals_is_sent(self):
        self.check('quantity')

    def test_unmodified_small_quantity_is_never_formatted_to_zero(self):
        self.check('small')

    def test_copy_strips_identity_and_recorded_money_snapshot(self):
        self.check('copy')

    def test_new_zero_quantity_is_rejected_before_save(self):
        self.check('new-zero')

    def test_existing_missing_price_stays_blank_with_recorded_money(self):
        self.check('missing-price')

    def test_explicitly_entering_missing_price_changes_money(self):
        self.check('set-missing-price')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SalesEditHistoryFrontend)
    if suite.countTestCases() != 8:
        raise SystemExit('explicit frontend list must contain eight tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
