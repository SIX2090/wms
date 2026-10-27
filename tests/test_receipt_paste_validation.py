import json
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('text,expected', [
    ('M1\t2\t0', [('M1','2','0.00')]),
    ('M1\t2\t', [('M1','2','12.00')]),
    ('M1\t-3\t5', []), ('M1\t2abc\t5', []),
    ('M1\t0.001\t5', []), ('M1\tInfinity\t5', []),
    ('M1\t2\tbad', []), ('M1\t2\t-1', []),
    ('M1\t2\t0.001', []), ('M350\t2\t5', [('M350','2','5.00')]),
])
def test_paste_numeric_validation_and_cache_misses(page, text, expected):
    actual = _run_paste(page, text)
    assert [(r['code'], float(r['qty']), r['price']) for r in actual['rows']] == [(c,float(q),p) for c,q,p in expected]
    if not expected:
        assert actual['removed'] is False
        assert actual['text'] == text
    if 'M350' in text:
        assert len(actual['calls']) == 1


@pytest.mark.parametrize('page', ['in', 'out'])
def test_partial_failure_keeps_only_failed_rows_for_retry(page):
    result = _run_paste(page, 'M1\t2\t0\nM1\t-1\t5')
    assert len(result['rows']) == 1
    assert result['text'] == 'M1\t-1\t5'
    assert not result['removed']


@pytest.mark.parametrize('page', ['in', 'out'])
def test_failed_lookup_does_not_mutate_rows_or_discard_paste(page):
    result = _run_paste(page, 'M350\t2\t5', fail=True)
    assert result['rows'] == []
    assert result['text'] == 'M350\t2\t5'
    assert not result['removed']
    assert result['disabled'] is False


@pytest.mark.parametrize('page', ['in', 'out'])
def test_repeated_click_and_cancel_during_lookup_do_not_duplicate_or_insert(page):
    result=_run_paste(page,'M350\t2\t0',repeat=True)
    assert len(result['rows'])==1 and len(result['calls'])==1
    cancelled=_run_paste(page,'M350\t2\t0',cancel=True)
    assert cancelled['rows']==[] and not cancelled['removed']


@pytest.mark.parametrize('page', ['shared','adjustment'])
@pytest.mark.parametrize('quantity', ['-1','2abc','0.001','Infinity'])
def test_adjacent_paste_forms_reject_malformed_quantity(page,quantity):
    result=_run_paste(page,'M1\t'+quantity)
    assert result['rows']==[] and not result['removed']


@pytest.mark.parametrize('page', ['shared','adjustment'])
def test_adjacent_paste_forms_resolve_uncached_material(page):
    result=_run_paste(page,'M350\t2\t备注')
    assert len(result['rows'])==1 and result['rows'][0]['code']=='M350'


def test_stocktake_paste_accepts_zero_actual_stock():
    result=_run_paste('shared','M1\t0',doc_type='check')
    assert len(result['rows'])==1 and float(result['rows'][0]['qty'])==0


@pytest.mark.parametrize('page', ['in', 'out'])
@pytest.mark.parametrize('value,expected', [('0.001','3'),('2.345','3'),('0.25','0.25'),('2','2.00')])
def test_bulk_quantity_preserves_valid_decimals_and_rejects_rounding_to_zero(page,value,expected):
    node=shutil.which('node')
    if not node: pytest.skip('Node.js required')
    source=(ROOT/f'app/templates/{page}_order_add.html').read_text(encoding='utf-8')
    function='function applyBatchUpdate()'+source.split('function applyBatchUpdate()',1)[1].split('\n</script>',1)[0]
    script=r'''
const fields={'.material-code':{value:'M1'},'.material-qty':{value:'3'}};
const row={querySelector(s){return fields[s];}};
const input={value:VALUE,focus(){}};
const document={getElementById(id){return {batchUpdateField:{value:'quantity'},batchUpdateValue:input,batchUpdateModal:{remove(){}}}[id];},querySelectorAll(){return [row];}};
function showToast(){} function alert(){} function calcAmount(){} function calcTotal(){}
''' .replace('VALUE',json.dumps(value))+function+"\napplyBatchUpdate();process.stdout.write(fields['.material-qty'].value);"
    r=subprocess.run([node,'-e',script],capture_output=True,text=True,encoding='utf-8',check=True)
    assert r.stdout==expected


def _run_paste(page, text, fail=False, repeat=False, cancel=False,doc_type='requisition'):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required')
    filename={'shared':'document_table_form.html','adjustment':'adjustment_add.html'}.get(page,f'{page}_order_add.html')
    source = (ROOT / 'app/templates'/filename).read_text(encoding='utf-8')
    start = source.index('function parsePastedData()')
    if source[start-6:start] == 'async ':
        start -= 6
    function = source[start:source.index('\nfunction findEmptyRow()',start)]
    script = r'''
const rows=[],calls=[]; let removed=false;
const pasteArea={value:TEXT,isConnected:true,readOnly:false};
const button={disabled:false}; const result={textContent:'',style:{}};
const modal={remove(){removed=true;},appendChild(){}};
const document={getElementById(id){return {pasteArea,pasteModal:modal,pasteImportResult:result}[id];},
 querySelector(s){return s.includes('last-child') ? rows.at(-1) : button;},createElement(){return result;}};
const materials=[{code:'M1',price:12}];
const docType=DOC_TYPE;
const WMS={api:{get:async url=>{calls.push(url);if(FAIL)throw new Error('network');if(CANCEL)pasteArea.isConnected=false;return [{code:'M350',price:12}];}}};
function showToast(){} function alert(){}
function findEmptyRow(){return null;}
function addNewRow(){const fields={};const r={dataset:{},querySelector(s){return fields[s] ||= {value:'',focus(){}};}};rows.push(r);return r;}
function fillMaterialFields(r,m){r.querySelector('.material-code').value=m.code;}
function findMaterialByCode(code){return materials.find(m=>m.code===code);}
function createRow(){return addNewRow();}
function calcAmount(){} function calcTotal(){} function calcRow(){} function updateCheckDiff(){}
function formatQtyTrim(q){return String(Number(q.toFixed(2)));}
function formatQty(q){return String(Number(q.toFixed(2)));}
''' .replace('TEXT', json.dumps(text)).replace('FAIL', json.dumps(fail)).replace('CANCEL',json.dumps(cancel)).replace('DOC_TYPE',json.dumps(doc_type)) + '\nconst window={WMS};\n' + (ROOT/'app/static/js/material-cache.js').read_text(encoding='utf-8') + function + r'''
const first=parsePastedData();
Promise.all([first,REPEAT ? parsePastedData() : Promise.resolve()]).then(()=>process.stdout.write(JSON.stringify({
 rows:rows.map(r=>({code:r.querySelector('.material-code').value,qty:r.querySelector('.material-qty').value||r.querySelector('.line-qty').value||r.querySelector('.adjust-qty').value||r.querySelector('.actual-stock').value,price:r.querySelector('.material-price').value})),
 calls,removed,text:pasteArea.value,disabled:button.disabled
}))).catch(err=>{process.stderr.write(String(err));process.exitCode=1;});
'''.replace('REPEAT',json.dumps(repeat))
    r = subprocess.run([node,'-e',script],text=True,encoding='utf-8',capture_output=True,check=True)
    return json.loads(r.stdout)


@pytest.fixture
def material_lookup_case(monkeypatch):
    import app as w
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.drop_all(); w.db.create_all()
        user=w.User(username='paste-fixture',password_hash='fixture-only',role='warehouse',status='active')
        w.db.session.add(user)
        w.db.session.add_all([w.Material(code='M1',name='物料1',price=12),w.Material(code='M10',name='物料10'),
                              w.Material(code='M%_',name='特殊编码'),w.Material(code='OFF',name='停用',status='inactive')])
        w.db.session.commit(); uid=user.id
        client=w.app.test_client()
        with client.session_transaction() as session: session.update(_user_id=str(uid),_fresh=True)
        yield client
        w.db.session.remove();w.db.drop_all()


def test_material_by_codes_exact_lookup_and_active_filter(material_lookup_case):
    r=material_lookup_case.get('/material/api/by_codes',query_string=[('code','M1'),('code','M%_'),('code','OFF'),('code','missing')])
    assert r.status_code == 200
    assert {m['code'] for m in r.get_json()['data']} == {'M1','M%_'}
    assert {key:r.get_json()[key] for key in ['total','page','page_size','total_pages']} == dict(total=2,page=1,page_size=4,total_pages=1)
    assert {m['code']:m['price'] for m in r.get_json()['data']}['M1'] == 12


def test_material_by_codes_rejects_empty_and_oversized_requests(material_lookup_case):
    assert material_lookup_case.get('/material/api/by_codes').status_code == 400
    assert material_lookup_case.get('/material/api/by_codes',query_string=[('code',f'M{i}') for i in range(201)]).status_code == 400
    assert material_lookup_case.get('/material/api/by_codes',query_string={'code':'X'*101}).status_code == 400


def test_material_by_codes_requires_login(material_lookup_case):
    with material_lookup_case.session_transaction() as session: session.clear()
    assert material_lookup_case.get('/material/api/by_codes?code=M1').status_code in (302,401)
