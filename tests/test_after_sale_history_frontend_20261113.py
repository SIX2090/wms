"""Actual售后 editor functions/input events; synthetic DOM/API, no real requests."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
def block(source,name):
    start=source.index('function '+name+'(')
    if source[max(0,start-6):start]=='async ':start-=6
    opening=source.index('{',source.index(') {',start));depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if depth==0:return source[start:end+1]
    raise AssertionError(name)

PROGRAM=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),Module=require('module');
const load=Module._load;Module._load=function(name,...args){if(/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))throw Error('external IO forbidden');return load.call(this,name,...args);};
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},requests=[],errors=[],messages=[];
function element(value=''){let current=String(value);const events={};return {get value(){return current;},set value(v){current=String(v);},dataset:{},style:{},textContent:'',focus(){},select(){},addEventListener:(type,fn)=>events[type]=fn,fire(type){events[type]?.call(this,{preventDefault(){}});},querySelectorAll(){return [];}};}
function makeRow(){const fields={},row={dataset:{},querySelector:s=>fields[s],querySelectorAll:()=>[],closest(){return row;},remove(){rows.splice(rows.indexOf(row),1);}};
 Object.defineProperty(row,'nextElementSibling',{get:()=>rows[rows.indexOf(row)+1]||null});
 Object.defineProperty(row,'innerHTML',{set(html){for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)){const classes=m[2].match(/class="([^"]*)"/);if(classes){const n=element();for(const c of classes[1].split(' '))fields['.'+c]=n;}}}});return row;}
const body={appendChild:r=>rows.push(r),insertBefore(r,before){rows.splice(rows.indexOf(before),0,r);}};
const item={line_id:10,material_code:'B-M',material_name:'合成物料',quantity:p.case==='small'?.0001:p.case==='precision'?1.2345:1.15,price:p.case==='precision'?3.56789:3.5,amount:p.case==='zero'?0:4.02};
const fields={order_id:'1',order_no:'ASO-SYN-HISTORY',date:'2026-11-13',warehouse_id:'5',reason:'合成售后',remark:'old'};
const headerFields={};for(const [key,value] of Object.entries(fields))headerFields[key]=element(value);
const materials=[{id:3,code:'B-M',name:'合成物料',price:99,unit:{name:'个'}},{id:4,code:'NEW',name:'合成新物料',price:5,unit:{name:'个'}}];
const ctx={materials,initialItems:[item],initialTotalAmount:p.case==='head-zero'?0:p.case==='head-none'?null:9.99,activeDropdown:null,
 document:{createElement:makeRow,getElementById:id=>id==='materialTableBody'?body:(totals[id]??=element()),
 querySelector:s=>headerFields[s.match(/name="([^"]+)"/)?.[1]]??element(),querySelectorAll:s=>s==='#materialTableBody tr'?rows:[]},
 collectAfterSaleOutErrors:()=>[],showAfterSaleOutValidation:value=>errors.push(...value),showToast:msg=>messages.push(msg),
 WMS:{MaterialPicker:{bindEntryRow(){}},api:{postRaw:(url,payload)=>{assert.equal(url,'/after_sale_out/add');requests.push(JSON.parse(JSON.stringify(payload)));return Promise.reject(Error('合成保存失败'));}}}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.money,ctx);vm.runInContext('const canEditAfterSaleOut=true;let afterSaleOutSaveBusy=false;'+p.script,ctx);
(async()=>{
const row=ctx.addNewRow(null,item);
assert.equal(row.querySelector('.material-qty').value,p.case==='small'?'0.0001':p.case==='precision'?'1.2345':'1.15');
assert.equal(row.querySelector('.material-price').value,p.case==='precision'?'3.56789':'3.5');
assert.equal(row.querySelector('.material-amount').value,p.case==='zero'?'0.00':'4.02');
assert.equal(totals.totalAmount.textContent,p.case==='head-zero'?'¥0.00':p.case==='head-none'?'¥4.02':'¥9.99');
if(p.case==='remark'){headerFields.remark.value='header note';row.querySelector('.material-remark').value='line note';}
if(p.case==='quantity'){row.querySelector('.material-qty').value='2';row.querySelector('.material-qty').fire('input');assert.equal(row.querySelector('.material-amount').value,'7.00');assert.equal(totals.totalAmount.textContent,'¥7.00');}
if(p.case==='price-zero'){row.querySelector('.material-price').value='0';row.querySelector('.material-price').fire('input');assert.equal(totals.totalAmount.textContent,'¥0.00');}
if(p.case==='copy'){ctx.copyRowAfter(row);const sent=ctx.collectAfterSaleOutRows();assert.equal(sent.items[0].line_id,10);assert.equal(sent.items[1].line_id,null);assert.equal(rows[1]._afterSaleOriginal,null);return;}
if(p.case==='material'){ctx.selectMaterial(row,'NEW');assert.equal(ctx.collectAfterSaleOutRows().items[0].line_id,null);return;}
if(p.case==='new-zero'){row.remove();const fresh=ctx.addNewRow(null,{material_code:'B-M',quantity:0,price:3.5});fresh.querySelector('.material-qty').value='0';await ctx.submitForm();assert.equal(requests.length,0);assert(errors.some(e=>/数量必须大于/.test(e.message)));return;}
await ctx.submitForm();assert.equal(errors.length,0);assert.equal(requests.length,1);const sent=requests[0].items[0];assert.equal(sent.line_id,10);assert.equal(Object.hasOwn(sent,'saved_amount'),false);
assert.equal(sent.quantity,p.case==='quantity'?2:p.case==='small'?.0001:p.case==='precision'?1.2345:1.15);
assert.equal(sent.price,p.case==='price-zero'?0:p.case==='precision'?3.56789:3.5);
assert(messages.some(msg=>msg.includes('合成保存失败')));assert.equal(row._afterSaleOriginal.amount,p.case==='zero'?0:4.02);
if(p.case==='remark'){assert.equal(requests[0].remark,'header note');assert.equal(sent.remark,'line note');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''

class AfterSaleHistoryFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node=shutil.which('node')
        if not cls.node:raise RuntimeError('Node required; explicit list must not be skipped')
        source=(ROOT/'app/templates/after_sale_out_add.html').read_text(encoding='utf-8-sig')
        names=('addNewRow','fillRowData','bindRow','selectMaterial','calcAmount','calcTotal','copyRowAfter','insertRowBefore','renumberRows','collectAfterSaleOutRows','submitForm')
        cls.script='\n'.join(block(source,n)+';' for n in names)
        cls.money=(ROOT/'app/static/js/money.js').read_text(encoding='utf-8-sig')
    def check(self,case):
        r=subprocess.run([self.node,'-e',PROGRAM],input=json.dumps(dict(script=self.script,money=self.money,case=case)),capture_output=True,encoding='utf-8',timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_load_preserves_historical_money(self):self.check('load')
    def test_remark_only_payload_preserves_identity_and_components(self):self.check('remark')
    def test_explicit_quantity_input_revalues(self):self.check('quantity')
    def test_small_quantity_not_rounded_on_load(self):self.check('small')
    def test_high_precision_components_not_rounded_on_load(self):self.check('precision')
    def test_recorded_zero_amount_survives(self):self.check('zero')
    def test_explicit_zero_price_revalues(self):self.check('price-zero')
    def test_copy_line_has_no_recorded_identity(self):self.check('copy')
    def test_changed_material_has_no_old_identity(self):self.check('material')
    def test_new_zero_quantity_is_rejected(self):self.check('new-zero')
    def test_known_zero_header_survives(self):self.check('head-zero')
    def test_missing_header_uses_recorded_line_amount(self):self.check('head-none')

if __name__=='__main__':unittest.main(verbosity=2)
