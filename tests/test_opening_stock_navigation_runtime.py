"""BUG-2026-10-30-006: execute the page navigator against its API contract."""
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest


SOURCE = Path(__file__).resolve().parents[1] / 'app/static/js/pages/opening-stock.js'


@pytest.mark.parametrize('doc_id,target,expected_id,expected_message', [
    (22, 'prev', 11, None),
    (22, 'next', 33, None),
    (11, 'next', 22, None),
    (33, 'prev', 22, None),
    (11, 'prev', None, '已经是首张单据'),
    (33, 'next', None, '已经是末张单据'),
    (22, 'first', 11, None),
    (22, 'last', 33, None),
    (None, 'prev', 33, None),
    (None, 'next', 11, None),
])
def test_navigation_uses_current_document(doc_id, target, expected_id, expected_message):
    node = shutil.which('node')
    assert node, 'Node is required to verify the actual frontend navigator'
    match = re.search(r'^function navigateOpeningDoc\(target\) \{[\s\S]*?^}',
                      SOURCE.read_text(encoding='utf-8'), re.M)
    assert match
    state = json.dumps({'docId': doc_id, 'target': target})
    script = '''
const state = STATE;
const OPENING_DOC = state.docId === null ? null : {id: state.docId};
const window = {location: {href: 'unchanged'}};
const toasts = [];
const calls = [];
const showToast = (msg, type) => toasts.push({msg, type});
const WMS = window.WMS = {api: {get(url) {
    calls.push(url);
    const query = new URL(url, 'http://qa.invalid').searchParams;
    const current = Number(query.get('current_id'));
    const ids = [11, 22, 33];
    const index = ids.indexOf(current);
    return Promise.resolve({status: 'success', total: ids.length,
        first_id: ids[0], last_id: ids[2],
        prev_id: index > 0 ? ids[index - 1] : null,
        next_id: index >= 0 && index < 2 ? ids[index + 1] : null});
}}};
FUNCTION
navigateOpeningDoc(state.target);
setImmediate(() => process.stdout.write(JSON.stringify({calls, toasts, href: window.location.href})));
'''.replace('STATE', state).replace('FUNCTION', match.group(0))
    result = subprocess.run([node, '-e', script], capture_output=True, text=True,
                            encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stderr
    actual = json.loads(result.stdout)
    suffix = '' if doc_id is None else '?current_id=' + str(doc_id)
    assert actual['calls'] == ['/api/document_navigation/opening_stock' + suffix]
    assert actual['href'] == ('unchanged' if expected_id is None
                              else '/opening_stock/' + str(expected_id))
    assert actual['toasts'] == ([] if expected_message is None
                                 else [{'msg': expected_message, 'type': 'info'}])
