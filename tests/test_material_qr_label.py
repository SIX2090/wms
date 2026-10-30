"""Unified label identity and read-only material-detail behavior, using an isolated DB."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS
from urllib.parse import parse_qs, urlsplit

import pytest

from app import app, db, Material, User, Warehouse
from services.material_label import material_label_qr, material_scan_code


@pytest.mark.parametrize('code', ['M001', '物料 / A&B+01', '000123'])
def test_material_label_qr(code, monkeypatch):
    monkeypatch.setenv('WMS_PUBLIC_URL', 'https://wms.example')
    with app.test_request_context('/'):
        qr = material_label_qr(code)
    assert qr['qrcode'].startswith('https://wms.example/mobile/material?')
    assert qr['qrcode_png'].startswith('iVBOR')
    assert material_scan_code(qr['qrcode']) == code
    assert material_scan_code(code) == code


@pytest.mark.parametrize('value', ['https://example.com/unrelated?code=M1', 'https://example.com/mobile/material?code=A&code=B'])
def test_material_scan_code(value):
    assert material_scan_code(value) != 'M1'
    assert material_scan_code(value) != 'A'


@pytest.fixture()
def material_fixture(monkeypatch):
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = User(username='qr-fixture', role='admin', password_hash='unused', must_change_password=False)
        material = Material(code='QR / A&B+01', name='长名称物料', brand='品牌甲', spec='规格甲', purpose='用途甲', remark='<b>备注</b>', stock=0)
        warehouse = Warehouse(code='QRWH', name='标签测试仓', status='active', is_default=True)
        db.session.add_all([user, material, warehouse])
        db.session.commit()
        uid, mid = user.id, material.id
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(uid)
        session['_fresh'] = True
    yield client, mid
    with app.app_context():
        assert db.session.get(Material, mid).stock == 0
        db.session.remove()
        db.drop_all()


def test_batch_label_serializes_brand_and_one_live_qr_identity(material_fixture):
    client, mid = material_fixture
    response = client.get(f'/label/batch_print?ids={mid}')
    assert response.status_code == 200
    rows = json.loads(re.search(r'var MATERIALS\s*=\s*(.*?);', response.text)[1])
    assert rows[0]['brand'] == '品牌甲'
    assert material_scan_code(rows[0]['qrcode']) == 'QR / A&B+01'
    assert rows[0]['qrcode_png'].startswith('iVBOR')


def test_detail_requires_login_and_displays_current_master_fields(material_fixture):
    client, mid = material_fixture
    anonymous = app.test_client().get('/mobile/material?code=QR%20%2F%20A%26B%2B01')
    assert anonymous.status_code == 302 and '/login' in anonymous.location
    response = client.get('/mobile/material', query_string={'code': 'QR / A&B+01'})
    assert response.status_code == 200
    for value in ['长名称物料', '品牌甲', '规格甲', '用途甲', '&lt;b&gt;备注&lt;/b&gt;', '标签测试仓']:
        assert value in response.text
    assert '<b>备注</b>' not in response.text
    for mode in ('in', 'out', 'query', 'check'):
        assert f'mode={mode}' in response.text
    assert client.get('/mobile/material?code=not-found').status_code == 404


def test_detail_url_works_in_mobile_and_pc_lookup(material_fixture):
    client, _ = material_fixture
    target = 'https://wms.example/mobile/material?code=QR+%2F+A%26B%2B01'
    for path, query in [('/mobile/api/stock_lookup', {'code': target, 'warehouse': 'QRWH'}),
                        ('/api/material/info', {'code': target, 'warehouse': 'QRWH'})]:
        response = client.get(path, query_string=query)
        assert response.status_code == 200
        assert response.json['data']['code'] == 'QR / A&B+01'


def test_scan_mode_prefills_the_code_without_submitting(material_fixture):
    client, _ = material_fixture
    response = client.get('/mobile/scan?mode=in&code=QR%20%2F%20A%26B%2B01')
    assert response.status_code == 200
    assert 'value="QR / A&amp;B+01"' in response.text


def test_public_qr_origin_can_be_selected_without_changing_material(material_fixture):
    client, mid = material_fixture
    response = client.get('/label/batch_print', query_string={'ids': mid, 'qr_base_url': 'https://warehouse.example'})
    rows = json.loads(re.search(r'var MATERIALS\s*=\s*(.*?);', response.text)[1])
    assert rows[0]['qrcode'].startswith('https://warehouse.example/mobile/material?')
    assert 'value="https://warehouse.example"' in response.text


def test_detail_and_scan_keep_the_selected_warehouse_and_never_guess_stock(material_fixture):
    from app import StockTransaction
    client, mid = material_fixture
    with app.app_context():
        first = Warehouse.query.filter_by(code='QRWH').one()
        second = Warehouse(code='QRWH2', name='第二仓', status='active')
        db.session.add(second)
        db.session.flush()
        db.session.add_all([
            StockTransaction(material_id=mid, warehouse_id=first.id, location=first.name, transaction_type='in', quantity=3),
            # Historical warehouse_id NULL, resolvable by warehouse name.
            StockTransaction(material_id=mid, location=second.name, transaction_type='in', quantity=7),
        ])
        db.session.commit()
    for wh, stock in [('QRWH', 3), ('QRWH2', 7)]:
        response = client.get('/mobile/material', query_string={'code': 'QR / A&B+01', 'warehouse': wh, 'embedded': 1})
        assert f'class="fs-3">{stock}.0</strong>' in response.text
        assert 'name="embedded" value="1"' in response.text
        scan = client.get('/mobile/scan', query_string={'code': 'QR / A&B+01', 'warehouse': wh})
        wh_name = '标签测试仓' if wh == 'QRWH' else '第二仓'
        assert re.search(r'id="warehouseInput"[^>]*value="' + wh_name + '"', scan.text)
    assert client.get('/mobile/material', query_string={'code': 'QR / A&B+01', 'warehouse': 'wrong'}).status_code == 400


@pytest.mark.parametrize('base', ['javascript:alert(1)', 'https://user:password@example.com', 'https://example.com/path', 'https://example.com?x=1'])
def test_bad_qr_address_has_a_visible_client_error(material_fixture, base):
    client, mid = material_fixture
    assert client.get('/label/batch_print', query_string={'ids': mid, 'qr_base_url': base}).status_code == 400


def test_official_renderer_uses_new_label_even_when_legacy_template_is_default():
    from jinja2 import Environment, FileSystemLoader
    from tests.test_batch_label_template_loading_runtime import Nodes, PROGRAM
    root = Path(__file__).resolve().parents[1]
    env = Environment(loader=FileSystemLoader(root / 'app/templates'), autoescape=True)
    material = dict(id=7, code='C/&', brand='品牌甲', name='<img src=x onerror=bad()>fixture material',
                    spec='型号/规格', qrcode_png='fixture-png', qrcode='https://wms.example/mobile/material?code=C%2F%26')
    html = env.get_template('print_batch_labels.html').render(
        materials=[material], materials_data=[material], default_material_qr=True,
        qr_public_base='https://wms.example', request=NS(args={}),
        current_user=NS(is_authenticated=True), config={}, url_for=lambda *a, **kw: '/fixture')
    branch = r'''
 if(p.action==='builtin_qr'){
  await finish(excel,{status:'success',templates:[]});
  await finish(list,{status:'success',templates:[{id:'A',name:'old default',width:90,height:50,is_default:true}]});
  assert.equal(ids.templateSelect.value,'');
  assert(!calls.some(c=>c.url===detail('A')),'official label must not silently load the old layout');
  const card=ids.labelsContainer.children[0];
  assert.equal(card.style.width,'90mm');assert.equal(card.style.height,'50mm');
  const left=card.children[0].children[0];
  assert.equal(left.children.length,3);assert.equal(left.children[0].children[0].textContent,'C/&');
  assert.equal(left.children[0].children[1].textContent,'品牌甲');
  assert.equal(left.children[1].textContent,'<img src=x onerror=bad()>fixture material');
  assert.equal(left.children[2].textContent,'型号/规格');
  const images=all(card,'img');assert.equal(images.length,1);assert.equal(images[0].src,'data:image/png;base64,fixture-png');
  select('A');await finish(detail('A'),{status:'success',template:template('A')});
  assert.equal(ids.labelsContainer.children[0].style.width,'40mm','custom template remains selectable');
  select('');assert.equal(ids.labelsContainer.children[0].style.width,'90mm');
  assert.equal(all(ids.labelsContainer,'img')[0].src,'data:image/png;base64,fixture-png');
  return;
 }
'''
    program = PROGRAM.replace(" if(p.action==='token')", branch + " if(p.action==='token')")
    assert branch in program
    payload = dict(action='builtin_qr', nodes=Nodes(html).nodes,
                   scripts=[body for attrs, body in re.findall(r'<script([^>]*)>(.*?)</script>', html, re.S) if 'src=' not in attrs],
                   api=(root / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr


def test_inbound_item_print_uses_material_identity_and_the_same_label(material_fixture):
    from app import InOrder, InOrderItem
    client, mid = material_fixture
    with app.app_context():
        order = InOrder(order_no='QR-FIXTURE', status='pending', warehouse='标签测试仓')
        db.session.add(order)
        db.session.flush()
        item = InOrderItem(id=17, in_order_id=order.id, material_id=mid, quantity=1, price=0, amount=0)
        db.session.add(item)
        db.session.commit()
    response = client.get('/print_in_order_labels?ids=17')
    assert response.status_code == 200
    rows = json.loads(re.search(r'var MATERIALS\s*=\s*(.*?);', response.text)[1])
    assert rows[0]['id'] == mid and rows[0]['brand'] == '品牌甲'
    assert material_scan_code(rows[0]['qrcode']) == 'QR / A&B+01'
    assert 'var builtinMaterialQrMode = true' in response.text
    assert f'name="ids" value="{mid}"' in response.text


@pytest.mark.parametrize('value', ['', None, 'missing', '内容<&>'])
def test_builtin_label_empty_fields_are_blank_in_real_renderer(value):
    from jinja2 import Environment, FileSystemLoader
    from tests.test_batch_label_template_loading_runtime import Nodes, PROGRAM
    root = Path(__file__).resolve().parents[1]
    material = dict(id=7, qrcode_png='fixture-png')
    if value != 'missing':
        material.update({key: value for key in ('code', 'brand', 'name', 'spec')})
    env = Environment(loader=FileSystemLoader(root / 'app/templates'), autoescape=True)
    html = env.get_template('print_batch_labels.html').render(
        materials=[material], materials_data=[material], default_material_qr=True,
        qr_public_base='', request=NS(args={}), current_user=NS(is_authenticated=True),
        config={}, url_for=lambda *a, **kw: '/fixture')
    expected = value if value == '内容<&>' else ''
    branch = r'''
 if(p.action==='empty_label'){
  await finish(excel,{status:'success',templates:[]});
  await finish(list,{status:'success',templates:[]});
  const card=ids.labelsContainer.children[0],left=card.children[0].children[0];
  assert.equal(card.style.width,'90mm');assert.equal(card.style.height,'50mm');
  const fields=[...left.children[0].children,left.children[1],left.children[2]];
  assert.equal(fields.length,4);
  for(const field of fields)assert.equal(field.textContent,p.expected);
  assert.equal(all(card,'img')[0].src,'data:image/png;base64,fixture-png');
  return;
 }
'''
    program = PROGRAM.replace(" if(p.action==='token')", branch + " if(p.action==='token')")
    payload = dict(action='empty_label', expected=expected, nodes=Nodes(html).nodes,
                   scripts=[body for attrs, body in re.findall(r'<script([^>]*)>(.*?)</script>', html, re.S) if 'src=' not in attrs],
                   api=(root / 'app/static/js/api.js').read_text(encoding='utf-8'))
    result = subprocess.run([shutil.which('node'), '-e', program], input=json.dumps(payload),
                            capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stderr
