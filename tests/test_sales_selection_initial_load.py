"""BUG-2026-11-01-027: execute the page's scripts in rendered layout order."""
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
import subprocess

import pytest
from tests.test_document_create_number_conflicts import case  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


class Scripts(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.scripts = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.current = dict(attrs, text='')

    def handle_data(self, data):
        if self.current is not None:
            self.current['text'] += data

    def handle_endtag(self, tag):
        if tag == 'script':
            self.scripts.append(self.current)
            self.current = None


@pytest.mark.parametrize('embedded', [False, True])
@pytest.mark.parametrize('outcome', ['success', 'network'])
def test_first_load_has_api_before_query_and_failure_remains_retryable(case, embedded, outcome):
    client = case[0][0]
    response = client.get('/sales/outbound_selection'+('?embedded=1' if embedded else ''))
    assert response.status_code == 200
    scripts = Scripts(response.get_data(as_text=True)).scripts
    selected = []
    for script in scripts:
        if '/js/api.js' in script.get('src', ''):
            selected.append((ROOT/'app/static/js/api.js').read_text(encoding='utf-8'))
        elif 'let selectable =' in script['text']:
            selected.append(script['text'])
    assert len(selected) == 2
    program = r'''
const vm=require('node:vm'),assert=require('node:assert/strict'),p=JSON.parse(process.argv[1]);
const fields={},requests=[];let failed=p.outcome==='network';
const element=id=>fields[id]||(fields[id]={value:'',textContent:'',innerHTML:'',checked:false,
 classList:{remove(){},add(){}},addEventListener(){}});
const doc={getElementById:element,querySelector:s=>s==='meta[name="csrf-token"]'?{content:'fixture'}:null,
 querySelectorAll:()=>[],createElement:()=>({textContent:'',innerHTML:''})};
const ctx={document:doc,URLSearchParams,Headers,FormData,location:{href:'original'},confirm:()=>false,
 fetch:(url,opts)=>{requests.push({url,opts});return failed?Promise.reject(Error('offline')):
 Promise.resolve({ok:true,status:200,json:()=>Promise.resolve({status:'success',items:[]})});}};
ctx.window=ctx;vm.createContext(ctx);
for(const script of p.scripts)vm.runInContext(script,ctx);
(async()=>{await new Promise(r=>setImmediate(r));assert.equal(requests.length,1);
assert(requests[0].url.startsWith('/api/sales_order/selectable'));
if(failed){assert(element('itemsBody').innerHTML.includes('失败'));failed=false;await ctx.loadSelectable();}
assert(!element('itemsBody').innerHTML.includes('正在加载'));assert.equal(element('entryStatus').textContent,'');
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run([shutil.which('node'), '-e', program,
                             json.dumps(dict(scripts=selected, outcome=outcome))],
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
