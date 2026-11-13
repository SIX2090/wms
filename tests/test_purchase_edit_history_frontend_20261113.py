"""Actual purchase edit functions and input events on a synthetic, non-network DOM."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


def block(source, marker):
    start = source.index(marker)
    opening = source.index('{', start)
    # addNewRow has an object default before its function body.
    if marker == 'function addNewRow(':
        opening = source.index('{', source.index(') {', start))
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(marker)


PROGRAM = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),Module=require('module');
const load=Module._load;Module._load=function(name,...args){
 if(/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))
  throw new Error('external I/O forbidden');return load.call(this,name,...args);};
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},requests=[],validation=[],messages=[];
function element(value='') {
 let current=String(value);const events={};
 return {get value(){return current;},set value(value){current=String(value);},
  dataset:{},style:{},textContent:'',focus(){},select(){},
  addEventListener:(type,fn)=>{events[type]=fn;},fire(type){events[type]?.call(this,{key:'',preventDefault(){}});},
  querySelectorAll(){return [];}};
}
function makeRow(){
 const fields={},row={querySelector:s=>fields[s],querySelectorAll:()=>[],
  remove(){rows.splice(rows.indexOf(row),1);},closest(){return row;}};
 Object.defineProperty(row,'nextElementSibling',{get:()=>rows[rows.indexOf(row)+1]||null});
 Object.defineProperty(row,'innerHTML',{set(html){
  for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)){
   const classes=m[2].match(/class="([^"]*)"/);if(!classes)continue;
   const value=m[2].match(/\bvalue="([^"]*)"/),n=element(value?value[1]:'');
   for(const c of classes[1].split(' '))fields['.'+c]=n;
  }
 }});return row;
}
const body={appendChild:r=>rows.push(r),insertBefore(r,before){rows.splice(rows.indexOf(before),0,r);}};
const item={line_id:10,material_id:3,material_code:'B-M',material_name:'Synthetic material',
 quantity:p.case==='small'?.0001:1.2345,price:p.case.includes('missing-price')?null:3.56789,amount:4.02};
const fields={order_id:'1',supplier_id:'5',supplier_name:'Synthetic supplier',date:'2026-11-13',remark:'original note'};
class FormData{constructor(form){} get(key){return fields[key]??'';}}
const materials=[{id:3,code:'B-M',name:'Synthetic material',price:3.5,unit:'PCS'},
 {id:4,code:'NEW',name:'Another material',price:5,unit:'PCS'}];
const ctx={FormData,materials,activeDropdown:null,initialItems:p.case==='new-zero'?[]:[item],initialTotalAmount:9.99,
 escapeHtml:value=>String(value??''),document:{createElement:()=>makeRow(),
  getElementById:id=>id==='materialTableBody'?body:(totals[id]??=element()),
  querySelectorAll:selector=>selector==='#materialTableBody tr'?rows:[],},
 showToast:message=>messages.push(message),showPurchaseValidation:errors=>validation.push(...errors),
 WMS:{api:{post:(url,payload)=>{assert.equal(url,'/purchase_order/save');
  requests.push(JSON.parse(JSON.stringify(payload)));return Promise.reject(Error(
   p.case==='change-missing-price-quantity'?'该历史明细缺少单价，请明确填写单价':'synthetic capture only'));}}}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.money,ctx,{timeout:1000});vm.runInContext(p.script,ctx,{timeout:1000});
(async()=>{
 if(p.case==='new-zero'){
  const row=ctx.addNewRow({material_id:3,material_code:'B-M',quantity:0,price:3.5});
  row.querySelector('.material-qty').value='0';await ctx.submitForm(false);
  assert.equal(requests.length,0);assert(validation.some(error=>/数量必须大于/.test(error.message)));return;
 }
 const row=ctx.addNewRow(item);
 assert.equal(row.querySelector('.material-qty').value,p.case==='small'?'0.0001':'1.2345');
 assert.equal(row.querySelector('.material-price').value,p.case.includes('missing-price')?'':'3.56789');
 assert.equal(row.querySelector('.material-amount').value,'4.02');
 assert.equal(totals.totalAmount.textContent,'¥9.99');
 if(p.case==='remark'){fields.remark='only header changed';row.querySelector('.material-remark').value='line note changed';}
 if(p.case==='quantity'){row.querySelector('.material-qty').value='1.23';row.querySelector('.material-qty').fire('input');
  assert.equal(row.querySelector('.material-amount').value,'4.39');assert.equal(totals.totalAmount.textContent,'¥4.39');}
 if(p.case==='price-zero'){row.querySelector('.material-price').value='0';row.querySelector('.material-price').fire('input');
  assert.equal(row.querySelector('.material-qty').value,'1.2345');assert.equal(totals.totalAmount.textContent,'¥0.00');}
 if(p.case==='set-missing-price'){row.querySelector('.material-price').value='3.5';row.querySelector('.material-price').fire('input');
  assert.equal(row.querySelector('.material-amount').value,'4.32');}
 if(p.case==='change-missing-price-quantity'){
  row.querySelector('.material-qty').value='2';row.querySelector('.material-qty').fire('input');
  await ctx.submitForm(false);assert.equal(requests.length,1);
  assert.equal(requests[0].items[0].quantity,'2');assert.equal(requests[0].items[0].price,'');
  assert(messages.some(message=>message.includes('单价')));assert.equal(ctx.submitForm.pending,false);
  assert.equal(row.querySelector('.material-qty').value,'2');assert.equal(row.querySelector('.material-price').value,'');
  assert.equal(row._purchaseSnapshot.amount,4.02,'error cannot mutate saved snapshot');return;
 }
 if(p.case.startsWith('fill-missing-price-quantity-')){
  const entered=p.case.slice('fill-missing-price-quantity-'.length);
  row.querySelector('.material-qty').value='2';row.querySelector('.material-price').value=entered;
  row.querySelector('.material-price').fire('input');await ctx.submitForm(false);
  assert.equal(requests.length,1);assert.equal(requests[0].items[0].quantity,'2');
  assert.equal(requests[0].items[0].price,entered);assert.equal(requests[0].items[0].line_id,10);
  assert.equal(row.querySelector('.material-amount').value,entered==='0'?'0.00':'7.00');return;
 }
 if(p.case==='copy-previous'||p.case==='copy-after'){
  if(p.case==='copy-previous')ctx.copyPreviousRow();else ctx.copyRowAfter(row);
  const values=ctx.collectItems();assert.equal(values[0].line_id,10);assert.equal(values[1].line_id,null);
  assert.equal(rows[1]._purchaseSnapshot,null);return;
 }
 if(p.case==='material'){
  row.querySelector('.material-code').value='NEW';ctx.fillMaterial(row,materials[1]);
  const values=ctx.collectItems();assert.equal(values[0].line_id,null);assert.equal(Number(values[0].material_id),4);
  assert.equal(Object.hasOwn(values[0],'purchase_request_item_id'),false);return;
 }
 await ctx.submitForm(false);assert.equal(validation.length,0);assert.equal(requests.length,1);
 const sent=requests[0].items[0];assert.equal(sent.line_id,10);assert.equal(Object.hasOwn(sent,'saved_amount'),false);
 assert.equal(sent.quantity,p.case==='quantity'?'1.23':p.case==='small'?'0.0001':'1.2345');
 assert.equal(sent.price,p.case==='price-zero'?'0':p.case==='set-missing-price'?'3.5':p.case==='missing-price'?'':'3.56789');
 if(p.case==='remark'){assert.equal(requests[0].remark,'only header changed');assert.equal(sent.remark,'line note changed');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''


class PurchaseEditHistoryFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        if not cls.node:
            raise unittest.SkipTest('Node required for actual purchase edit interactions')
        source = (ROOT / 'app/templates/purchase_order_add.html').read_text(encoding='utf-8-sig')
        markers = ('function getMaterialUnit(', 'function formatMoney(', 'function materialSearchText(',
                   'function findMaterial(', 'function findMaterialByKeyword(', 'function addNewRow(',
                   'function bindRow(', 'function fillMaterial(', 'function purchaseLineId(',
                   'function calcAmount(', 'function calcTotal(', 'function renumberRows(',
                   'function rowData(', 'function copyPreviousRow(', 'function copyRowAfter(',
                   'function collectItems(', 'function collectPurchaseValidationErrors(', 'function submitForm(')
        cls.script = '\n'.join(block(source, marker) + ';' for marker in markers
                               if marker != 'function purchaseLineId(' or marker in source)
        cls.money = (ROOT / 'app/static/js/money.js').read_text(encoding='utf-8-sig')

    def check(self, case):
        result = subprocess.run([self.node, '-e', PROGRAM], input=json.dumps({
            'script': self.script, 'money': self.money, 'case': case}),
            encoding='utf-8', capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opening_keeps_exact_components_and_recorded_money(self):
        self.check('load')

    def test_only_remarks_send_original_identity_and_money_components(self):
        self.check('remark')

    def test_actual_quantity_input_event_sends_explicit_two_decimal_change(self):
        self.check('quantity')

    def test_explicit_zero_price_keeps_original_quantity_precision(self):
        self.check('price-zero')

    def test_unmodified_small_quantity_is_preserved(self):
        self.check('small')

    def test_missing_price_is_not_silently_filled(self):
        self.check('missing-price')

    def test_operator_can_fill_a_missing_price(self):
        self.check('set-missing-price')

    def test_both_copy_paths_create_rows_without_source_identity(self):
        self.check('copy-previous')
        self.check('copy-after')

    def test_material_change_is_an_explicit_new_row(self):
        self.check('material')

    def test_new_zero_quantity_uses_actual_validation_and_never_posts(self):
        self.check('new-zero')

    def test_unknown_price_rejection_is_shown_without_losing_inputs(self):
        self.check('change-missing-price-quantity')

    def test_explicit_zero_and_positive_price_are_sent_with_quantity_change(self):
        self.check('fill-missing-price-quantity-0')
        self.check('fill-missing-price-quantity-3.5')


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PurchaseEditHistoryFrontend)
    if suite.countTestCases() != 12:
        raise SystemExit('explicit purchase frontend list must contain 12 tests')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
