"""Run the shared form's actual JS: successful requisitions open a fresh form."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('carry', [False, True])
@pytest.mark.parametrize('doc_type', ['requisition', 'transfer', 'check'])
@pytest.mark.parametrize('status', ['success', 'error', 'confirm', 'network_error'])
@pytest.mark.parametrize('mode', ['save', 'save_complete', 'complete', 'force'])
def test_requisition_completion_navigation(doc_type, status, mode, carry):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for browser callback execution')
    source = (ROOT / 'app/templates/document_table_form.html').read_text(encoding='utf-8')
    submit = 'function submitForm(completeAfterSave) {' + source.split('function submitForm(completeAfterSave) {', 1)[1].split('\nfunction escapeHtmlText', 1)[0]
    run = 'function runComplete(actionUrl, force, orderId) {' + source.split('function runComplete(actionUrl, force, orderId) {', 1)[1].split('\nfunction showCompleteConfirm', 1)[0]
    helpers = source[source.index('function beginDocumentAction()'):source.index('function submitForm(')]
    api = (ROOT / 'app/static/js/api.js').read_text(encoding='utf-8')
    complete = 'function completeDocument() {' + source.split('function completeDocument() {', 1)[1].split('\nfunction revertDocument', 1)[0]
    script = 'const carry=' + json.dumps(carry) + ';\n' + '''
let confirmed = 0, calls = [], issues = [];
const window = {location: {href: 'original'}};
const fields = {'order_id': {value:'7'}, 'order_no': {value:'REQ7'}, 'date': {value:'2026-10-15'}};
if (carry) Object.assign(fields, {warehouse_id:{value:'2'}, production_order:{value:'工单 & 1'}, picker:{value:'张三'}, purpose:{value:'生产'}, bom_id:{value:'9'}});
const document = {querySelector(s) {if(s.startsWith('meta'))return {content:'fixture-token'};return fields[s.match(/name="([^"]+)"/)[1]];},querySelectorAll(){return [];}};
const documentRoleAllowed = true;
const requisitionLocationRequired = false;
class FormData {}
const readonly = false, saveUrl = '/save', completeUrl = '/complete/0', detailUrl = '/detail';
function collectItems() {return {items:[{code:'M1',quantity:1}], invalidRows:[]};}
function collectHeader() {return {};}
function showToast() {}
function confirm() {return true;}
function setTimeout(fn) {fn();}
function showCompleteConfirm() {confirmed++;}
function showDocumentCompletionIssue(url,result) {issues.push({url,result});}
function fetch(url, options) {
    calls.push({url, body:JSON.parse(options.body)});
    if (url === '/save') return Promise.resolve({ok:true,status:200,json:() => Promise.resolve({status:'success',id:7})});
    if (status === 'network_error') return Promise.reject(new Error('network'));
    return Promise.resolve({ok:true,status:200,json:() => Promise.resolve({status})});
}
''' + api + '\nconst WMS=window.WMS;\n' + helpers + f'const docType={json.dumps(doc_type)}, status={json.dumps(status)};\n' + submit + run + complete
    script += {'save':'submitForm(false);', 'save_complete':'submitForm(true);', 'complete':'completeDocument();', 'force':"runComplete('/complete/7',true,7).catch(() => {});"}[mode]
    script += '\nsetImmediate(() => process.stdout.write(JSON.stringify({url:window.location.href, confirmed, calls, issues, locked:!!submitForm.completed})));'
    result = subprocess.run([node, '-e', script], text=True, encoding='utf-8', capture_output=True, check=True)
    actual = json.loads(result.stdout)
    if mode == 'save':
        assert actual['url'] == '/detail/7'
        assert len(actual['calls']) == 1
    elif status == 'success':
        if carry and doc_type == 'requisition':
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(actual['url'])
            assert parsed.path == '/requisition/add'
            assert parse_qs(parsed.query) == {'warehouse_id':['2'], 'production_order':['工单 & 1'], 'picker':['张三'], 'purpose':['生产'], 'bom_id':['9']}
        else:
            assert actual['url'] == ('/requisition/add' if doc_type == 'requisition' else '/detail/7')
    elif status == 'error':
        assert actual['url'] == 'original'
        assert len(actual['issues']) == 1
        assert actual['issues'][0]['url'] == '/detail/7'
        assert actual['locked'] is True
    else:
        assert actual['url'] == 'original'
        assert actual['confirmed'] == (1 if status == 'confirm' else 0)
        if status == 'network_error':
            assert len(actual['issues']) == 1
            assert actual['issues'][0]['url'] == '/detail/7'
            assert actual['locked'] is True
        else:
            assert actual['issues'] == []
            assert actual['locked'] is False
    if mode == 'force':
        assert actual['calls'][0]['body'] == {'force':True}
