from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'

os.environ['FLASK_ENV'] = 'testing'
os.environ['WMS_SKIP_STARTUP_DB_UPGRADE'] = '1'
os.environ['SECRET_KEY'] = 'verify-ai-stage7-secret'
sys.path.insert(0, str(APP_DIR))

import app as wms_app


def _login(client, user_id: int) -> None:
    with client.session_transaction() as session_data:
        session_data['_user_id'] = str(user_id)
        session_data['_fresh'] = True


def _delete_stage7_materials() -> None:
    materials = wms_app.Material.query.filter(wms_app.Material.code.in_(('STAGE7-A', 'STAGE7-B'))).all()
    material_ids = [material.id for material in materials]
    if material_ids:
        wms_app.StockTransaction.query.filter(wms_app.StockTransaction.material_id.in_(material_ids)).delete(synchronize_session=False)
        wms_app.PurchaseRequestItem.query.filter(wms_app.PurchaseRequestItem.material_id.in_(material_ids)).delete(synchronize_session=False)
        wms_app.PurchaseOrderItem.query.filter(wms_app.PurchaseOrderItem.material_id.in_(material_ids)).delete(synchronize_session=False)
        wms_app.Material.query.filter(wms_app.Material.id.in_(material_ids)).delete(synchronize_session=False)


def main() -> int:
    app = wms_app.app
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        wms_app.db.create_all()
        _delete_stage7_materials()
        for username in ('stage7-purchase', 'stage7-warehouse', 'stage7-production'):
            wms_app.User.query.filter_by(username=username).delete()
        wms_app.db.session.commit()

        unit = wms_app.Unit.query.filter_by(code='STAGE7-U').first()
        if not unit:
            unit = wms_app.Unit(code='STAGE7-U', name='Stage7Unit')
            wms_app.db.session.add(unit)
        supplier = wms_app.Supplier.query.filter_by(code='STAGE7-S').first()
        if not supplier:
            supplier = wms_app.Supplier(code='STAGE7-S', name='Stage7Supplier')
            wms_app.db.session.add(supplier)
        wms_app.db.session.flush()

        risky = wms_app.Material(
            code='STAGE7-A',
            name='Stage7 Risk Material',
            unit_id=unit.id,
            supplier_id=supplier.id,
            stock=5,
            min_stock=10,
            max_stock=50,
            reorder_point=20,
            price=2.5,
        )
        normal = wms_app.Material(
            code='STAGE7-B',
            name='Stage7 Normal Material',
            unit_id=unit.id,
            supplier_id=supplier.id,
            stock=100,
            min_stock=10,
            max_stock=50,
            reorder_point=20,
            price=1,
        )
        purchase = wms_app.User(username='stage7-purchase', password_hash='not-used', role='purchase', status='normal')
        warehouse = wms_app.User(username='stage7-warehouse', password_hash='not-used', role='warehouse', status='normal')
        production = wms_app.User(username='stage7-production', password_hash='not-used', role='production', status='normal')
        wms_app.db.session.add_all([risky, normal, purchase, warehouse, production])
        wms_app.db.session.flush()
        wms_app.db.session.add(wms_app.StockTransaction(
            material_id=risky.id,
            transaction_type='out',
            quantity=-30,
            reference_type='verify-stage7',
            created_at=wms_app.datetime.now(),
        ))
        wms_app.db.session.commit()
        purchase_id = purchase.id
        warehouse_id = warehouse.id
        production_id = production.id

        report = wms_app._ai_replenishment_report(days=30, coverage_days=30, limit=20, only_action=True)
        risky_rows = [row for row in report['rows'] if row['code'] == 'STAGE7-A']
        assert risky_rows
        assert risky_rows[0]['action_required']
        assert risky_rows[0]['suggested_qty'] > 0
        assert report['summary']['action_required'] >= 1
        assert 'replenishment_planning' in wms_app.AI_TOOL_DISPATCHERS

    client = app.test_client()

    _login(client, purchase_id)
    purchase_page = client.get('/ai/replenishment?days=30&coverage_days=30')
    assert purchase_page.status_code == 200
    purchase_html = purchase_page.get_data(as_text=True)
    assert 'AI补货建议' in purchase_html
    assert 'STAGE7-A' in purchase_html

    _login(client, warehouse_id)
    warehouse_page = client.get('/ai/replenishment')
    assert warehouse_page.status_code == 200

    _login(client, production_id)
    forbidden = client.get('/ai/replenishment')
    assert forbidden.status_code in (302, 403)

    with app.app_context():
        with app.test_request_context('/_verify/stage7-replenishment'):
            wms_app.login_user(wms_app.db.session.get(wms_app.User, purchase_id))
            response = wms_app._ai_dispatch_registered_tool('replenishment_planning', '补货预测', {})
            assert response is not None
            data = response.get_json()
            assert data['status'] == 'success'
            assert any(action.get('url') == '/ai/replenishment' for action in data.get('actions', []))

    print('PASS AI-STAGE7-REPLENISHMENT: PC replenishment planning page, risk calculation, permissions, and AI entrypoint are stable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
