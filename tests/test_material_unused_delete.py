"""Batch cleanup deletes only unused selected archives; all fixtures are isolated."""
import json

import pytest


@pytest.fixture
def cleanup_case(bom_case):
    from app import db, Material
    client, ids = bom_case
    materials = [Material(code='CLEAN-'+str(i), name='清理测试'+str(i),
                          unit_id=ids['unit'], stock=0) for i in range(4)]
    db.session.add_all(materials)
    db.session.commit()
    return client, [m.id for m in materials]


def test_delete_unused_materials(cleanup_case):
    from app import db, Material, StockTransaction, OperationAudit
    client, ids = cleanup_case
    db.session.add(StockTransaction(material_id=ids[1], transaction_type='in', quantity=0))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': [ids[0], ids[1], ids[2]]})
    assert response.status_code == 200
    data = response.json['data']
    assert (data['selected_count'], data['deleted_count'], data['skipped_count'], data['failed_count']) == (3, 2, 1, 0)
    assert [row['id'] for row in data['items']] == ids[:3]
    assert data['items'][1]['status'] == 'skipped'
    assert '业务引用' in data['items'][1]['reason']
    assert db.session.get(Material, ids[0]) is None
    assert db.session.get(Material, ids[1]) is not None
    assert db.session.get(Material, ids[2]) is None
    assert db.session.get(Material, ids[3]) is not None  # Never selected.
    assert StockTransaction.query.filter_by(material_id=ids[1]).count() == 1
    audit = OperationAudit.query.filter_by(operation='delete_material').order_by(OperationAudit.id.desc()).first()
    assert {x['id'] for x in json.loads(audit.old_data)} == {ids[0], ids[2]}


@pytest.mark.parametrize('quantity', [5, -5])
@pytest.mark.parametrize('location_management', ['0', '1'])
def test_nonzero_inventory_is_kept_even_with_zero_total(cleanup_case, quantity, location_management):
    from app import db, Material, LocationInventory, Warehouse, set_system_setting
    client, ids = cleanup_case
    warehouse = Warehouse(code='CLEAN-W', name='清理测试仓')
    other = Warehouse(code='CLEAN-W2', name='另一个清理仓', status='inactive')
    db.session.add_all([warehouse, other])
    set_system_setting('location_management_enabled', location_management)
    db.session.flush()
    db.session.add(LocationInventory(material_id=ids[0], warehouse_id=warehouse.id,
                                     location='库位A', quantity=quantity))
    db.session.add(LocationInventory(material_id=ids[0], warehouse_id=other.id,
                                     location='库位B', quantity=-quantity))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 200
    assert response.json['data']['deleted_count'] == 1
    assert '库存' in response.json['data']['items'][0]['reason']
    assert db.session.get(Material, ids[0]) is not None
    assert sorted(x.quantity for x in LocationInventory.query.filter_by(material_id=ids[0])) == [-5, 5]


def test_unassigned_historical_inventory_is_never_discarded(cleanup_case):
    from app import db, Material, LocationInventory
    client, ids = cleanup_case
    db.session.add(LocationInventory(material_id=ids[0], warehouse_id=None, location='', quantity=3))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 200
    assert response.json['data']['skipped_count'] == 1
    assert db.session.get(Material, ids[0]) is not None
    assert LocationInventory.query.filter_by(material_id=ids[0]).one().quantity == 3


@pytest.mark.parametrize('stock', [2, -2])
def test_legacy_orphan_total_balance_is_kept(cleanup_case, stock):
    from app import db, Material
    client, ids = cleanup_case
    db.session.get(Material, ids[0]).stock = stock
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 200
    assert response.json['data']['deleted_count'] == 1
    assert '库存' in response.json['data']['items'][0]['reason']
    assert db.session.get(Material, ids[0]).stock == stock


def test_zero_auxiliary_inventory_is_removed_with_unused_archive(cleanup_case):
    from app import db, Material, LocationInventory
    client, ids = cleanup_case
    db.session.add(LocationInventory(material_id=ids[0], location='空辅助行', quantity=0))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': [str(ids[0]), ids[0]]})
    assert response.status_code == 200
    assert response.json['data']['selected_count'] == 1
    assert response.json['data']['deleted_count'] == 1
    assert db.session.get(Material, ids[0]) is None
    assert not LocationInventory.query.filter_by(material_id=ids[0]).first()


def test_code_only_references_are_kept(cleanup_case):
    from app import db, Material, BOM, PurchaseRequest, PurchaseRequestItem
    client, ids = cleanup_case
    db.session.add(BOM(bom_no='CLEAN-BOM', product_code='CLEAN-0', product_name='清理产品'))
    document = PurchaseRequest(request_no='CLEAN-PR')
    db.session.add(document)
    db.session.flush()
    db.session.add(PurchaseRequestItem(purchase_request_id=document.id, material_id=None,
                                       material_code='CLEAN-1', quantity=1))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:3]})
    assert response.status_code == 200
    assert response.json['data']['skipped_count'] == 2
    assert response.json['data']['deleted_count'] == 1
    assert all(db.session.get(Material, mid) is not None for mid in ids[:2])


def test_images_and_missing_ids_have_explicit_kept_results(cleanup_case):
    from app import db, MaterialImage
    client, ids = cleanup_case
    db.session.add(MaterialImage(material_id=ids[0], image='uploads/synthetic.jpg'))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': [ids[0], 999999]})
    assert response.status_code == 400  # Preserve legacy all-blocked status.
    data = response.json['data']
    assert (data['deleted_count'], data['skipped_count']) == (0, 2)
    assert '存在物料图片' in data['items'][0]['reason']
    assert '不存在' in data['items'][1]['reason']


def test_legacy_primary_image_is_kept_without_image_table_row(cleanup_case):
    from app import db, Material, MaterialImage
    client, ids = cleanup_case
    db.session.get(Material, ids[0]).image = 'uploads/synthetic-legacy.jpg'
    db.session.commit()
    assert MaterialImage.query.filter_by(material_id=ids[0]).count() == 0
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 200
    assert response.json['data']['skipped_count'] == 1
    assert '存在物料图片' in response.json['data']['items'][0]['reason']
    assert db.session.get(Material, ids[0]).image == 'uploads/synthetic-legacy.jpg'


def test_single_delete_failure_does_not_rollback_previous_successes(cleanup_case):
    from app import db, Material, LocationInventory, OperationAudit
    client, ids = cleanup_case
    db.session.add(LocationInventory(material_id=ids[1], location='空辅助行', quantity=0))
    db.session.commit()
    db.session.execute(db.text("CREATE TRIGGER cleanup_failure BEFORE DELETE ON material WHEN OLD.code='CLEAN-1' BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END"))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:3]})
    assert response.status_code == 200
    data = response.json['data']
    assert (data['deleted_count'], data['failed_count'], data['skipped_count']) == (2, 1, 0)
    assert [x['status'] for x in data['items']] == ['deleted', 'failed', 'deleted']
    assert [db.session.get(Material, mid) is not None for mid in ids[:3]] == [False, True, False]
    assert LocationInventory.query.filter_by(material_id=ids[1]).count() == 1
    audit = OperationAudit.query.filter_by(operation='delete_material').order_by(OperationAudit.id.desc()).first()
    assert {x['id'] for x in json.loads(audit.old_data)} == {ids[0], ids[2]}


def test_missing_required_reference_table_fails_closed(cleanup_case):
    from app import db, Material
    client, ids = cleanup_case
    db.session.execute(db.text('DROP TABLE stock_transaction'))
    db.session.commit()
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 503
    assert '未删除' in response.json['msg']
    assert all(db.session.get(Material, mid) is not None for mid in ids)


def test_unexpected_reference_query_error_fails_closed(cleanup_case, monkeypatch):
    from app import db, Material
    from sqlalchemy.exc import OperationalError
    client, ids = cleanup_case
    original = db.session.execute
    def execute(statement, *args, **kwargs):
        if 'SELECT' in str(statement).upper() and 'in_order_item' in str(statement):
            raise OperationalError('synthetic reference failure', {}, Exception('synthetic'))
        return original(statement, *args, **kwargs)
    monkeypatch.setattr(db.session, 'execute', execute)
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 503
    assert all(db.session.get(Material, mid) is not None for mid in ids)


@pytest.mark.parametrize('body', [None, [], {'ids': []}, {'ids': '1'}, {'ids': [True]},
                                   {'ids': [1.1]}, {'ids': [-1]}, {'ids': [0]}, {'ids': ['x']}])
def test_bad_input_never_deletes(cleanup_case, body):
    from app import db, Material
    client, ids = cleanup_case
    response = client.post('/material/delete', data=json.dumps(body), content_type='application/json')
    assert response.status_code == 400
    assert response.is_json
    assert all(db.session.get(Material, mid) is not None for mid in ids)


def test_form_encoded_legacy_call_still_works(cleanup_case):
    client, ids = cleanup_case
    response = client.post('/material/delete', data={'ids': json.dumps([str(ids[0])])})
    assert response.status_code == 200
    assert response.json['data']['deleted_count'] == 1


def test_new_reference_table_is_automatically_protected(cleanup_case):
    from app import db, Material
    from sqlalchemy import Table, Column, Integer, ForeignKey
    client, ids = cleanup_case
    table = Table('cleanup_future_reference', db.metadata,
                  Column('id', Integer, primary_key=True),
                  Column('material_id', Integer, ForeignKey('material.id')))
    try:
        table.create(db.engine)
        db.session.execute(table.insert().values(material_id=ids[0]))
        db.session.commit()
        response = client.post('/material/delete', json={'ids': ids[:2]})
        assert response.status_code == 200
        assert response.json['data']['skipped_count'] == 1
        assert db.session.get(Material, ids[0]) is not None
        assert db.session.execute(db.select(table)).first() is not None
    finally:
        db.session.rollback()
        table.drop(db.engine)
        db.metadata.remove(table)


def test_final_commit_failure_rolls_back_every_deletion(cleanup_case, monkeypatch):
    from app import db, Material, OperationAudit
    client, ids = cleanup_case
    def failed_commit():
        raise RuntimeError('synthetic final commit failure')
    monkeypatch.setattr(db.session, 'commit', failed_commit)
    response = client.post('/material/delete', json={'ids': ids[:3]})
    assert response.status_code == 503
    assert '未删除' in response.json['msg']
    assert all(db.session.get(Material, mid) is not None for mid in ids)
    assert OperationAudit.query.filter_by(operation='delete_material').count() == 0


def test_csrf_is_required_for_cleanup(cleanup_case, monkeypatch):
    from app import app, db, Material
    client, ids = cleanup_case
    monkeypatch.setitem(app.config, 'WTF_CSRF_ENABLED', True)
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 400
    assert all(db.session.get(Material, mid) is not None for mid in ids)


def test_unauthenticated_cleanup_is_rejected(cleanup_case):
    from app import app, db, Material
    _, ids = cleanup_case
    response = app.test_client().post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code in (302, 401)
    assert all(db.session.get(Material, mid) is not None for mid in ids)


def test_sales_account_cannot_cleanup(cleanup_case):
    from app import db, Material, User
    client, ids = cleanup_case
    user = User(username='cleanup-sales-only', role='sales', password_hash='synthetic-unused', must_change_password=False)
    db.session.add(user)
    db.session.commit()
    with client.session_transaction() as session:
        session['_user_id'] = str(user.id)
        session['_fresh'] = True
    response = client.post('/material/delete', json={'ids': ids[:2]})
    assert response.status_code == 403
    assert all(db.session.get(Material, mid) is not None for mid in ids)


def test_batch_limit_and_malformed_json_never_delete(cleanup_case):
    from app import db, Material
    client, ids = cleanup_case
    assert client.post('/material/delete', json={'ids': [ids[0]] * 1001}).status_code == 400
    assert client.post('/material/delete', data='{', content_type='application/json').status_code == 400
    assert all(db.session.get(Material, mid) is not None for mid in ids)
