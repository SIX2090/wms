"""BUG-2026-10-24-010: actual GET preview must use selected material and saved layout."""
import json
import re
from html import unescape

import pytest


@pytest.fixture
def preview(monkeypatch):
    from app import app, db, User, Material, Unit, MaterialCategory, Supplier, LabelTemplate
    monkeypatch.setitem(app.config, 'TESTING', True)
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', False)
    with app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.session.remove()
        db.drop_all()
        db.create_all()
        user = User(username='preview-test', password_hash='unused', role='admin', must_change_password=False)
        unit = Unit(code='U', name='套')
        category = MaterialCategory(code='C', name='五金')
        supplier = Supplier(code='S', name='供应商甲')
        db.session.add_all([user, unit, category, supplier])
        db.session.flush()
        first = Material(code='FIRST', name='第一物料')
        second = Material(code='P/#?&02', name='<b>第二物料</b>', spec='规格&乙', unit_id=unit.id,
                          category_id=category.id, supplier_id=supplier.id, stock=7, price=0)
        template = LabelTemplate(name='预览测试', rows=1, cols=1, width=60, height=40,
                                 layout=json.dumps({'0-0': {'field': 'name'}}))
        db.session.add_all([first, second, template])
        db.session.commit()
        ids = (user.id, second.id, template.id)
    client = app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids[0])
        session['_fresh'] = True

    def render(layout=None, query=None):
        if layout is not None:
            with app.app_context():
                row = db.session.get(LabelTemplate, ids[2])
                row.layout = layout if isinstance(layout, str) else json.dumps(layout)
                db.session.commit()
        response = client.get(f'/label_template/{ids[2]}/preview', query_string=query)
        return response

    yield render, ids[1], client, ids[2]
    with app.app_context():
        db.session.remove()
        db.drop_all()


def _values(response):
    assert response.status_code == 200, response.get_data(as_text=True)[:500]
    return [unescape(v) for v in re.findall(r'<span class="cell-value">(.*?)</span>', response.get_data(as_text=True))]


@pytest.mark.parametrize('field,expected', [
    ('code', 'P/#?&02'), ('name', '<b>第二物料</b>'), ('spec', '规格&乙'),
    ('unit', '套'), ('unit_name', '套'), ('category', '五金'), ('category_name', '五金'),
    ('supplier', '供应商甲'), ('supplier_name', '供应商甲'), ('stock', '7.0'), ('price', '0.0'),
])
def test_selected_material_fields(preview, field, expected):
    render, mid, _, _ = preview
    response = render({'0-0': {'field': field}}, {'material_id': mid})
    assert _values(response) == [expected]
    html = response.get_data(as_text=True)
    assert re.search(r'<option value="' + str(mid) + r'"\s+selected', html)
    assert '<b>第二物料</b>' not in html


@pytest.mark.parametrize('kind', ['cells', 'legacy_list', 'mixed'])
def test_saved_designer_layout(preview, kind):
    render, mid, _, _ = preview
    cells = [{'row': 0, 'col': 0, 'field': 'name'}]
    layout = cells if kind == 'legacy_list' else {'cells': cells}
    if kind == 'mixed':
        layout['0-0'] = {'field': 'code'}
    assert _values(render(layout, {'material_id': mid})) == ['<b>第二物料</b>']


@pytest.mark.parametrize('field,path', [('barcode', '/api/barcode/'), ('qrcode', '/api/qrcode/')])
def test_image_uses_selected_code_and_encoded_url(preview, field, path):
    render, mid, _, _ = preview
    response = render({'0-0': {'field': field}}, {'material_id': mid})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    sources = [unescape(src) for src in re.findall(r'<img src="([^"]+)"', html) if path in src]
    assert len(sources) == 1
    assert sources[0].startswith(path + 'P/%23%3F&02')


@pytest.mark.parametrize('query', [None, {'material_id': ''}])
def test_default_is_explicit_sample(preview, query):
    render, _, _, _ = preview
    response = render(query=query)
    assert _values(response) == ['示例物料', '另一个物料']
    assert re.search(r'<option value=""\s+selected[^>]*>使用示例数据', response.get_data(as_text=True))


@pytest.mark.parametrize('value,status', [('abc', 400), ('-1', 400), ('0', 400), ('1.5', 400), ('99999', 404)])
def test_invalid_selection_never_prints_sample(preview, value, status):
    render, _, _, _ = preview
    assert render(query={'material_id': value}).status_code == status


def test_content_is_inside_base_body(preview):
    render, mid, _, _ = preview
    html = render(query={'material_id': mid}).get_data(as_text=True)
    assert html.count('<body') == 1
    assert html.count('</head>') == 1
    assert html.index('<body') < html.index('class="preview-container"') < html.rindex('</body>')


def test_missing_relations_and_literal_text(preview):
    render, mid, _, _ = preview
    from app import app, db, Material
    with app.app_context():
        material = db.session.get(Material, mid)
        material.unit_id = material.category_id = material.supplier_id = None
        db.session.commit()
    assert _values(render({'0-0': {'field': 'unit'}}, {'material_id': mid})) == ['']
    assert _values(render({'cells': [{'row': 0, 'col': 0, 'text': '<img onerror=x>'}]}, {'material_id': mid})) == ['<img onerror=x>']


def test_anonymous_still_requires_login(preview):
    _, mid, client, tid = preview
    with client.session_transaction() as session:
        session.clear()
    response = client.get(f'/label_template/{tid}/preview?material_id={mid}')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_date_and_empty_inventory_are_rendered(preview):
    from datetime import datetime
    render, mid, _, _ = preview
    assert _values(render({'0-0': {'field': 'date'}}, {'material_id': mid})) == [datetime.now().strftime('%Y-%m-%d')]
    from app import app, db, Material
    with app.app_context():
        Material.query.delete()
        db.session.commit()
    assert _values(render({'0-0': {'field': 'name'}})) == ['示例物料', '另一个物料']


@pytest.mark.parametrize('layout', ['broken json', 'null', '42', '{}'])
def test_invalid_or_empty_layout_degrades_to_grid(preview, layout):
    render, mid, _, _ = preview
    response = render(layout, {'material_id': mid})
    assert response.status_code == 200
    assert '1-1</span>' in response.get_data(as_text=True)


def test_merged_columns_and_row_height(preview):
    render, mid, _, tid = preview
    from app import app, db, LabelTemplate
    with app.app_context():
        template = db.session.get(LabelTemplate, tid)
        template.rows, template.cols = 2, 2
        db.session.commit()
    response = render({'rowHeights': [60, 30], 'cells': [
        {'row': 0, 'col': 0, 'field': 'name', 'colSpan': 2},
        {'row': 1, 'col': 0, 'field': 'code'},
    ]}, {'material_id': mid})
    html = response.get_data(as_text=True)
    assert 'colspan="2"' in html
    assert html.count('<td') == 3
    heights = [float(x) for x in re.findall(r'<tr style="height: ([0-9.]+)px;', html)]
    assert len(heights) == 2 and 1.8 < heights[0] / heights[1] < 2.2


def test_get_does_not_change_material_or_layout(preview):
    render, mid, _, tid = preview
    from app import app, db, Material, LabelTemplate
    def snapshot():
        with app.app_context():
            return ([tuple(getattr(m, c.name) for c in Material.__table__.columns) for m in Material.query.all()],
                    db.session.get(LabelTemplate, tid).layout)
    before = snapshot()
    assert render(query={'material_id': mid}).status_code == 200
    assert snapshot() == before


def test_selector_can_switch_back_to_sample(preview):
    import shutil
    import subprocess
    render, mid, _, tid = preview
    html = render(query={'material_id': mid}).get_data(as_text=True)
    handler = re.search(r'function changeMaterial\(\) \{(.*?)\n        \}', html, re.S).group(0)
    program = "const assert=require('node:assert/strict'); let value=''; " + \
        "global.document={getElementById:()=>({value})}; global.window={location:{}}; " + handler + \
        f"; changeMaterial(); assert.equal(window.location.href, '/label_template/{tid}/preview'); " + \
        f"value='{mid}'; changeMaterial(); assert.equal(window.location.href, '/label_template/{tid}/preview?material_id={mid}');"
    result = subprocess.run([shutil.which('node'), '-e', program], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
