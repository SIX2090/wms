"""Real selection function/api.js in a closed Node VM; not a browser/app run."""
import ast
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ('/after_sale_out/17/copy','/check/17/copy','/in_order/17/copy_to_out',
 '/in_order/17/copy','/out_order/17/copy','/purchase_order/17/copy','/sales/17/copy',
 '/subcontract/17/copy','/transfer/17/copy','/purchase_order/17/create_in_order',
 '/purchase_order/create_in_order_from_selection','/bom/17/create_requisition')
SCENARIOS = [('raw', path) for path in COMMANDS]
SCENARIOS += [(mode, '/purchase_order/create_in_order_from_selection')
              for mode in ('none','zero','nan','over','success','network','business','http')]
assert len(SCENARIOS) == 20

PROGRAM = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const [mode,path]=JSON.parse(process.argv[3]),calls=[],toasts=[];
const qty={value:mode==='zero'?'0':mode==='nan'?'abc':mode==='over'?'11':'2',getAttribute(){return '10';},focus(){this.focused=true;}};
const row={querySelector(){return qty;}};
const check={dataset:{itemId:'7'},closest(){return row;},focus(){this.focused=true;}};
const ctx={FormData:class {},Date,Math,
 document:{querySelectorAll(){return mode==='none'?[]:[check];},querySelector(selector){
  if(selector.includes('csrf-token'))return {content:'SYN-CSRF'};
  if(selector==='[name="warehouse_id"]')return {value:'4'};
  if(selector==='[name="remark"]')return {value:'原备注'};
  return check;
 }},showToast(...args){toasts.push(args);},location:{href:'original'},confirm(){return false;},setTimeout(){},
 fetch(url,options){
  calls.push({url,options});const fail=calls.length===1;
  if(fail&&(mode==='network'||mode==='raw'))return Promise.reject(Error('lost synthetic response'));
  const status=fail&&mode==='http'?400:200;
  return Promise.resolve({status,ok:status===200,json(){return Promise.resolve({
   status:fail&&['business','http'].includes(mode)?'error':'success',id:77,
   redirect_url:'/in_order/77',msg:'合成业务消息'
  });}});
 }
};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const html=fs.readFileSync(process.argv[2],'utf8'),start=html.indexOf('function createInOrderFromPurchaseOrderSelection()');
const end=html.indexOf('// ==================== 扫码自动填充',start);
assert.ok(start>=0&&end>start);vm.runInContext(html.slice(start,end),ctx);
const key=index=>calls[index].options.headers['X-Idempotency-Key'];
const tick=()=>new Promise(setImmediate);
(async()=>{
 if(mode==='raw'){
  const body={id:17,order_id:19};
  await assert.rejects(()=>ctx.WMS.api.postRaw(path,body));
  assert.equal(typeof key(0),'string');assert.ok(key(0).length>10);
  const response=await ctx.WMS.api.postRaw(path,body);assert.equal(response.id,77);
  assert.equal(key(1),key(0));await ctx.WMS.api.postRaw(path,body);assert.notEqual(key(2),key(1));return;
 }
 ctx.createInOrderFromPurchaseOrderSelection();await tick();
 if(['none','zero','nan','over'].includes(mode)){
  assert.equal(calls.length,0);assert.equal(toasts.length,1);assert.equal(ctx.location.href,'original');
  assert.ok(mode==='none'?check.focused:qty.focused);return;
 }
 assert.equal(calls.length,1);assert.equal(calls[0].url,path);
 assert.equal(typeof key(0),'string');assert.ok(key(0).length>10);
 assert.equal(calls[0].options.headers['X-CSRFToken'],'SYN-CSRF');
 assert.deepEqual(JSON.parse(calls[0].options.body),{warehouse_id:'4',remark:'原备注',items:[{purchase_order_item_id:'7',quantity:2}]});
 if(mode==='success'){
  assert.equal(ctx.location.href,'/in_order/77');assert.equal(toasts.length,0);
  ctx.createInOrderFromPurchaseOrderSelection();await tick();assert.notEqual(key(1),key(0));
 }else{
  assert.equal(ctx.location.href,'original');assert.equal(toasts.length,1);assert.ok(toasts[0][0].startsWith('生成失败：'));
  ctx.createInOrderFromPurchaseOrderSelection();await tick();assert.equal(key(1),key(0));assert.equal(ctx.location.href,'/in_order/77');
  ctx.createInOrderFromPurchaseOrderSelection();await tick();assert.notEqual(key(2),key(1));
 }
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
'''


class PurchaseSelectionCommandVMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        assert cls.node, 'Node required; do not silently skip explicit VM cases'
        tree = ast.parse((ROOT/'tests/test_document_command_transport_vm_20261114.py').read_text(encoding='utf-8'))
        guard = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                     and any(isinstance(t,ast.Name) and t.id=='NODE_GUARD' for t in n.targets))
        cls.temp = tempfile.TemporaryDirectory(prefix='wms-selection-node-guard-')
        cls.guard = Path(cls.temp.name)/'guard.cjs'
        cls.guard.write_text(guard,encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def scenario(self, specification):
        env = {key:os.environ[key] for key in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP') if key in os.environ}
        result = subprocess.run([self.node,'--require',str(self.guard),'-e',PROGRAM,
            str(ROOT/'app/static/js/api.js'),str(ROOT/'app/templates/in_order_add.html'),json.dumps(specification)],
            capture_output=True,text=True,encoding='utf-8',timeout=20,env=env)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


for index, specification in enumerate(SCENARIOS):
    def test(self,specification=specification):
        self.scenario(specification)
    setattr(PurchaseSelectionCommandVMTests,'test_selection_transport_'+str(index),test)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PurchaseSelectionCommandVMTests)
    assert suite.countTestCases()==20
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
