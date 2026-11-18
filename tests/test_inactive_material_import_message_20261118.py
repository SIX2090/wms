"""Known import validation is visible; unexpected errors stay private and atomic."""
import pytest

import app as w
from tests.test_document_import_warehouses import (
    ADJUSTMENT_HEADERS, OLD_HEADERS, TRANSFER_HEADERS,
    import_state, post_file, snapshot,
)


@pytest.mark.parametrize('url,headers', [
    ('/after_sale_out/import', OLD_HEADERS),
    ('/adjustment/import', ADJUSTMENT_HEADERS),
    ('/transfer/import', TRANSFER_HEADERS),
])
def test_inactive_import_explains_material_and_rolls_back(import_state, url, headers):
    client, ids = import_state
    with w.app.app_context():
        material = w.db.session.get(w.Material, ids['material'])
        material.status = 'inactive'
        w.db.session.add(w.Material(code='AI-ACTIVE', name='合成有效物料', status='active',
                                    unit_id=material.unit_id, stock=0, price=1))
        w.db.session.commit()
    before = snapshot(ids)
    response = post_file(client, [{'物料编码': 'AI-ACTIVE'}, {'物料编码': 'AI-M'}],
                         url=url, base_headers=headers)
    assert response.status_code == 400
    assert response.json['status'] == 'error'
    assert 'AI-M' in response.json['msg'] and '已停用' in response.json['msg']
    assert snapshot(ids) == before


def test_unexpected_import_error_does_not_expose_internal_details(import_state, monkeypatch):
    client, ids = import_state
    before = snapshot(ids)
    def fail(*args, **kwargs):
        raise ValueError('synthetic-internal-detail')
    monkeypatch.setattr(w, '_find_or_create_material', fail)
    response = post_file(client, [{}])
    assert response.status_code == 400
    assert response.json['status'] == 'error'
    assert 'synthetic-internal-detail' not in response.json['msg']
    assert snapshot(ids) == before
