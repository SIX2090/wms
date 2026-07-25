#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Isolated acceptance tests for inbound-to-outbound document push."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix='wms-test-e2e-push-', suffix='.db')
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
            viewer = wms.User(username='TEST-E2E-VIEWER', password_hash=generate_password_hash('Viewer@2026'), role='viewer', status='normal')
            unit = wms.Unit(code='TEST-E2E-U', name='测试个')
            material = wms.Material(code='TEST-E2E-PUSH-MAT', name='下推测试物料', spec='E2E', unit=unit, stock=100, price=12.5)
            customer = wms.Customer(code='TEST-E2E-C', name='下推测试客户', contact='测试联系人', phone='13800000000')
            contract = wms.Contract(contract_no='TEST-E2E-HT-001', project_name='TEST-E2E-低压柜工程', status='active')
            wms.db.session.add_all([admin, viewer, unit, material, customer, contract])
            wms.db.session.flush()
            fixtures = {'material': material.id, 'customer': customer.id, 'contract': contract.id, 'viewer': viewer.id}
            for index, business_type in enumerate(['采购入库'] * 3 + ['其他入库'] * 3, start=1):
                order = wms.InOrder(order_no=f'TEST-E2E-IN-{index:02d}', business_type=business_type, warehouse='TEST-E2E-WH', status='completed', operator_id=admin.id)
                wms.db.session.add(order)
                wms.db.session.flush()
                wms.db.session.add(wms.InOrderItem(
                    in_order_id=order.id, material_id=material.id, quantity=10, price=8, amount=80,
                    contract_id=contract.id, contract_no=contract.contract_no, project_name=contract.project_name,
                ))
            customer_supply = wms.InOrder(order_no='TEST-E2E-CUSTOMER-SUPPLY', business_type='其他入库', warehouse='TEST-E2E-WH', customer_id=customer.id, status='completed', operator_id=admin.id)
            wms.db.session.add(customer_supply)
            wms.db.session.flush()
            wms.db.session.add(wms.InOrderItem(in_order_id=customer_supply.id, material_id=material.id, quantity=5, price=0, amount=0, is_customer_supplied=True))
            draft_source = wms.InOrder(order_no='TEST-E2E-DRAFT-SOURCE', business_type='采购入库', warehouse='TEST-E2E-WH', status='pending', operator_id=admin.id)
            wms.db.session.add(draft_source)
            wms.db.session.flush()
            wms.db.session.add(wms.InOrderItem(in_order_id=draft_source.id, material_id=material.id, quantity=5, price=8, amount=40))
            wms.db.session.commit()
            source_ids = [row.id for row in wms.InOrder.query.filter(wms.InOrder.order_no.like('TEST-E2E-IN-%')).order_by(wms.InOrder.order_no).all()]
            fixtures.update(customer_supply=customer_supply.id, draft_source=draft_source.id)

        def login(client, username, password):
            return client.post('/login', data={'username': username, 'password': password})

        with wms.app.test_client() as client:
            login(client, 'admin', 'TestAdmin@2026')
            target_types = ['requisition', 'other_out', 'after_sale_out'] * 2
            created = []
            for index, (source_id, target_type) in enumerate(zip(source_ids, target_types), start=1):
                with wms.app.app_context():
                    source = wms.db.session.get(wms.InOrder, source_id)
                    source_item_id = source.items[0].id
                payload = {
                    'target_type': target_type, 'request_id': f'TEST-E2E-REQ-{index}',
                    'purpose': 'TEST/E2E 其他出库测试', 'customer_id': fixtures['customer'],
                    'reason': 'TEST/E2E 售后换货',
                    'items': [{'source_item_id': source_item_id, 'quantity': 4}],
                }
                before = None
                with wms.app.app_context():
                    before = wms.db.session.get(wms.Material, fixtures['material']).stock
                response = client.post(f'/in_order/{source_id}/push', json=payload)
                body = response.get_json() or {}
                if response.status_code != 200 or body.get('status') != 'success':
                    failures.append(f'{source_id}->{target_type} failed: {response.status_code} {body}')
                    continue
                created.append((target_type, body['id'], source_id, payload))
                source_page = client.get(f'/in_order/{source_id}')
                target_page = client.get(body['url'])
                push_page = client.get(f'/in_order/{source_id}/push?target={target_type}')
                if source_page.status_code != 200 or '下推记录'.encode() not in source_page.data:
                    failures.append(f'{target_type} source trace page did not render')
                if target_page.status_code != 200 or '来源入库单'.encode() not in target_page.data:
                    failures.append(f'{target_type} target source page did not render')
                if push_page.status_code != 200 or '可下推'.encode() not in push_page.data:
                    failures.append(f'{target_type} selection page did not render')
                with wms.app.app_context():
                    after = wms.db.session.get(wms.Material, fixtures['material']).stock
                    links = wms.DocumentPushLine.query.filter_by(target_document_type=target_type, target_document_id=body['id'], status='active').all()
                    if after != before:
                        failures.append(f'{target_type} draft changed stock {before}->{after}')
                    if len(links) != 1 or links[0].pushed_quantity != 4:
                        failures.append(f'{target_type} source trace mismatch')
                    if target_type in ('requisition', 'other_out'):
                        item = wms.db.session.get(wms.OutOrder, body['id']).items[0]
                    else:
                        item = wms.db.session.get(wms.AfterSaleOutOrder, body['id']).items[0]
                    if item.contract_no != 'TEST-E2E-HT-001' or item.project_name != 'TEST-E2E-低压柜工程':
                        failures.append(f'{target_type} contract/project not inherited')
                replay = client.post(f'/in_order/{source_id}/push', json=payload).get_json() or {}
                if not replay.get('replayed') or replay.get('id') != body['id']:
                    failures.append(f'{target_type} idempotency failed')

            # Partial second push, then over-push rejection.
            target_type, target_id, source_id, first_payload = created[0]
            second = dict(first_payload)
            second['request_id'] = 'TEST-E2E-PARTIAL-SECOND'
            second['items'] = [{'source_item_id': first_payload['items'][0]['source_item_id'], 'quantity': 6}]
            if client.post(f'/in_order/{source_id}/push', json=second).status_code != 200:
                failures.append('second partial push should consume remaining quantity')
            over = dict(first_payload)
            over['request_id'] = 'TEST-E2E-OVER'
            over['items'] = [{'source_item_id': first_payload['items'][0]['source_item_id'], 'quantity': 0.01}]
            if client.post(f'/in_order/{source_id}/push', json=over).status_code != 409:
                failures.append('over-push was not rejected')

            invalid = dict(first_payload)
            invalid['request_id'] = 'TEST-E2E-ZERO'
            invalid['items'] = [{'source_item_id': first_payload['items'][0]['source_item_id'], 'quantity': 0}]
            if client.post(f'/in_order/{source_id}/push', json=invalid).status_code != 400:
                failures.append('zero quantity was not rejected')

            with wms.app.app_context():
                draft_item = wms.db.session.get(wms.InOrder, fixtures['draft_source']).items[0].id
                customer_item = wms.db.session.get(wms.InOrder, fixtures['customer_supply']).items[0].id
            draft_response = client.post(f'/in_order/{fixtures["draft_source"]}/push', json={**first_payload, 'request_id': 'TEST-E2E-DRAFT', 'items': [{'source_item_id': draft_item, 'quantity': 1}]})
            if draft_response.status_code != 409:
                failures.append('pending source was not rejected')
            customer_response = client.post(f'/in_order/{fixtures["customer_supply"]}/push', json={**first_payload, 'request_id': 'TEST-E2E-CUSTOMER', 'items': [{'source_item_id': customer_item, 'quantity': 1}]})
            if customer_response.status_code != 409 or '所有权库存隔离' not in (customer_response.get_json() or {}).get('msg', ''):
                failures.append('customer-supplied source was not blocked')

            # Source protection while an active target exists.
            protected_source = created[1][2]
            if client.post(f'/in_order/{protected_source}/revert').status_code != 409:
                failures.append('source revert was not blocked')
            if client.post(f'/in_order/{protected_source}/delete').status_code != 409:
                failures.append('source delete was not blocked')

            # Manual complete/revert changes stock exactly once.
            complete_type, complete_id, _, _ = next(row for row in created if row[0] == 'requisition')
            with wms.app.app_context():
                before = wms.db.session.get(wms.Material, fixtures['material']).stock
            completed = client.post(f'/out_order/{complete_id}/complete').get_json() or {}
            with wms.app.app_context():
                after_complete = wms.db.session.get(wms.Material, fixtures['material']).stock
            if completed.get('status') != 'success' or after_complete != before - 4:
                failures.append(f'manual complete stock mismatch {before}->{after_complete}')
            client.post(f'/out_order/{complete_id}/revert')
            with wms.app.app_context():
                after_revert = wms.db.session.get(wms.Material, fixtures['material']).stock
            if after_revert != before:
                failures.append(f'manual revert stock mismatch {before}->{after_revert}')

            # Deleting a pending target releases its allocation.
            delete_type, delete_id, delete_source, _ = next(row for row in created if row[0] == 'other_out')
            if (client.post(f'/out_order/{delete_id}/delete').get_json() or {}).get('status') != 'success':
                failures.append('target draft delete failed')
            with wms.app.app_context():
                active = wms.DocumentPushLine.query.filter_by(target_document_type=delete_type, target_document_id=delete_id, status='active').count()
                released = wms.DocumentPushLine.query.filter_by(target_document_type=delete_type, target_document_id=delete_id, status='released').count()
            if active or not released:
                failures.append('target delete did not release allocation')

        # Viewer cannot invoke the push endpoint.
        with wms.app.test_client() as viewer_client:
            login(viewer_client, 'TEST-E2E-VIEWER', 'Viewer@2026')
            with wms.app.app_context():
                source = wms.db.session.get(wms.InOrder, source_ids[-1])
                item_id = source.items[0].id
            denied = viewer_client.post(f'/in_order/{source_ids[-1]}/push', json={'target_type': 'requisition', 'request_id': 'TEST-E2E-DENIED', 'items': [{'source_item_id': item_id, 'quantity': 1}]})
            if denied.status_code not in (302, 403):
                failures.append(f'unauthorized push returned HTTP {denied.status_code}')

        if failures:
            for failure in failures:
                print('FAIL', failure)
            return 1
        print('PASS INBOUND-PUSH: 6 target combinations, trace, limits, idempotency, permissions, stock lifecycle and customer-supplied blocking verified')
        print(f'PASS TEST-DATA: isolated database removed ({Path(db_path).name})')
        return 0
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
