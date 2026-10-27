"""Execute actual quality-page comparison and production HTTP parsing."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_in_order_material_search_runtime import function

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('scenario', ['html502', 'html200', 'success'])
def test_quality_compare_transport_runtime(scenario):
    html = (ROOT/'app/templates/ai_business_quality.html').read_text(encoding='utf-8')
    helper = function(html, 'qualityRequestError') if 'function qualityRequestError' in html else ''
    compare = 'async ' + function(html, 'loadVersionComparison')
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(require('node:fs').readFileSync(0,'utf8'));
const messages=[],calls=[],nodes={};let rendered=0;
const document={getElementById:id=>nodes[id]??=( {value:id.includes('threshold')?'0.1':'',textContent:''}),querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:null};
const ctx={document,FormData:class{},console,showToast:(m,t)=>messages.push(m),renderVersionComparison:()=>rendered++,
fetch:async(url,options)=>{calls.push({url,options});return {ok:p.scenario!=='html502',status:p.scenario==='html502'?502:200,
json:async()=>{if(p.scenario!=='success')throw new SyntaxError('Unexpected token <');return {status:'ok',comparison:{}};}};}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.helper+'\n'+p.compare,ctx);
(async()=>{await ctx.loadVersionComparison();assert.equal(calls.length,1);
assert.equal(calls[0].options.headers['X-CSRFToken'],'fixture-token');
if(p.scenario==='success'){assert.equal(rendered,1);assert.equal(messages.length,0);}
else {assert.equal(rendered,0);assert(messages.some(m=>/服务器/.test(m)),messages.join('|'));assert(!messages.some(m=>/Unexpected/.test(m)));}
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program],
        input=json.dumps({'scenario':scenario,'api':(ROOT/'app/static/js/api.js').read_text(encoding='utf-8'),
                         'helper':helper,'compare':compare}),
        capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
