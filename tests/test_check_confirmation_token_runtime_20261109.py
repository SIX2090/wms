"""Run the shared completion functions in a Node VM with synthetic requests only."""
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def deny(*_args, **_kwargs):
    raise AssertionError('production database and network are forbidden')


PROGRAM = r'''
'use strict';
const assert = require('node:assert/strict'), vm = require('node:vm'), Module = require('node:module');
const load = Module._load;
Module._load = function(name, ...args) {
  if (/^(?:node:)?(?:http|https|net|tls|dns|dgram|child_process|worker_threads)$/.test(name))
    throw Error('network and subprocess are forbidden');
  return load.call(this, name, ...args);
};
const input = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const source = input.source;
const first = source.slice(source.indexOf('function beginDocumentAction()'), source.indexOf('function submitForm('));
const second = source.slice(source.indexOf('function escapeHtmlText('), source.indexOf('function completeDocument()'));
assert(first.includes('function endDocumentAction') && second.includes('function showCompleteConfirm'));
let calls=[], pending=[], modal=null, button=null, messages=[], timers=[];
const document = {
  querySelectorAll(){return [];},
  getElementById(id){return id==='completeConfirmModal'?modal:id==='forceCompleteBtn'?button:null;},
  createElement(){return {id:'',style:{},innerHTML:'',remove(){if(modal===this)modal=null;}};},
  body:{appendChild(value){modal=value;button={onclick:null,disabled:false};}}
};
const submitForm = function(){}; submitForm.pending=false; submitForm.completed=false;
const WMS={api:{postRaw(url,body){
  assert.equal(url,'/synthetic/7/complete');
  calls.push(JSON.parse(JSON.stringify(body)));
  return new Promise((resolve,reject)=>pending.push({resolve,reject}));
}}};
const ctx={document,submitForm,WMS,docType:input.doc,documentRoleAllowed:true,readonly:false,
 detailUrl:'/synthetic',showToast:(...args)=>messages.push(args),showDocumentCompletionIssue(){throw Error('unexpected completion issue');},
 setTimeout(fn,ms){timers.push({fn,ms});},window:{location:{href:'/synthetic-original'}},URLSearchParams};
vm.createContext(ctx);vm.runInContext(first+'\n'+second,ctx,{timeout:1000,contextCodeGeneration:{strings:false,wasm:false}});
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(r=>setImmediate(r));};
const reply=async(i,value)=>{pending[i].resolve(value);await settle();};
const bad='<img src=x onerror="alert(1)">';
(async()=>{
 vm.runInContext("runComplete('/synthetic/7/complete',false,7)",ctx);
 assert.deepEqual(calls,[{force:false}]);
 const initial={status:'confirm',msg:'未盘 2 行；动销 1 项；未知流水 1 条 '+bad,
                samples:[{code:bad,name:bad}],count:2,total:3};
 if(!['missing','blank','numeric','boolean'].includes(input.scenario))initial.confirmation_token='synthetic-token-1';
 if(input.scenario==='blank')initial.confirmation_token='   ';
 if(input.scenario==='numeric')initial.confirmation_token=123;
 if(input.scenario==='boolean')initial.confirmation_token=true;
 await reply(0,initial);
 assert(modal);assert.equal(calls.length,1,'人工确认前不得重发');
 assert(modal.innerHTML.includes('未盘 2 行；动销 1 项；未知流水 1 条'));
 assert(!modal.innerHTML.includes('<img'));assert(modal.innerHTML.includes('&lt;img'));
 assert(!modal.innerHTML.includes('synthetic-token-1'),'token 不应插入 HTML');
 if(input.scenario==='cancel'){
   modal.remove();assert.equal(calls.length,1);assert.equal(timers.length,0);return;
 }
 if(['missing','blank','numeric','boolean'].includes(input.scenario)){
   assert(modal.innerHTML.includes('盘点确认信息缺失'));
   assert(modal.innerHTML.includes('id="forceCompleteBtn" disabled'));
   if(button.onclick)button.onclick();await settle();
   assert.equal(calls.length,1,'缺少签名令牌时不得以旧 force 绕过');
   assert.equal(timers.length,0);return;
 }
 const firstButton=button;firstButton.onclick();firstButton.onclick();await settle();
 if(input.doc==='check')assert.deepEqual(calls[1],{force:true,confirmation_token:'synthetic-token-1'});
 else assert.deepEqual(calls[1],{force:true});
 assert.equal(calls.length,2,'重复点击必须受互斥保护');
 if(input.scenario==='changed'){
   await reply(1,{status:'confirm',msg:'风险已变化，未盘 3 行；动销 2 项',confirmation_token:'synthetic-token-2'});
   assert(modal);assert(modal.innerHTML.includes('风险已变化'));assert.equal(calls.length,2);
   button.onclick();await settle();assert.deepEqual(calls[2],{force:true,confirmation_token:'synthetic-token-2'});
   await reply(2,{status:'success',msg:'完成'});assert.equal(timers.length,1);
 } else {await reply(1,{status:'success',msg:'完成'});assert.equal(timers.length,1);}
})().catch(err=>{process.stderr.write(err.stack);process.exitCode=1;});
'''


class SyntheticConfirmation(unittest.TestCase):
    def run_case(self, doc, scenario):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        source = (ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
        env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny), \
             patch.object(socket, 'getaddrinfo', deny), patch.object(sqlite3, 'connect', deny):
            result = subprocess.run([node, '--disable-proto=throw', '-e', PROGRAM],
                                    input=json.dumps({'source': source, 'doc': doc, 'scenario': scenario}),
                                    env=env, text=True, capture_output=True, encoding='utf-8', timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_check_token_and_changed_risks(self):
        self.run_case('check', 'changed')

    def test_check_missing_token_does_not_force(self):
        for scenario in ('missing', 'blank', 'numeric', 'boolean'):
            with self.subTest(scenario=scenario):
                self.run_case('check', scenario)

    def test_cancel_keeps_draft(self):
        self.run_case('check', 'cancel')

    def test_transfer_force_remains_compatible(self):
        self.run_case('transfer', 'normal')


def test_confirmation_token_in_isolated_process():
    env = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR', 'PATH') if key in os.environ}
    result = subprocess.run([os.path.abspath(os.sys.executable), '-I', '-S', '-B', '-X', 'utf8', __file__],
                            env=env, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticConfirmation)
    if suite.countTestCases() != 4:
        raise SystemExit('synthetic test list must be nonempty and complete')
    raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
