"""Execute the BOM list controller: confirmation, single request and failure recovery."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('action', ['delete', 'calculate_cost', 'create_requisition'])
def test_perform_bom_action_confirms_and_recovers_from_failed_request(action):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    script = r'''
const fs=require('node:fs'),assert=require('node:assert/strict');
const source=fs.readFileSync(JSON.parse(process.argv[1]),'utf8');
let start=source.indexOf('async function performBomAction(');
assert.ok(start>=0,'Missing list action controller');
let depth=0,end=0;
for(let i=source.indexOf('{',start);i<source.length;i++){if(source[i]==='{')depth++;if(source[i]==='}'&&--depth===0){end=i+1;break;}}
let accept=false,requests=[],reloaded=0,toasts=[],fail=false;
const window={confirm:()=>accept,location:{href:'',reload(){reloaded++;}}};
const WMS={api:{post:async(url,data)=>{requests.push({url,data});if(fail)throw Error('网络失败');return{id:42};}}};
function showToast(message){toasts.push(message);}
eval(source.slice(start,end));
const action=process.argv[2],button={dataset:{bomAction:action,id:'12'},disabled:false};
(async()=>{
 await performBomAction(button);assert.equal(requests.length,0);assert.equal(button.disabled,false);
 accept=true;await performBomAction(button);assert.equal(requests.length,1);
 assert.equal(requests[0].url,'/bom/12/'+action);assert.deepEqual(requests[0].data,{});
 if(action==='create_requisition')assert.equal(window.location.href,'/requisition/42');
 else assert.equal(reloaded,1);
 assert.equal(button.disabled,false);
 fail=true;await performBomAction(button);assert.equal(button.disabled,false);assert.deepEqual(toasts,['网络失败']);
})().catch(e=>{console.error(e);process.exit(1);});
'''
    result = subprocess.run([node, '-e', script, json.dumps(str(ROOT / 'app/templates/bom.html')), action],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
