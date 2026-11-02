"""Run the actual reset handler without generating or changing credentials."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['duplicate', 'navigation', 'network', 'cancel', 'different-target'])
def test_reset_token_has_one_active_request_per_workstation(scenario):
    program = r'''
// WMS_AUDIT_TOKEN_UI: response labels only, no credential/server/device creation.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const p=JSON.parse(process.argv[1]),html=fs.readFileSync(p.root+'/app/templates/print_routing.html','utf8');
const start=html.indexOf('function resetToken('),end=html.indexOf('function deleteWs(',start);
assert(start>=0&&end>start);
const requests=[],alerts=[],errors=[];let reloads=0;
const c={confirm:()=>p.scenario!=='cancel',alert:text=>alerts.push(text),location:{reload(){reloads++;}},
 showToast:text=>errors.push(text),WMS:{api:{post(url,data){return new Promise((resolve,reject)=>requests.push({url,data,resolve,reject}));}}}};
vm.createContext(c);vm.runInContext(html.slice(start,end),c);
const settle=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));};
(async()=>{
 c.resetToken(7);await settle();
 if(p.scenario==='cancel'){assert.equal(requests.length,0);return;}
 assert.equal(requests.length,1);
 if(p.scenario==='duplicate'){c.resetToken(7);await settle();assert.equal(requests.length,1,'same target in-flight reset must not rotate twice');}
 if(p.scenario==='different-target'){c.resetToken(8);await settle();assert.equal(requests.length,2);assert(requests[1].url.includes('/8/'));}
 if(p.scenario==='network'){
   requests[0].reject(new Error('synthetic transport failure'));await settle();assert.equal(alerts.length,0);assert.equal(reloads,0);assert.equal(errors.length,1);
   c.resetToken(7);await settle();assert.equal(requests.length,2,'explicit confirmed retry must recover after failure');requests[1].resolve({token:'synthetic display label'});await settle();assert.equal(alerts.length,1);return;
 }
 requests[0].resolve({token:'synthetic display label'});await settle();assert.equal(alerts.length,1);assert.equal(reloads,1);
 if(p.scenario==='navigation'){c.resetToken(7);await settle();assert.equal(requests.length,1,'successful reset must remain locked while reload is pending');}
})().catch(error=>{console.error(error);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node
    result = subprocess.run([node, '-e', program, json.dumps({'root': ROOT.as_posix(), 'scenario': scenario})],
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
