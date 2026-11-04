"""Execute the production revision transport with realistic Headers and URL APIs."""
from pathlib import Path
import subprocess


def test_revision_transport_stays_on_its_origin_and_document_family():
    source = Path(__file__).resolve().parents[1] / 'app/static/js/document-edit-guard.js'
    program = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict');
const listeners={};
const element={content:'revision-one',getAttribute(){return '/in_order/';}};
const ctx={Headers,URL,document:{querySelector(){return element;},addEventListener(n,f){listeners[n]=f;},createElement(){return {};}}};
ctx.location={href:'http://127.0.0.1:5097/in_order/3',origin:'http://127.0.0.1:5097'};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
const api=ctx.WmsDocumentRevision;
assert.equal(api.tokenFor('/in_order/3/update','POST'),'revision-one');
assert.equal(api.tokenFor('/in_order/3/update','GET'),'');
assert.equal(api.tokenFor('/out_order/3/update','POST'),'');
assert.equal(api.tokenFor('http://127.0.0.1:5097.evil.test/in_order/3/update','POST'),'');
assert.equal(api.tokenFor('//example.test/in_order/3/update','POST'),'');
let h=api.headers('/in_order/add','POST',{'X-CSRFToken':'csrf','X-Idempotency-Key':'request'});
assert.equal(h.get('X-WMS-Document-Revision'),'revision-one');assert.equal(h.get('X-CSRFToken'),'csrf');assert.equal(h.get('X-Idempotency-Key'),'request');
h=api.headers('/in_order/add','POST',new Headers({'X-WMS-Document-Revision':'explicit'}));assert.equal(h.get('X-WMS-Document-Revision'),'explicit');
api.acceptResponse({headers:new Headers()});assert.equal(element.content,'revision-one');
api.acceptResponse({headers:new Headers({'X-WMS-Document-Revision':'revision-two'})});assert.equal(element.content,'revision-two');
api.acceptResponse({getResponseHeader(){return 'revision-three';}});assert.equal(element.content,'revision-three');
const form={action:'/in_order/add',method:'post',querySelector(){return this.input;},appendChild(i){this.input=i;}};
listeners.submit({target:form});assert.equal(form.input.name,'document_revision');assert.equal(form.input.type,'hidden');assert.equal(form.input.value,'revision-three');
element.getAttribute=()=>'/subcontract/';assert.equal(api.tokenFor('/subcontract/issue/3/complete','POST'),'');
element.getAttribute=()=>'/subcontract_issue/,/subcontract/issue/';assert.equal(api.tokenFor('/subcontract/issue/3/complete','POST'),'revision-three');
element.content='';assert.equal(api.tokenFor('/subcontract_issue/3/complete','POST'),'');
'''
    result = subprocess.run(['node', '-e', program, str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_document_page_does_not_save_when_revision_asset_is_missing():
    root = Path(__file__).resolve().parents[1]
    base = (root / 'app/templates/base.html').read_text(encoding='utf-8')
    start = base.index('    (function() {\n        var csrfToken =')
    end = base.index('    })();', start) + len('    })();')
    program = r'''
const vm=require('vm'),assert=require('assert/strict');
const meta={content:'current-document-revision',getAttribute(){return '/in_order/';}},calls=[];
const ctx={Headers,document:{querySelector(s){return s.includes('csrf-token')?{content:'csrf'}:meta;}},location:{origin:'http://fixture',href:'http://fixture/in_order/1'},fetch(u,o){calls.push(u);return Promise.resolve({status:200});}};
ctx.window=ctx;vm.createContext(ctx);vm.runInContext(process.argv[1],ctx);
(async()=>{
 await assert.rejects(()=>ctx.fetch('/in_order/1/update',{method:'POST'}),/页面组件未加载完成/);
 assert.equal(calls.length,0,'missing revision dependency must not silently submit a web edit');
 await ctx.fetch('/in_order/1',{method:'GET'});assert.equal(calls.length,1);
 meta.content='';await ctx.fetch('/material/add',{method:'POST'});assert.equal(calls.length,2);
})().catch(e=>{process.stderr.write(e.stack);process.exitCode=1;});
'''
    result = subprocess.run(['node', '-e', program, base[start:end]], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
