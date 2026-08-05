#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproduce the exact screenshot scenario: a purchase inbound order with
self-entered items (no purchase order source) being completed via the UI route."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix='wms-repro-complete-', suffix='.db')
    os.close(fd)
    os.environ['WMS_DATABASE_URI'] = f'sqlite:///{db_path}'
    os.environ['WMS_ALLOW_AUTO_SECRET_KEY'] = '1'
    os.environ['WMS_BOOTSTRAP_PASSWORD'] = 'TestAdmin@2026'
    os.environ['FLASK_ENV'] = 'testing'
    try:
        import logging
        logging.basicConfig(level=logging.DEBUG)
        import app as wms
        from werkzeug.security import generate_password_hash

        wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
        with wms.app.app_context():
            wms.db.drop_all()
            wms.db.create_all()
            admin = wms.User(username='admin', password_hash=generate_password_hash('TestAdmin@2026'), role='admin', status='normal')
            unit = wms.Unit(code='U1', name='个')
            material = wms.Material(code='206140', name='物料', spec='', unit=unit, stock=0, price=10)
            wh = wms.Warehouse(code='XM', name='项目仓', status='active', is_default=True)
            order = wms.InOrder(order_no='REPRO-PO-001', business_type='采购入库', warehouse='项目仓', status='pending', operator_id=admin.id)
            wms.db.session.add_all([admin, unit, material, wh, order])
            wms.db.session.flush()
            wms.db.session.add(wms.InOrderItem(in_order_id=order.id, material_id=material.id, quantity=25, price=10, amount=250))
            wms.db.session.commit()
            order_id = order.id

        def login(client, username, password):
            return client.post('/login', data={'username': username, 'password': password})

        with wms.app.test_client() as client:
            login(client, 'admin', 'TestAdmin@2026')
            print('=== POST /in_order/{id}/complete ===')
            resp = client.post(f'/in_order/{order_id}/complete')
            body = resp.get_json()
            print(f'status_code={resp.status_code}')
            print(f'body={json_dumps(body)}')
            with wms.app.app_context():
                o = wms.db.session.get(wms.InOrder, order_id)
                print(f'order.status={o.status}')
                print(f'can_push_source={wms._in_order_push_source_type(o)}')
                print(f'material.stock={wms.db.session.get(wms.Material, material.id).stock}')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return 1
    return 0


def json_dumps(body):
    import json
    return json.dumps(body, ensure_ascii=False)


if __name__ == '__main__':
    sys.exit(main())