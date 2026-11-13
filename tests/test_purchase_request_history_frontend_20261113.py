"""Execute actual editor functions/input events in a synthetic Node DOM; no network."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
def block(source,name):
    start=source.index('function '+name+'(');opening=source.index('{',source.index(') {',start));depth=0
    for end in range(opening,len(source)):
        depth+=(source[end]=='{')-(source[end]=='}')
        if depth==0:return source[start:end+1]
    raise AssertionError(name)

PROGRAM=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),Module=require('module');
const load=Module._load;Module._load=function(name,...args){if(/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))throw Error('external IO forbidden');return load.call(this,name,...args);};
const p=JSON.parse(fs.readFileSync(0,'utf8')),rows=[],totals={},requests=[],messages=[];
function element(value=''){let current=String(value);const events={};return {get value(){return current;},set value(v){current=String(v);},dataset:{},style:{},textContent:'',focus(){},select(){},addEventListener:(type,fn)=>events[type]=fn,fire(type){events[type]?.call(this,{preventDefault(){}});},querySelectorAll(){return [];}};}
function makeRow(){const fields={},row={dataset:{},querySelector:s=>fields[s],querySelectorAll:()=>[]};
 Object.defineProperty(row,'nextElementSibling',{get:()=>rows[rows.indexOf(row)+1]||null});
 Object.defineProperty(row,'innerHTML',{set(html){for(const m of html.matchAll(/<(input|div|button|td)\b([^>]*)>/g)){const classes=m[2].match(/class="([^"]*)"/);if(classes){const n=element();for(const c of classes[1].split(' '))fields['.'+c]=n;}}}});return row;}
const body={appendChild:r=>rows.push(r),insertBefore(r,before){rows.splice(rows.indexOf(before),0,r);}};
const item={line_id:10,material_id:3,material_code:'B-M',material_name:'合成物料',quantity:p.case==='small'?.0001:1.2345,estimated_price:p.case.includes('null')?null:3.56789,estimated_amount:p.case==='zero'?0:4.02};
const fields={request_id:'1',date:'2026-11-13',remark:'old'};
class FormData{get(key){return fields[key]??'';}}
const ctx={rowCounter:0,FormData,initialItems:[item],initialTotalAmount:9.99,
document:{createElement:makeRow,getElementById:id=>id==='materialTableBody'?body:(totals[id]??=element()),querySelectorAll:s=>s==='#materialTableBody tr'?rows:[]},
bindSupplierInput(){},cancelMaterialSearch(){},showToast:msg=>messages.push(msg),
WMS:{api:{postRaw:(url,payload)=>{assert.equal(url,'/purchase_request/add');requests.push(JSON.parse(JSON.stringify(payload)));return Promise.reject(Error('合成错误，预估单价'));}}}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.money,ctx);vm.runInContext(p.script,ctx);
(async()=>{
const row=ctx.addNewRow(null,item);
assert.equal(row.querySelector('.quantity').value,p.case==='small'?'0.0001':'1.2345');
assert.equal(row.querySelector('.estimated-price').value,p.case.includes('null')?'':'3.56789');
assert.equal(row.querySelector('.estimated-amount').value,p.case==='zero'?'0.00':'4.02');
assert.equal(totals.totalAmount.textContent,'¥9.99');
if(p.case==='remark'){fields.remark='header note';row.querySelector('.line-remark').value='line note';}
if(p.case==='quantity'){row.querySelector('.quantity').value='1.23';row.querySelector('.quantity').fire('input');assert.equal(row.querySelector('.estimated-amount').value,'4.39');assert.equal(totals.totalAmount.textContent,'¥4.39');}
if(p.case==='price-zero'){row.querySelector('.estimated-price').value='0';row.querySelector('.estimated-price').fire('input');assert.equal(totals.totalAmount.textContent,'¥0.00');}
if(p.case==='copy'){ctx.copyRowAfter(row);const sent=ctx.collectItems();assert.equal(sent[0].line_id,10);assert.equal(sent[1].line_id,null);assert.equal(rows[1]._requestOriginal,null);return;}
if(p.case==='material'){ctx.selectMaterial(row,{id:4,code:'NEW',name:'合成新物料',price:5});assert.equal(ctx.collectItems()[0].line_id,null);return;}
if(p.case==='null-change'){row.querySelector('.quantity').value='2';row.querySelector('.quantity').fire('input');}
await ctx.submitForm();assert.equal(requests.length,1);const sent=requests[0].items[0];assert.equal(sent.line_id,10);assert.equal(Object.hasOwn(sent,'saved_amount'),false);
assert.equal(sent.quantity,p.case==='quantity'?'1.23':p.case==='small'?'0.0001':p.case==='null-change'?'2':'1.2345');
assert.equal(sent.estimated_price,p.case==='price-zero'?'0':p.case.includes('null')?'':'3.56789');
assert.equal(ctx.submitForm.pending,false);assert(messages.some(msg=>msg.includes('预估单价')));
if(p.case==='null-change'){assert.equal(row._requestOriginal.estimated_amount,4.02);assert.equal(row.querySelector('.quantity').value,'2');}
if(p.case==='remark'){assert.equal(requests[0].remark,'header note');assert.equal(sent.remark,'line note');}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
'''

class PurchaseRequestHistoryFrontend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node=shutil.which('node')
        if not cls.node:raise RuntimeError('Node is required, do not skip this explicit test target')
        source=(ROOT/'app/templates/purchase_request_add.html').read_text(encoding='utf-8-sig')
        names=('addNewRow','fillRowData','bindMaterialInput','getMaterialUnitName','getMaterialUnitId','selectMaterial','copyRowAfter','renumberRows','updateRowAmount','updateTotals','collectItems','submitForm','requestLineId','requestFinancialUnchanged')
        cls.script='\n'.join(block(source,n)+';' for n in names if 'function '+n+'(' in source)
        cls.money=(ROOT/'app/static/js/money.js').read_text(encoding='utf-8-sig')
    def check(self,case):
        result=subprocess.run([self.node,'-e',PROGRAM],input=json.dumps(dict(script=self.script,money=self.money,case=case)),encoding='utf-8',capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_load(self):self.check('load')
    def test_remark(self):self.check('remark')
    def test_explicit_quantity_two_places(self):self.check('quantity')
    def test_small_quantity(self):self.check('small')
    def test_recorded_zero(self):self.check('zero')
    def test_explicit_zero_price(self):self.check('price-zero')
    def test_copy_has_no_saved_identity(self):self.check('copy')
    def test_new_material_has_no_saved_identity(self):self.check('material')
    def test_null_price_metadata(self):self.check('null')
    def test_null_price_error_retains_inputs(self):self.check('null-change')

if __name__=='__main__':unittest.main(verbosity=2)
