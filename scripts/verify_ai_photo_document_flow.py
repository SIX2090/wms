#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verify photo OCR confirmation can create a material and warehouse draft."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def main() -> int:
    fd, db_path = tempfile.mkstemp(prefix='wms-test-photo-ai-', suffix='.db')
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
        wms._ai_document_confirm_allowed = lambda _doc_type: True
        with wms.app.app_context():
            wms.db.drop_all()
            wms.db.create_all()
            admin = wms.User(username='admin', password_hash=generate_password_hash('TestAdmin@2026'), role='admin', status='normal')
            unit = wms.Unit(code='PCS', name='个')
            wms.db.session.add_all([admin, unit])
            wms.db.session.commit()
            unit_id = unit.id

        token = 'TEST-PHOTO-CONFIRM'
        payload = {
            'document_type': 'out_order',
            'source_text': 'TEST/E2E 领料：M8螺母 5个',
            'rows': [{
                'raw': 'M8螺母 5个', 'raw_text': 'M8螺母 5个', 'code': '',
                'name': 'M8螺母', 'spec': '镀锌', 'unit': '个', 'quantity': 5,
                'material_id': None, 'match_status': 'unmatched', 'reason': '未找到物料档案',
            }],
        }
        with wms.app.test_client() as client:
            client.post('/login', data={'username': 'admin', 'password': 'TestAdmin@2026'})
            with client.session_transaction() as session:
                session['_ai_document_confirmations'] = {token: payload}

            page = client.get(f'/ai/document_confirm/{token}')
            if page.status_code != 200 or b'ai-create-material' not in page.data:
                failures.append('confirmation page does not offer material creation')

            response = client.post(f'/ai/document_confirm/{token}', data={
                'row_count': '1', 'use_row_0': '1', 'create_material_0': '1',
                'new_material_code_0': 'AI-TEST-M8', 'new_material_name_0': 'M8螺母',
                'new_material_spec_0': '镀锌', 'new_material_unit_id_0': str(unit_id),
                'quantity_0': '5',
            }, follow_redirects=False)
            if response.status_code != 302 or '/out_order/' not in (response.headers.get('Location') or ''):
                failures.append(f'confirmed flow did not redirect to outbound draft: {response.status_code} {response.headers.get("Location")}')

            with wms.app.app_context():
                material = wms.Material.query.filter_by(code='AI-TEST-M8').first()
                order = wms.OutOrder.query.order_by(wms.OutOrder.id.desc()).first()
                if not material or material.name != 'M8螺母' or material.stock != 0:
                    failures.append('confirmed material was not created safely with zero stock')
                if not order or order.status != 'pending' or len(order.items) != 1:
                    failures.append('outbound draft was not created')
                elif order.items[0].material_id != material.id or order.items[0].quantity != 5:
                    failures.append('outbound draft line does not reference the new material')

            inbound_token = 'TEST-PHOTO-INBOUND'
            inbound_payload = {
                'document_type': 'in_order', 'source_text': 'TEST/E2E 到货：铜排 2根',
                'rows': [{'raw': '铜排 2根', 'name': '铜排', 'spec': 'TMY-30x3', 'unit': '个', 'quantity': 2,
                          'material_id': None, 'match_status': 'unmatched', 'reason': '未找到物料档案'}],
            }
            with client.session_transaction() as session:
                session['_ai_document_confirmations'] = {inbound_token: inbound_payload}
            inbound = client.post(f'/ai/document_confirm/{inbound_token}', data={
                'row_count': '1', 'use_row_0': '1', 'create_material_0': '1',
                'new_material_code_0': 'AI-TEST-COPPER', 'new_material_name_0': '铜排',
                'new_material_spec_0': 'TMY-30x3', 'new_material_unit_id_0': str(unit_id),
                'quantity_0': '2', 'inbound_business_type': 'purchase_in',
            }, follow_redirects=False)
            if inbound.status_code != 302 or '/in_order/' not in (inbound.headers.get('Location') or ''):
                failures.append('confirmed photo did not create an inbound draft')
            with wms.app.app_context():
                inbound_order = wms.InOrder.query.order_by(wms.InOrder.id.desc()).first()
                copper = wms.Material.query.filter_by(code='AI-TEST-COPPER').first()
                copper_id = copper.id if copper else None
                if not inbound_order or inbound_order.status != 'pending' or inbound_order.business_type != '采购入库':
                    failures.append('photo inbound was not saved as a manual purchase receipt draft')
                if not copper or copper.stock != 0:
                    failures.append('new inbound material changed stock before manual completion')

            other_token = 'TEST-PHOTO-OTHER-INBOUND'
            other_payload = {
                'document_type': 'in_order', 'source_text': 'TEST/E2E other inbound',
                'rows': [{'raw': 'AI-TEST-COPPER 1', 'code': 'AI-TEST-COPPER', 'name': 'Copper',
                          'spec': 'TMY-30x3', 'unit': 'PCS', 'quantity': 1,
                          'material_id': copper_id, 'match_status': 'matched', 'reason': ''}],
            }
            with client.session_transaction() as session:
                session['_ai_document_confirmations'] = {other_token: other_payload}
            other = client.post(f'/ai/document_confirm/{other_token}', data={
                'row_count': '1', 'use_row_0': '1', 'material_id_0': str(copper_id),
                'quantity_0': '1', 'inbound_business_type': 'other_in',
            }, follow_redirects=False)
            if other.status_code != 302 or '/in_order/' not in (other.headers.get('Location') or ''):
                failures.append('confirmed photo did not create an other-inbound draft')
            with wms.app.app_context():
                other_order = wms.InOrder.query.order_by(wms.InOrder.id.desc()).first()
                copper = wms.db.session.get(wms.Material, copper_id)
                if not other_order or other_order.status != 'pending' or other_order.business_type != '其他入库':
                    failures.append('photo inbound was not saved as an other-inbound draft')
                if copper.stock != 0:
                    failures.append('other-inbound draft changed stock before manual completion')

        app_source = (ROOT / 'app' / 'app.py').read_text(encoding='utf-8')
        route_start = app_source.index('def api_document_ocr():')
        route_end = app_source.index("@app.route('/api/ai/document_feedback'", route_start)
        route_source = app_source[route_start:route_end]
        if "'confirmation': confirmation_action" not in route_source:
            failures.append('photo OCR response does not expose confirmation URL')
        if '_ai_create_in_order_draft(draft_message)' in route_source:
            failures.append('photo OCR still creates an inbound draft before human confirmation')

        if failures:
            for failure in failures:
                print('FAIL', failure)
            return 1
        print('PASS AI-PHOTO-DOCUMENT: unmatched material confirmation, material code creation and outbound draft verified')
        print(f'PASS TEST-DATA: isolated database removed ({Path(db_path).name})')
        return 0
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


if __name__ == '__main__':
    raise SystemExit(main())
