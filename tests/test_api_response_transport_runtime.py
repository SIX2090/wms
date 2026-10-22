"""BUG-2026-10-22-015: binary responses keep the shared transport protections."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('body', ['json', 'form', 'empty'])
@pytest.mark.parametrize('scenario', ['binary', 'json', 'http_json', 'http_html', 'unauthorized', 'expired', 'network', 'abort'])
def test_response_mode_keeps_body_metadata_and_common_errors(body, scenario):
    run('postResponse', body, scenario)


@pytest.mark.parametrize('method', ['post', 'postRaw'])
@pytest.mark.parametrize('scenario', ['json', 'business', 'http_json', 'http_html', 'unauthorized', 'expired'])
def test_existing_json_modes_still_unwrap_or_keep_root(method, scenario):
    run(method, 'json', scenario)


def run(method, body, scenario):
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm'),p=JSON.parse(process.argv[1]);
let calls=[],jsonReads=0,blobReads=0,confirms=0;
const root={status:p.scenario==='business'?'error':'success',msg:'服务器原因',data:{id:7}};
const status=p.scenario==='http_json'?409:p.scenario==='http_html'?503:p.scenario==='unauthorized'?401:p.scenario==='expired'?419:200;
const bytes=new Uint8Array([80,75,3,4,0,255]);
const response={status,ok:status===200,headers:new Headers({'Content-Type':p.scenario==='binary'?'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':'application/json','Content-Disposition':"attachment; filename*=UTF-8''%E5%85%A5%E5%BA%93.xlsx"}),
json(){jsonReads++;return p.scenario==='http_html'||p.scenario==='binary'?Promise.reject(SyntaxError('not json')):Promise.resolve(root);},
blob(){blobReads++;return Promise.resolve(new Blob([bytes]));}};
const signal=new AbortController().signal;
const doc={querySelector:s=>s.includes('meta')?{content:'response-csrf'}:null};
const context={document:doc,FormData,Headers,Blob,location:{href:'original'},confirm(){confirms++;return true;},setTimeout(){},
fetch(url,options){calls.push({url,options});if(p.scenario==='network')return Promise.reject(Error('offline'));if(p.scenario==='abort')return Promise.reject(new DOMException('cancelled','AbortError'));return Promise.resolve(response);}};
context.window=context;vm.createContext(context);vm.runInContext(p.api,context);
(async()=>{
 const data=p.body==='empty'?undefined:p.body==='form'?new FormData():{ids:[1,2],remark:'中文&+'};
 if(p.body==='form'){data.append('id','1');data.append('id','2');}
 let result,error;try{result=await context.WMS.api[p.method]('/download',data,{signal,headers:{'X-Custom':'kept'}});}catch(e){error=e;}
 assert.equal(calls.length,1);const options=calls[0].options;
 assert.equal(options.method,'POST');assert.equal(options.credentials,'same-origin');assert.equal(options.headers['X-CSRFToken'],'response-csrf');
 assert.equal(options.headers['X-Requested-With'],'XMLHttpRequest');assert.equal(options.headers['X-Custom'],'kept');assert.equal(options.signal,signal);
 if(p.body==='json'){assert.equal(options.headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(options.body),data);}
 else{assert.equal(options.headers['Content-Type'],undefined);assert.equal(options.body,data);if(data)assert.deepEqual(data.getAll('id'),['1','2']);}
 if(['unauthorized','expired'].includes(p.scenario)){assert.equal(error.code,'SESSION_EXPIRED');assert.equal(jsonReads,0);assert.equal(confirms,1);assert.equal(context.location.href,'/login');}
 else if(p.scenario==='http_json'){assert.equal(error.code,'HTTP_ERROR');assert.equal(error.status,409);assert.equal(error.message,'服务器原因');assert.equal(jsonReads,1);}
 else if(p.scenario==='http_html'){assert.equal(error.code,'HTTP_ERROR');assert.equal(error.status,503);assert.match(error.message,/503/);assert.equal(jsonReads,1);}
 else if(p.scenario==='network'){assert.equal(error.message,'offline');assert.equal(jsonReads,0);}
 else if(p.scenario==='abort'){assert.equal(error.name,'AbortError');assert.equal(jsonReads,0);}
 else if(p.method==='postResponse'){
  assert.equal(error,undefined);assert.equal(result,response);assert.equal(jsonReads,0);assert.equal(blobReads,0);
  assert.equal(result.headers.get('Content-Disposition'),"attachment; filename*=UTF-8''%E5%85%A5%E5%BA%93.xlsx");
  if(p.scenario==='binary'){assert.deepEqual(new Uint8Array(await(await result.blob()).arrayBuffer()),bytes);assert.equal(blobReads,1);}
  else{assert.equal(await result.json(),root);assert.equal(jsonReads,1);}
 }else if(p.method==='post'&&p.scenario==='business'){assert.equal(error.code,'BUSINESS_ERROR');assert.equal(error.message,'服务器原因');}
 else{assert.equal(error,undefined);assert.equal(result,p.method==='post'?root.data:root);assert.equal(jsonReads,1);}
 assert.equal(blobReads,p.scenario==='binary'?1:0);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    node = shutil.which('node')
    assert node, 'Node required for shared transport regression'
    env = dict(os.environ, NODE_OPTIONS='--max-old-space-size=64')
    payload = dict(method=method, body=body, scenario=scenario,
                   api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program, json.dumps(payload)],
                            capture_output=True, encoding='utf-8', env=env, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
