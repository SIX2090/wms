"""Regressions from the isolated real-browser audit; never use production data."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import io
import shutil
import subprocess

from flask import url_for
from openpyxl import load_workbook
import pytest
import app as wms

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def case(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()
        wms.db.create_all()
        user = wms.User(username='SYNTHETIC-AUDIT', role='admin',
                        password_hash='unusable-test-hash', must_change_password=False)
        wh = wms.Warehouse(code='AUD-W', name='审计仓', status='active', is_default=True)
        unit = wms.Unit(code='AUD-U', name='个')
        wms.db.session.add_all([user, wh, unit])
        wms.db.session.flush()
        material = wms.Material(code='AUD-M', name='审计物料', unit_id=unit.id,
                                stock=0, min_stock=5, max_stock=500, price=11)
        wms.db.session.add(material)
        wms.db.session.commit()
        ids = user.id, wh.id, material.id
    client = wms.app.test_client()
    with client.session_transaction() as session:
        session['_user_id'] = str(ids[0])
        session['_fresh'] = True
    yield client, ids
    with wms.app.app_context():
        wms.db.session.remove()
        wms.db.drop_all()


@pytest.mark.parametrize('kind', ['', 'sale', 'purchase_return'])
def test_outbound_canonical_add_url_preserves_business_type(case, kind):
    client, _ = case
    with wms.app.test_request_context():
        link = url_for('out_order_add_page', **({'type': kind} if kind else {}))
    assert link.startswith('/out_order/add')
    response = client.get(link)
    assert response.status_code == 200
    expected = {'': '新增领料单', 'sale': '新增销售出库单', 'purchase_return': '新增采购退货出库单'}[kind]
    assert expected in response.get_data(as_text=True)


@pytest.mark.parametrize('stock,minimum', [(0, 5), (4, 5), (-1, 0)])
def test_health_redline_without_outbound_history_is_not_healthy(case, stock, minimum):
    with wms.app.app_context():
        material = wms.db.session.get(wms.Material, case[1][2])
        material.stock, material.min_stock = stock, minimum
        wms.db.session.commit()
        result = wms._ai_inventory_health_report()
        row = result['rows'][0]
        assert row['risk_type'] == 'shortage'
        assert row['health_score'] < 80
        assert '库存状态良好' not in row['ai_suggestion']
        assert '无法估算' in row['ai_suggestion']
        assert result['summary']['healthy'] == 0
        assert not wms._ai_inventory_health_report(risk_filter='healthy')['rows']
        assert wms.StockTransaction.query.count() == 0


def test_batch_count_uses_counted_metadata_including_zero(case):
    with wms.app.app_context():
        rows = [SimpleNamespace(material_id=i, difference=0, counted_at=None, counted_by=None)
                for i in range(1, 36)]
        rows[0].counted_at = datetime.now()
        rows[1].counted_by = case[1][0]
        check = SimpleNamespace(id=999, items=rows, frozen_at=None)
        meta = wms._build_check_batch_meta(check)
        assert meta['material_count'] == 35
        assert meta['counted_count'] == 2
        assert meta['uncounted_count'] == 33


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('template_mode', ['', '&template_mode=1'])
def test_stock_prices_match_switch_on_screen_and_default_template(case, enabled, template_mode):
    client, ids = case
    with wms.app.app_context():
        wms.set_system_setting('price_dimension_enabled', '1' if enabled else '0')
        import doc_print_excel as dpe
        path = dpe._builtin_template_abspath(wms.app.static_folder, 'stock_query')
        template = wms.ExcelPrintTemplate(name='审计默认模板', target_type='list', target_code='stock_query',
            template_type='excel', excel_template_path='/static/uploads/print_templates/' + Path(path).name,
            is_default=True)
        wms.db.session.add(template)
        wms.db.session.commit()
    html = client.get('/stock_query?warehouse_id=' + str(ids[1])).get_data(as_text=True)
    assert ('¥11.00' in html) is enabled
    response = client.get('/report/stock/print?warehouse_id=' + str(ids[1]) + template_mode)
    assert response.status_code == 200
    workbook = load_workbook(io.BytesIO(response.data))
    values = [cell.value for row in workbook.active for cell in row]
    assert ('单价' in values) is enabled
    assert ('库存金额' in values) is enabled
    assert 'AUD-M' in values
    preview = client.get('/report/stock/print_preview?warehouse_id=' + str(ids[1])).get_data(as_text=True)
    assert ('库存金额' in preview) is enabled


def test_continue_prefills_department_and_warehouse(case):
    from html.parser import HTMLParser
    class Selected(HTMLParser):
        selected = []
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == 'option' and 'selected' in attrs:
                self.selected.append(attrs.get('value'))
    with wms.app.app_context():
        department = wms.Department(code='AUD-D', name='审计部门', status='active')
        wms.db.session.add(department)
        wms.db.session.commit()
        dept_id = department.id
    response = case[0].get('/out_order/add', query_string={'department_id': dept_id, 'warehouse':'审计仓', 'picker':'审计员'})
    parser = Selected(); parser.feed(response.get_data(as_text=True))
    assert str(dept_id) in parser.selected
    assert '审计员' in response.get_data(as_text=True)


@pytest.mark.parametrize('builtin', [False, True])
def test_remove_builtin_stock_price_columns(builtin):
    from openpyxl import Workbook
    from services.stock_print_preview import remove_builtin_stock_price_columns
    workbook = Workbook(); sheet = workbook.active
    sheet['A1'] = '库存查询'; sheet.merge_cells('A1:C1')
    sheet.append(['物料', '单价', '库存金额'])
    sheet.append(['{item.code}', '{item.price}', '{item.amount}'])
    path = 'builtin_stock_query_default.xlsx' if builtin else 'custom.xlsx'
    remove_builtin_stock_price_columns(workbook, path)
    assert sheet['A1'].value == '库存查询'
    assert sheet.max_column == (1 if builtin else 3)
    assert [str(r) for r in sheet.merged_cells.ranges] == ([] if builtin else ['A1:C1'])


@pytest.mark.parametrize('kind', ['warehouse_patrol', 'purchase_followup'])
def test_disabled_alerts_are_reported_as_not_scanned(case, monkeypatch, kind):
    monkeypatch.setattr(wms, '_ai_capability_allowed', lambda *_: True)
    monkeypatch.setattr(wms, 'inventory_alert_enabled', lambda: False)
    monkeypatch.setattr(wms, 'build_purchase_order_todo_summary', lambda: {})
    with wms.app.test_request_context():
        from flask_login import login_user
        login_user(wms.db.session.get(wms.User, case[1][0]))
        task, error = getattr(wms, '_ai_run_' + kind + '_agent')()
        assert error is None
        texts = task.summary + ' '.join(step.result_summary or '' for step in task.steps)
        assert '库存预警未启用' in texts and '未检测低库存' in texts
        assert '低库存：0 项' not in texts


@pytest.mark.parametrize('scenario', ['selection-settings', 'completed-click', 'pending-click', 'share-capabilities', 'implemented-tabs'])
def test_browser_audit_frontend_handlers(scenario):
    result = subprocess.run([shutil.which('node'), str(ROOT/'tests/frontend_browser_report_20261103.cjs'),
        str(ROOT), scenario], capture_output=True, text=True, encoding='utf-8', timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr


def test_empty_alert_list_does_not_certify_print_health(case):
    html = case[0].get('/print_alerts').get_data(as_text=True)
    assert '暂无未读告警' in html
    assert '打印链路运行正常' not in html


@pytest.mark.parametrize('mode', ['in', 'out'])
@pytest.mark.parametrize('order_id', [None, 7])
def test_other_order_editor_does_not_offer_hint_only_share(mode, order_id):
    from jinja2 import Environment, FileSystemLoader
    from html.parser import HTMLParser
    class Actions(HTMLParser):
        def __init__(self):
            super().__init__(); self.actions = []
        def handle_starttag(self, tag, attrs):
            value = dict(attrs).get('data-action')
            if value:
                self.actions.append(value)
    env = Environment(loader=FileSystemLoader(str(ROOT/'app/templates')))
    env.globals['other_order_navigation'] = lambda *_: dict(first=None, prev=None, next=None, last=None)
    parser = Actions()
    parser.feed(env.get_template('_other_order_toolbar.html').render(toolbar_mode=mode, order_id=order_id))
    assert 'smart-share' not in parser.actions
    assert 'save' in parser.actions
