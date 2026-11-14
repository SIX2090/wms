"""Real api.js in a Node VM with a closed fake transport, never a WMS/browser run."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = (
    '/after_sale_out/17/copy', '/check/17/copy', '/in_order/17/copy_to_out',
    '/in_order/17/copy', '/out_order/17/copy', '/purchase_order/17/copy',
    '/sales/17/copy', '/subcontract/17/copy', '/transfer/17/copy',
    '/purchase_order/17/create_in_order', '/purchase_order/create_in_order_from_selection',
    '/bom/17/create_requisition',
)
SAVE_PATHS = (
    '/bom/add', '/bom/save_table', '/in_order/add', '/out_order/add', '/adjustment/add',
    '/after_sale_out/add', '/check/save_table', '/check/add', '/transfer/save_table',
    '/transfer/add', '/purchase_request/add', '/requisition/add', '/requisition/save_table',
    '/purchase_order/save', '/sales/add', '/subcontract/add', '/subcontract_issue/add',
    '/subcontract/issue/add', '/subcontract_receive/add', '/subcontract/receive/add',
)
MODES = ('network', 'malformed', 'http', 'business', 'no_body', 'source_ids', 'form_ids', 'explicit')
SCENARIOS = [(url, mode, 'POST') for url in COMMANDS for mode in MODES]
SCENARIOS += [(url, 'legacy_save', 'POST') for url in SAVE_PATHS]
SCENARIOS += [(url, 'legacy_edit', 'POST') for url in SAVE_PATHS]
SCENARIOS += [('/in_order/17/copy', 'unrelated', method) for method in ('GET', 'PUT', 'DELETE')]
SCENARIOS += [('/in_order/17/complete', 'unrelated', 'POST'), ('/api/material/search', 'unrelated', 'POST')]
assert len(COMMANDS) == 12 and len(SAVE_PATHS) == 20 and len(SCENARIOS) == 141

NODE_PROGRAM = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const spec=JSON.parse(process.argv[2]),calls=[];
const [url,mode,method]=spec;
class FakeFormData {
  constructor(){this.values={id:'17',order_id:'19',csrf_token:'FORM-CSRF'};}
  get(name){return this.values[name]===undefined?null:this.values[name];}
}
let random=0;const randomMath=Object.create(Math);randomMath.random=()=>++random/100000;
const ctx={FormData:FakeFormData,Math:randomMath,Date,
 document:{querySelector(s){return s.includes('meta')?{content:'SYN-CSRF'}:null;}},
 location:{href:'synthetic',origin:'https://synthetic.invalid'},confirm(){return false;},setTimeout(){},
 fetch(target,options){
  calls.push({url:target,options});const first=calls.length===1;
  const failure=!['legacy_edit','unrelated'].includes(mode)&&first;
  if(failure&&!['malformed','http','business'].includes(mode))return Promise.reject(Error('synthetic response lost'));
  const status=failure&&mode==='http'?400:200;
  return Promise.resolve({status,ok:status===200,json(){
   if(failure&&mode==='malformed')return Promise.reject(Error('synthetic invalid JSON'));
   return Promise.resolve({status:failure&&mode==='business'?'error':'success',id:23,msg:'synthetic'});
  }});
 }
};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
let data={items:[{code:'SYNTHETIC',quantity:1}],remark:'unchanged'};
if(mode==='source_ids'||mode==='legacy_edit')data={id:17,order_id:19,request_id:21,header:{id:17},remark:'same source'};
if(mode==='form_ids')data=new FakeFormData();
if(mode==='no_body')data=undefined;
const originalData=data, originalJSON=JSON.stringify(data);
function send(options){
 if(method==='POST')return ctx.WMS.api.post(url,data,options);
 if(method==='GET')return ctx.WMS.api.get(url,options);
 if(method==='PUT')return ctx.WMS.api.put(url,data,options);
 return ctx.WMS.api.delete(url,data,options);
}
function key(index){return calls[index].options.headers['X-Idempotency-Key'];}
(async()=>{
 const options=mode==='explicit'?{headers:{'X-Idempotency-Key':'caller-owned-key','X-Custom':'keep'}}:undefined;
 if(mode==='legacy_edit'||mode==='unrelated'){
  await send(options);assert.equal(key(0),undefined);return;
 }
 await assert.rejects(()=>send(options));
 assert.equal(typeof key(0),'string');assert.ok(key(0).length>10);
 await send(options);assert.equal(key(1),key(0),'unknown result must retain the same request identity');
 await send();assert.notEqual(key(2),key(1),'known success must release the URL intent for the next command');
 assert.equal(JSON.stringify(data),originalJSON,'intent detection must not mutate the original source payload');
 for(const call of calls){
  assert.equal(call.options.credentials,'same-origin');assert.equal(call.options.headers['X-CSRFToken'],'SYN-CSRF');
  if(mode==='form_ids'){
   assert.equal(call.options.body,originalData);assert.equal(call.options.headers['Content-Type'],undefined);
  }else if(mode==='no_body')assert.equal(call.options.body,undefined);
  else{assert.equal(call.options.body,originalJSON);assert.equal(call.options.headers['Content-Type'],'application/json');}
 }
 if(mode==='explicit'){
  assert.equal(key(0),'caller-owned-key');assert.equal(key(1),'caller-owned-key');
  assert.equal(calls[1].options.headers['X-Custom'],'keep');
 }
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
'''

NODE_GUARD = r'''
const load=require('module')._load;
require('module')._load=function(name,...args){
 if(/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))throw Error('external I/O forbidden');
 return load.call(this,name,...args);
};
global.fetch=()=>{throw Error('real fetch forbidden');};
'''


class CommandTransportVMTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = shutil.which('node')
        if not cls.node:
            raise AssertionError('Node is required; the explicit VM suite must not silently skip')
        cls.temp = tempfile.TemporaryDirectory(prefix='wms-command-node-guard-')
        cls.guard = Path(cls.temp.name) / 'guard.cjs'
        cls.guard.write_text(NODE_GUARD, encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_scenario(self, scenario):
        env = {key: os.environ[key] for key in ('PATH', 'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')
               if key in os.environ}
        result = subprocess.run(
            [self.node, '--require', str(self.guard), '-e', NODE_PROGRAM,
             str(ROOT / 'app/static/js/api.js'), json.dumps(scenario)],
            capture_output=True, text=True, encoding='utf-8', timeout=20, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


for index, specification in enumerate(SCENARIOS):
    def _generated_case(self, specification=specification):
        self.run_scenario(specification)
    setattr(CommandTransportVMTests, 'test_command_transport_' + str(index), _generated_case)

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CommandTransportVMTests)
    assert suite.countTestCases() == 141
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
