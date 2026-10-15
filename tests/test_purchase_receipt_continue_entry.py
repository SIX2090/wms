"""Execute the completion callbacks: only successful purchase receipts open a fresh form."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('page', ['add', 'detail'])
@pytest.mark.parametrize('kind', ['采购入库', '产品入库', '其他入库'])
@pytest.mark.parametrize('status', ['success', 'error', 'warning'])
def test_completion_navigation(page, kind, status):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required to execute browser completion callbacks')
    source = (ROOT / f'app/templates/in_order_{page}.html').read_text(encoding='utf-8')
    if page == 'add':
        callback = source.split('.then(completeRes => {', 1)[1].split('\n            });', 1)[0]
        action = f'const completeRes = response; {callback}'
    else:
        function = source.split('function completeOrder(id, force) {', 1)[1].split('\nfunction showAnomalyWarning', 1)[0]
        function = function.replace("{{ (order.business_type or '采购入库')|tojson }}", json.dumps(kind))
        action = 'function completeOrder(id, force) {' + function + '\ncompleteOrder(7, false);'
    script = '''
let cleared = 0, reloaded = 0, warned = 0;
const window = {location: {href: 'original'}};
const location = {reload() {reloaded++;}};
function clearDraft() {cleared++;}
function showToast() {}
function alert() {}
function setTimeout(fn) {fn();}
function showAnomalyWarning() {warned++;}
function showConfirm() {return Promise.resolve(true);}
function csrfFetch() {return Promise.resolve({json: () => Promise.resolve(response)});}
const data = {id: 7};
const saveAndNew = false;
const returnAddUrl = '/in_order/add?type=product';
''' + f'const businessType = {json.dumps(kind)}; const response = {json.dumps(dict(status=status, anomalies=[]))};\n' + action + '''
setImmediate(() => process.stdout.write(JSON.stringify({url: window.location.href, cleared, reloaded, warned})));
'''
    result = subprocess.run([node, '-e', script], text=True, encoding='utf-8', capture_output=True, check=True)
    actual = json.loads(result.stdout)
    if status == 'success' and kind == '采购入库':
        assert actual['url'] == '/in_order/add'
        assert actual['cleared'] == (1 if page == 'add' else 0)
    elif page == 'add':
        assert actual['url'] == '/in_order/7'
        assert actual['cleared'] == (1 if status == 'success' else 0)
    else:
        assert actual['url'] == 'original'
        assert actual['reloaded'] == (1 if status == 'success' else 0)
        assert actual['warned'] == (1 if status == 'warning' else 0)
