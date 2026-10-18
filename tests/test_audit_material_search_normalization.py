# -*- coding: utf-8 -*-
"""BUG-2026-10-17-016：物料档案搜索必须兼容全角数字（中文输入法）。"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'app'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import app as wms  # noqa: E402
from app import Material, MaterialCategory, Unit, User, db  # noqa: E402

wms.app.config['TESTING'] = True
wms.app.config['WTF_CSRF_ENABLED'] = False


@pytest.fixture()
def client():
    with wms.app.app_context():
        db.drop_all(); db.create_all()
        from werkzeug.security import generate_password_hash
        db.session.add_all([Unit(code='PCS', name='个'),
                            MaterialCategory(code='C', name='默认'),
                            User(username='admin', password_hash=generate_password_hash('admin'),
                                 role='admin', must_change_password=False)])
        db.session.flush()
        db.session.add(Material(code='121001', name='塑料外壳式断路器', category_id=1, unit_id=1, stock=0))
        db.session.commit()
    c = wms.app.test_client()
    with c.session_transaction() as s:
        s['_user_id'] = '1'; s['_fresh'] = True
    return c


def test_fullwidth_digits_search_matches_halfwidth_code(client):
    resp = client.get('/material?search=' + '%EF%BC%91%EF%BC%92%EF%BC%91%EF%BC%90%EF%BC%90%EF%BC%91&status=active')
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert '121001' in body, '全角数字搜索应命中半角编码物料'
    assert '暂无物料数据' not in body
