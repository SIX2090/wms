"""Round9–11 regressions against real isolated routes and page listeners."""
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import app as wms
from flask import g
from services.warehouse_stock_service import apply_stock_delta

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def followup_client(monkeypatch):
    monkeypatch.setitem(wms.app.config, 'TESTING', True)
    monkeypatch.setitem(wms.app.config, 'WTF_CSRF_ENABLED', False)
    hooks = dict(wms.app.before_request_funcs)
    def refresh_user():
        g.pop('_login_user', None)
    hooks[None] = [refresh_user, *hooks.get(None, [])]
    monkeypatch.setattr(wms.app, 'before_request_funcs', hooks)
    monkeypatch.setattr(wms, '_ai_call_llm_chat', lambda *a, **k: 'Synthetic local analysis')
    with wms.app.app_context():
        wms.db.session.remove(); wms.db.drop_all(); wms.db.create_all()
        user = wms.User(username='QA-FOLLOWUP', password_hash='unusable-test-hash', role='admin', must_change_password=False)
        wha = wms.Warehouse(code='QA-A', name='合成仓A', is_default=True, status='active')
        whb = wms.Warehouse(code='QA-B', name='合成仓B', status='active')
        cat = wms.MaterialCategory(code='QA-C', name='合成分类')
        unit = wms.Unit(code='QA-U', name='个')
        supplier = wms.Supplier(code='QA-S', name='合成供应商')
        wms.db.session.add_all([user, wha, whb, cat, unit, supplier]); wms.db.session.flush()
        material = wms.Material(code='QA-M', name='合成物料', category_id=cat.id, unit_id=unit.id, stock=0)
        legacy = wms.Material(code='QA-LEGACY', name='无分类单位物料', stock=0)
        wms.db.session.add_all([material, legacy]); wms.db.session.commit()
        client = wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(user.id); session['_fresh'] = True
        yield client, (material.id, legacy.id, wha.id, whb.id, supplier.id)
        wms.db.session.remove(); wms.db.drop_all()


def test_supplier_report_counts_completed_deliveries_only(followup_client):
    client, (mid, _, wa, wb, sid) = followup_client
    for n, (status, amount, wh) in enumerate([('completed', 4, wa), ('completed', 8, wb), ('pending', 200, wa)], 1):
        order = wms.InOrder(order_no=f'QA-IN-{n}', date=date.today(), status=status, total_amount=amount, supplier_id=sid, warehouse=wms.db.session.get(wms.Warehouse, wh).name)
        wms.db.session.add(order); wms.db.session.flush()
        wms.db.session.add(wms.InOrderItem(in_order_id=order.id, material_id=mid, quantity=amount / 2, price=2, amount=amount))
    wms.db.session.commit()
    response = client.post('/api/ai/supplier_evaluation', json={})
    assert response.status_code == 200
    data = response.get_json(); row = data['evaluations'][0]
    assert row['order_count'] == 2 and row['total_amount'] == 12
    assert data['summary']['total_amount'] == sum(x['total_amount'] for x in data['evaluations'])
    assert data['summary']['total'] == len(data['evaluations'])


@pytest.mark.parametrize('category,expected', [('', 2), ('合成分类', 1), ('不存在分类', 0)])
def test_forecast_serializes_relationship_names_and_filters(followup_client, category, expected):
    client, (mid, legacy_id, wa, wb, _) = followup_client
    for material_id, warehouse_id, quantity, kind in [(mid, wa, 10, 'in'), (mid, wb, 20, 'in'), (mid, wa, -3, 'out'), (legacy_id, wa, 5, 'in'), (legacy_id, wa, -1, 'out')]:
        with wms.app.test_request_context('/'):
            ok, error = apply_stock_delta(wms.db.session.get(wms.Material, material_id), quantity, transaction_type=kind, reference_type='qa_followup', warehouse=wms.db.session.get(wms.Warehouse, warehouse_id))
        assert ok, error
    # Historic code-based warehouse attribution remains readable; no production data.
    for txn in wms.StockTransaction.query.filter_by(transaction_type='out'):
        txn.location = wms.db.session.get(wms.Warehouse, wa).code
        txn.warehouse_id = None
    wms.db.session.commit()
    response = client.post('/api/ai/demand_forecast', json={'forecast_days': 30, 'category': category})
    assert response.status_code == 200, response.get_json()
    data = response.get_json(); assert len(data['forecasts']) == expected
    if expected:
        row = next(x for x in data['forecasts'] if x['material_id'] == mid)
        assert row['category'] == '合成分类' and row['unit'] == '个'
        assert row['current_stock'] == 27 and row['forecast_qty'] == .5
        assert data['summary']['total'] == len(data['forecasts'])
        assert sum(data['summary'][k] for k in ['need_restock', 'stock_sufficient', 'stock_excess']) == expected
        assert wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse, wb))[mid] == 20


def test_location_material_options_use_unit_name(followup_client):
    client, _ = followup_client
    response = client.post('/api/ai/recommend_location', json={})
    assert response.status_code == 200
    assert response.get_json()['materials'][0]['unit'] == '个'


@pytest.mark.parametrize('decision', ['pending', 'no_go', 'go'])
def test_acceptance_daily_snapshots_exposes_latest_saved_package(followup_client, decision):
    client, _ = followup_client
    for number, status in [(1, 'no_go'), (2, decision)]:
        row = wms.AIAcceptanceEvidencePackage(package_id=f'QA-PKG-{number}', start_date='2026-10-25', end_date='2026-10-31', daily_snapshot_dates='[]', seven_day_summary='{}', go_no_go_decision=status, decision_reason='QA 已保存原因')
        wms.db.session.add(row)
    wms.db.session.commit()
    body = client.get('/api/ai/acceptance/daily_snapshots').get_json()
    assert body['latest_package_id'] == 2
    detail = client.get('/api/ai/acceptance/evidence_package/2').get_json()['package']
    assert detail['go_no_go_decision'] == decision and detail['decision_reason'] == 'QA 已保存原因'


def test_mark_read_returns_same_count_as_visible_badge(followup_client):
    client, _ = followup_client
    notes = [wms.Notification(type=t, target_id=i, title='QA', content='QA', is_read=False, created_at=created) for i, (t, created) in enumerate([('print_failed', datetime.now()), ('print_pending_timeout', datetime.now()), ('system', datetime.now()), ('print_failed', datetime.now() - timedelta(days=40))], 1)]
    wms.db.session.add_all(notes); wms.db.session.commit()
    body = client.post('/print_alerts/mark_read', json={'ids': [notes[0].id]}).get_json()
    assert body['unread_count'] == 1
    assert wms.db.session.get(wms.Notification, notes[2].id).is_read is False
    body = client.post('/print_alerts/mark_read', json={'all': True}).get_json()
    assert body['unread_count'] == 0


@pytest.mark.parametrize('scenario', ['workstation-enabled', 'workstation-disabled', 'route-enabled', 'route-disabled', 'alert-parent-count', 'audit-parent', 'audit-busy', 'acceptance-no_go', 'acceptance-go', 'acceptance-pending', 'acceptance-load-race', 'ocr-clear', 'ocr-replace', 'ocr-file-error', 'ocr-type-change', 'ocr-read-type-change', 'ocr-clear-reader', 'ocr-error', 'ocr-success'])
def test_followup_frontend_runtime(scenario):
    result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/frontend_audit_followup.cjs'), str(ROOT), scenario], capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr


def test_print_editor_markup_passes_enabled_values(followup_client):
    client, (_, _, wh, _, _) = followup_client
    ws = wms.PrintWorkstation(code='QA-WS', name='QA WS', device_id='synthetic-only', enabled=False, auth_token=None)
    wms.db.session.add(ws); wms.db.session.flush()
    printer = wms.PrintDevice(workstation_id=ws.id, system_name='QA virtual printer', display_name='QA virtual printer')
    wms.db.session.add(printer); wms.db.session.flush()
    rule = wms.PrintRouteRule(name='QA rule', business_event='out_order', workstation_id=ws.id, printer_id=printer.id, enabled=False, priority=100)
    wms.db.session.add(rule); wms.db.session.commit()
    page = client.get('/print_routing').get_data(as_text=True)
    assert re.search(r'editWs\([^\n]+false\)', page)
    assert re.search(r'editRule\([^\n]+false\)', page)
