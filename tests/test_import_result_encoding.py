"""Run import listeners and parse their actual HTML to preserve literal messages."""
import json
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def function_at(source, start):
    opening = source.index('{', start)
    depth = 0
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError('unclosed function')


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.tags = []; self.attrs = []; self.text = []
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        self.tags.append(tag); self.attrs.extend(attrs)
    def handle_data(self, data):
        self.text.append(data)


def execute(page, scenario, value, url='/opening_stock/7?q=A%26B'):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    path = 'app/static/js/pages/employee.js' if page == 'employee' else f'app/templates/{page}.html'
    source = (ROOT / path).read_text(encoding='utf-8')
    if page in ['employee', 'contract']:
        handler = function_at(source, source.index('function submitImport('))
        call = 'ctx.submitImport();'
    else:
        marker = "form.addEventListener('submit'" if page == 'batch_import' else "importForm.addEventListener('submit'"
        handler = 'var importHandler = ' + function_at(source, source.index('function(e)', source.index(marker))) + ';'
        call = 'ctx.importHandler.call(form,{preventDefault(){}});'
    app = (ROOT / 'app/static/js/app.js').read_text(encoding='utf-8')
    helper = function_at(app, app.index('function escapeHtml('))
    program = r'''
const assert=require('node:assert/strict'),vm=require('node:vm');const p=JSON.parse(process.argv[1]);let calls=0,timers=[];
const result={innerHTML:'',style:{}},btn={disabled:false,innerHTML:'Import',textContent:'Import'};
const form={id:'materialImportForm',action:'/fixture/import',dataset:{url:'/fixture/import'},querySelector:()=>btn,parentElement:{querySelector:()=>result}};
const response={status:['business','http'].includes(p.scenario)?'error':'success',msg:p.value,warnings:p.value,errors:[p.value],doc_no:p.value,detail_url:p.url};
const fetch=()=>{calls++;return p.scenario==='network'?Promise.reject({message:p.value}):Promise.resolve({ok:p.scenario!=='http',status:p.scenario==='http'?400:200,json:()=>Promise.resolve(response)});};
const document={getElementById:id=>id==='importBtn'?btn:id==='importResult'?result:form,querySelector:s=>s.startsWith('meta')?{content:'fixture-token'}:result};
const ctx={document,form,fetch,csrfFetch:fetch,FormData:class{},Headers,URL,Promise,location:{origin:'http://fixture.test',reload(){}},setTimeout:fn=>timers.push(fn),openingStockPrechecked:true,resetOpeningStockImport(){}};ctx.window=ctx;vm.createContext(ctx);vm.runInContext(p.helper,ctx);vm.runInContext(p.api,ctx);vm.runInContext(p.handler,ctx);
(async()=>{CALL;await new Promise(r=>setImmediate(r));assert.equal(calls,1);if(['batch_import','material'].includes(p.page))assert.equal(btn.disabled,false);process.stdout.write(JSON.stringify({html:result.innerHTML,timers:timers.length}));})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''.replace('CALL', call)
    payload = dict(page=page, scenario=scenario, value=value, url=url, helper=helper, handler=handler, api=(ROOT / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([node, '-e', program, json.dumps(payload)], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('page', ['employee', 'contract', 'material', 'batch_import'])
@pytest.mark.parametrize('scenario', ['success', 'business', 'http', 'network'])
@pytest.mark.parametrize('value', ['成功导入 1 条', '<img src=x onerror="alert(1)">', 'A&B <零件> "双引号" 与 \'单引号\''])
def test_import_messages_are_literal_in_every_result_branch(page, scenario, value):
    result = execute(page, scenario, value)
    markup = Markup(result['html'])
    assert set(markup.tags) <= {'div', 'i', 'a'}
    assert not any(k.startswith('on') or k == 'autofocus' for k, _ in markup.attrs)
    assert value in ''.join(markup.text)
    assert 'alert-success' in result['html'] if scenario == 'success' else 'alert-danger' in result['html']
    if scenario != 'success':
        assert result['timers'] == 0
    if scenario == 'success' and page == 'batch_import':
        assert ''.join(markup.text).count(value) == 4  # message, warning, document number, row error
        assert dict(markup.attrs)['href'] == '/opening_stock/7?q=A%26B'
        assert dict(markup.attrs)['target'] == '_blank'


@pytest.mark.parametrize('url,allowed', [('/opening_stock/7', True), ('http://fixture.test/opening_stock/7', True), ('javascript:alert(1)', False), ('https://other.test/', False), ('//other.test/', False), ('/\\other.test/', False), ('/\t/other.test/', False), ('http://[invalid', False)])
def test_import_document_links_stay_on_same_origin(url, allowed):
    parsed = Markup(execute('batch_import', 'success', 'literal', url)['html'])
    links = [v for k, v in parsed.attrs if k == 'href']
    assert links == ['/opening_stock/7'] if allowed else not links
