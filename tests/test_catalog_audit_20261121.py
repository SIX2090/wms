"""Catalog edits, Excel imports and exports must preserve the operator's intent."""
import re
import shutil
import subprocess
from pathlib import Path
from io import BytesIO

import app as w
from openpyxl import Workbook, load_workbook
from tests.test_material_status_toggle import _client, _seed, AJAX_HEADERS


def upload(client, url, *rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return client.post(url, data={'file': (stream, 'catalog.xlsx')}, headers=AJAX_HEADERS)


def test_material_edit_revision_preserves_status_and_price():
    client = _client()
    mid = _seed('CAT-EDIT', '档案', status='inactive')
    with w.app.app_context():
        user = w.User(username='catalog-operator', role='warehouse', password_hash='unused', must_change_password=False)
        w.db.session.add(user)
        w.db.session.commit()
        uid = user.id
    other = w.app.test_client()
    with other.session_transaction() as session:
        session['_user_id'], session['_fresh'] = str(uid), True
    prior = other.get(f'/material/{mid}').json['material']['edit_revision']
    data = client.get(f'/material/{mid}').json['material']
    form = {'code': data['code'], 'name': data['name'], 'edit_revision': data['edit_revision'], 'price': 39}
    assert client.post(f'/material/edit/{mid}', data=form).json['status'] == 'success'
    assert other.post(f'/material/edit/{mid}', data={**form, 'edit_revision': prior, 'price': 0}).status_code == 409
    assert client.post(f'/material/edit/{mid}', data={'code': 'CAT-EDIT', 'name': '档案'}).status_code == 409
    with w.app.app_context():
        m = w.db.session.get(w.Material, mid)
        assert (m.status, m.price) == ('inactive', 39)


def test_material_import_headers_and_skipped_relations():
    client = _client()
    headers = ['物料编码', '物料名称', '分类编码', '单位', '供应商', '单价']
    result = upload(client, '/material/import', headers, ['M1','好','C1','个','','3'],
                    ['M2','坏','错误类','错误单位','错误供方','待定'],
                    ['M3','好','重复行分类','个','','3'])
    assert result.json['count'] == 1
    with w.app.app_context():
        m = w.Material.query.one()
        assert (m.code, m.category.code, m.price) == ('M1','C1',3)
        assert w.MaterialCategory.query.count() == w.Unit.query.count() == 1
        assert w.Supplier.query.count() == 0
    assert upload(client, '/material/import', ['物料编码','物料代码','物料名称'], ['M','Z','重复列']).json['status'] == 'error'


def test_category_parent_limits_cache_and_material_export():
    client = _client()
    parent = client.post('/category/add', data={'code':'P','name':'父类'}).json['id']
    child = client.post('/category/add', data={'code':'C','name':'子类','parent_id':parent}).json['id']
    assert client.post(f'/category/edit/{child}', data={'code':'C','name':'子类','parent_id':'bad'}).status_code == 400
    assert client.get(f'/category/{child}').json['category']['parent_id'] == parent
    assert client.get('/api/options/category?kw=子类').json['total'] == 1
    assert client.post(f'/category/edit/{child}', data={'code':'C','name':'新类','parent_id':parent}).json['status'] == 'success'
    assert client.get('/api/options/category?kw=新类').json['total'] == 1
    _seed('Z','停用',status='inactive')
    _seed('A','启用')
    for status, expected in [('inactive',['Z']),('active',['A']),('all',['A','Z'])]:
        rows = load_workbook(BytesIO(client.get('/material/export?status='+status).data)).active.values
        assert [r[0] for r in list(rows)[1:]] == expected
    with w.app.app_context():
        w.set_system_setting('import_max_rows','1')
        w.set_system_setting('export_max_rows','1')
        w.db.session.commit()
    assert upload(client, '/category/import', ['分类编码','分类名称'], ['A','甲'], ['B','乙']).status_code == 400
    assert client.get('/category/export').status_code in (302,400)
    assert client.post('/material/add', data={'code':'A'*51,'name':'不应截断'}).status_code == 400


def test_selected_image_is_first_gallery_item_and_fresh_category_matches(monkeypatch):
    client = _client()
    mid = _seed('PHOTO','附图')
    monkeypatch.setattr(w, '_save_material_image_from_url', lambda material,url: ('uploads/chosen.jpg', ''))
    with w.app.app_context():
        monkeypatch.setattr(w,'startup_db_upgrade_disabled',lambda:False)
        w.ensure_material_category_tree_defaults()
        assert w.MaterialCategory.query.filter_by(code='400').one().name == '设备成品'
        w.db.session.add(w.MaterialImage(material_id=mid,image='uploads/previous.jpg',sort_order=0))
        w.db.session.commit()
    assert client.post(f'/material/{mid}/image_select',json={'image_url':'https://example.invalid/image'}).json['status']=='success'
    with w.app.app_context():
        images=w.MaterialImage.query.filter_by(material_id=mid).order_by(w.MaterialImage.sort_order,w.MaterialImage.id).all()
        assert [i.image for i in images]==['uploads/chosen.jpg','uploads/previous.jpg']
        assert w.db.session.get(w.Material,mid).image==images[0].image

def test_material_quick_selection_requires_an_exact_or_explicit_choice():
    root = Path(__file__).resolve().parents[1]
    script = (root / 'app/static/js/pages/material-list.js').read_text(encoding='utf8')
    template = (root / 'app/templates/material.html').read_text(encoding='utf8')
    for field in ('min_stock', 'max_stock', 'reorder_point'):
        assert re.search(r'id="edit_' + field + r'"[^>]*step="0\.01"', template)
    assert script.count('if (!commitQuickSelects(this)) return;') == 2
    functions = script[script.index('function commitQuickSelectInput'):script.index('function initQuickSelects')]
    program = """
const assert = require('node:assert/strict');
const hidden = {value:''}, input = {value:'轴承',focus(){}};
const document = {getElementById:()=>hidden};
const quickSelectTypeByHiddenId={rel:'category'};
const quickSelectData={category:[{id:1,name:'轴承甲',code:'A'},{id:2,name:'轴承乙',code:'B'}]};
const normalizeQuickText=s=>String(s||'').trim().toLowerCase(),quickSelectLabel=i=>i.name,showToast=()=>{};
const root={dataset:{hiddenId:'rel'},querySelector:()=>input,classList:{remove(){}}},form={querySelectorAll:()=>[root]};
""" + functions + """
assert.equal(commitQuickSelects(form),false);assert.equal(hidden.value,'');
input.value='未知';assert.equal(commitQuickSelects(form),false);
input.value='b';assert.equal(commitQuickSelects(form),true);assert.equal(hidden.value,2);
input.value='';assert.equal(commitQuickSelects(form),true);assert.equal(hidden.value,'');
"""
    subprocess.run([shutil.which('node'), '-e', program], check=True, timeout=10)
