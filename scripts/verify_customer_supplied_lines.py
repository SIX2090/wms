#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify line-level customer-supplied flags on other inbound documents."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix='wms-test-customer-supplied-', suffix='.db')
    os.close(fd)
    os.environ['WMS_DATABASE_URI'] = f'sqlite:///{db_path}'
    os.environ['WMS_ALLOW_AUTO_SECRET_KEY'] = '1'
    os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'TestAdmin@2026'
    os.environ['FLASK_ENV'] = 'testing'
    failures = []
    try:
        import app as wms
        from werkzeug.security import generate_password_hash

        wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with wms.app.app_context():
            wms.db.drop_all()
            wms.db.create_all()
            admin = wms.User(username='admin', password_hash=generate_password_hash('TestAdmin@2026'), role='admin', status='normal')
            customer = wms.Customer(code='TEST-CS-C', name='TEST客供客户')
            unit = wms.Unit(code='TEST-CS-U', name='个')
            material = wms.Material(code='TEST-CS-MAT', name='TEST客供物料', unit=unit, stock=20, price=3)
            warehouse = wms.Warehouse(code='TEST-CS-WH', name='TEST仓库', status='active')
            wms.db.session.add_all([admin, customer, warehouse, unit, material])
            wms.db.session.commit()
            fixture = {'customer': customer.id, 'material': material.id}

        with wms.app.test_client() as client:
            client.post('/login', data={'username': 'admin', 'password': 'TestAdmin@2026'})
            add_page = client.get('/other_in_order/add')
            if add_page.status_code != 200 or b'line-customer-supplied' not in add_page.data:
                failures.append('other inbound add page does not render the line checkbox')
            payload = {
                'order_no': 'TEST-CS-OTHER-IN-001', 'date': '2026-07-26',
                'business_type': '其他入库', 'purpose': 'TEST/E2E 混合归属',
                'customer_id': fixture['customer'], 'warehouse': 'TEST仓库',
                'items': [
                    {'code': 'TEST-CS-MAT', 'quantity': 2, 'price': 3, 'is_customer_supplied': False},
                    {'code': 'TEST-CS-MAT', 'quantity': 4, 'price': 0, 'is_customer_supplied': True},
                ],
            }
            before = None
            with wms.app.app_context():
                before = wms.db.session.get(wms.Material, fixture['material']).stock
            response = client.post('/in_order/add', json=payload)
            body = response.get_json() or {}
            if response.status_code != 200 or body.get('status') != 'success':
                failures.append(f'mixed draft save failed: {response.status_code} {body}')
                order_id = None
            else:
                order_id = body['id']

            if order_id:
                with wms.app.app_context():
                    order = wms.db.session.get(wms.InOrder, order_id)
                    flags = sorted((bool(item.is_customer_supplied), item.quantity) for item in order.items)
                    after = wms.db.session.get(wms.Material, fixture['material']).stock
                    item_ids = {bool(item.is_customer_supplied): item.id for item in order.items}
                    order.status = 'completed'
                    wms.db.session.commit()
                if flags != [(False, 2), (True, 4)]:
                    failures.append(f'ownership lines merged or flags lost: {flags}')
                if before != after:
                    failures.append(f'draft changed stock: {before}->{after}')
                detail = client.get(f'/in_order/{order_id}')
                if detail.status_code != 200 or '客供'.encode() not in detail.data:
                    failures.append('detail page does not show customer-supplied status')

                own_push = client.post(f'/in_order/{order_id}/push', json={
                    'target_type': 'requisition', 'request_id': 'TEST-CS-OWN-PUSH',
                    'items': [{'source_item_id': item_ids[False], 'quantity': 1}],
                })
                if own_push.status_code != 200:
                    failures.append(f'non-customer line push failed: {own_push.status_code}')
                customer_push = client.post(f'/in_order/{order_id}/push', json={
                    'target_type': 'requisition', 'request_id': 'TEST-CS-CUSTOMER-PUSH',
                    'items': [{'source_item_id': item_ids[True], 'quantity': 1}],
                })
                if customer_push.status_code != 409 or '客供料' not in (customer_push.get_json() or {}).get('msg', ''):
                    failures.append('customer-supplied line was not blocked from ordinary outbound push')

            missing_customer = dict(payload)
            missing_customer['order_no'] = 'TEST-CS-NO-CUSTOMER'
            missing_customer['customer_id'] = None
            missing_customer['items'] = [{'code': 'TEST-CS-MAT', 'quantity': 1, 'price': 0, 'is_customer_supplied': True}]
            rejected = client.post('/in_order/add', json=missing_customer)
            if rejected.status_code != 400 or '选择客户' not in (rejected.get_json() or {}).get('msg', ''):
                failures.append('customer-supplied line without customer was not rejected')

            wrong_type = dict(payload)
            wrong_type['order_no'] = 'TEST-CS-PURCHASE'
            wrong_type['business_type'] = '采购入库'
            wrong_type['supplier_id'] = None
            wrong_type['items'] = [{'code': 'TEST-CS-MAT', 'quantity': 1, 'price': 0, 'is_customer_supplied': True}]
            rejected = client.post('/in_order/add', json=wrong_type)
            if rejected.status_code != 400 or '其他入库单' not in (rejected.get_json() or {}).get('msg', ''):
                failures.append('customer-supplied flag on purchase inbound was not rejected')

        source = (ROOT / 'app' / 'app.py').read_text(encoding='utf-8')
        template = (ROOT / 'app' / 'templates' / 'in_order_add.html').read_text(encoding='utf-8')
        if 'ALTER TABLE in_order_item ADD COLUMN is_customer_supplied' not in source:
            failures.append('repeatable migration is missing')
        if 'line-customer-supplied' not in template or 'data-column-key="is_customer_supplied"' not in template:
            failures.append('line checkbox is missing from other inbound grid')

        if failures:
            for failure in failures:
                print('FAIL', failure)
            return 1
        print('PASS CUSTOMER-SUPPLIED-LINES: mixed ownership, persistence, validation, display and outbound blocking verified')
        print(f'PASS TEST-DATA: isolated database removed ({Path(db_path).name})')
        return 0
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
