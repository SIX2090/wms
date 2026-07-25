#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-R07-F02：物料分类识别与按分类建议编号专项验证。"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def test_pure_logic() -> None:
    from ai.documents.material_category_coding import (
        CategoryInfo,
        suggest_category_and_code,
        normalize_spec_token,
    )

    assert normalize_spec_token('8*5') == '8X5'
    assert normalize_spec_token('8×5') == '8X5'

    cats = [
        CategoryInfo(id=1, code='LS', name='螺丝'),
        CategoryInfo(id=2, code='DX', name='电线'),
        CategoryInfo(id=3, code='QT', name='其他'),
    ]
    s = suggest_category_and_code(
        name='螺丝',
        spec='8*5',
        raw_text='螺丝8*5 100个',
        categories=cats,
        existing_codes=[],
        fallback_code='AI260726001',
    )
    assert s.category_id == 1, s
    assert s.suggested_code.startswith('LS'), s
    assert s.suggested_code == 'LS-8X5' or s.suggested_code.startswith('LS-8X5'), s
    assert '8X5' in s.suggested_code, s
    assert s.confidence >= 0.5, s

    s2 = suggest_category_and_code(
        name='螺丝',
        spec='8*5',
        categories=cats,
        existing_codes=[s.suggested_code],
        fallback_code='AI260726001',
    )
    assert s2.suggested_code != s.suggested_code, (s.suggested_code, s2.suggested_code)

    s3 = suggest_category_and_code(
        name='未知奇奇怪怪',
        spec='',
        categories=cats,
        existing_codes=[],
        fallback_code='AI260726099',
    )
    assert s3.category_id is None
    assert s3.suggested_code == 'AI260726099'
    print('pure logic OK')


def test_confirm_flow() -> None:
    fd, db_path = tempfile.mkstemp(prefix='wms-test-cat-code-', suffix='.db')
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
            admin = wms.User(
                username='admin',
                password_hash=generate_password_hash('TestAdmin@2026'),
                role='admin',
                status='normal',
            )
            unit = wms.Unit(code='PCS', name='个')
            cat = wms.MaterialCategory(code='LS', name='螺丝')
            wms.db.session.add_all([admin, unit, cat])
            wms.db.session.commit()
            unit_id = unit.id
            cat_id = cat.id

            payload = {
                'document_type': 'in_order',
                'source_text': 'TEST/E2E 螺丝8*5 10个',
                'rows': [{
                    'raw': '螺丝8*5 10个',
                    'raw_text': '螺丝8*5 10个',
                    'code': '',
                    'name': '螺丝',
                    'spec': '8*5',
                    'unit': '个',
                    'quantity': 10,
                    'material_id': None,
                    'match_status': 'unmatched',
                    'reason': '未找到物料档案',
                }],
            }
            wms._ai_prepare_new_material_suggestions(payload)
            row = payload['rows'][0]
            if row.get('suggested_category_id') != cat_id:
                failures.append(f'category not suggested: {row}')
            if not str(row.get('suggested_material_code') or '').startswith('LS'):
                failures.append(f'code not category-based: {row.get("suggested_material_code")}')

        token = 'TEST-CAT-CODE'
        with wms.app.test_client() as client:
            client.post('/login', data={'username': 'admin', 'password': 'TestAdmin@2026'})
            with client.session_transaction() as session:
                session['_ai_document_confirmations'] = {token: payload}
            page = client.get(f'/ai/document_confirm/{token}')
            if page.status_code != 200:
                failures.append(f'confirm page {page.status_code}')
            body = page.data.decode('utf-8', errors='replace')
            if 'new_material_category_id_0' not in body:
                failures.append('category select missing on confirm page')
            if 'LS' not in body and '螺丝' not in body:
                failures.append('category options missing')

            code = payload['rows'][0].get('suggested_material_code') or 'LS-8X5'
            resp = client.post(
                f'/ai/document_confirm/{token}',
                data={
                    'row_count': '1',
                    'use_row_0': '1',
                    'create_material_0': '1',
                    'new_material_code_0': code,
                    'new_material_name_0': '螺丝',
                    'new_material_spec_0': '8*5',
                    'new_material_category_id_0': str(cat_id),
                    'new_material_unit_id_0': str(unit_id),
                    'quantity_0': '10',
                    'inbound_business_type': 'other_in',
                },
                follow_redirects=False,
            )
            if resp.status_code != 302 or '/in_order/' not in (resp.headers.get('Location') or ''):
                failures.append(f'draft not created: {resp.status_code} {resp.headers.get("Location")}')

            with wms.app.app_context():
                mat = wms.Material.query.filter_by(code=code).first()
                if not mat or mat.category_id != cat_id or mat.stock != 0:
                    failures.append(f'material not saved with category/zero stock: {mat}')
    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass

    if failures:
        raise AssertionError('; '.join(failures))
    print('confirm flow OK')


def main() -> int:
    test_pure_logic()
    test_confirm_flow()
    print('PASS AI-R07-F02 material category coding')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('FAIL', exc)
        raise SystemExit(1)
