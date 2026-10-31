"""Missing master-data registries must never be reported as a successful repair."""
import pytest
import app as wms


@pytest.fixture
def material_client():
    wms.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with wms.app.app_context():
        wms.db.drop_all(); wms.db.create_all()
        user=wms.User(username='SYN-MASTER', password_hash='unusable-test-hash', role='admin', must_change_password=False)
        wms.db.session.add(user); wms.db.session.commit()
        client=wms.app.test_client()
        with client.session_transaction() as session:
            session['_user_id']=str(user.id); session['_fresh']=True
        yield client
        wms.db.session.remove(); wms.db.drop_all()


def seed_material(unit=True, category=True, preferred=True, empty=None):
    if unit:
        wms.db.session.add(wms.Unit(code='SYN-U', name='个' if preferred else '合成单位'))
    if category:
        wms.db.session.add(wms.MaterialCategory(code='SYN-C', name='默认分类' if preferred else '合成分类'))
    material=wms.Material(code='SYN-M', name='合成物料', stock=10, unit_id=empty, category_id=empty)
    warehouses=[wms.Warehouse(code='SYN-A', name='合成仓A'), wms.Warehouse(code='SYN-B', name='合成仓B')]
    wms.db.session.add_all([material,*warehouses]); wms.db.session.flush()
    for warehouse,quantity in [(warehouses[0],4),(warehouses[1],3),(None,3)]:
        wms.db.session.add(wms.LocationInventory(material_id=material.id, warehouse_id=warehouse.id if warehouse else None, location='SYN', quantity=quantity))
    wms.db.session.commit()
    return material


def stock_snapshot():
    return ([(m.id,m.stock) for m in wms.Material.query.order_by(wms.Material.id)],
            [(r.material_id,r.warehouse_id,r.location,r.quantity) for r in wms.LocationInventory.query.order_by(wms.LocationInventory.id)],
            wms.StockTransaction.query.count())


@pytest.mark.parametrize('unit,category',[(False,True),(True,False),(False,False)])
def test_missing_registry_rejects_entire_repair_without_partial_changes(material_client,unit,category):
    material=seed_material(unit,category); before=stock_snapshot()
    response=material_client.post('/material/fix_empty_fields',json={})
    assert response.status_code==400, response.get_json()
    body=response.get_json(); assert body['status']=='error'
    assert ('计量单位' in body['msg']) is (not unit)
    assert ('物料分类' in body['msg']) is (not category)
    wms.db.session.expire_all()
    assert material.unit_id is None and material.category_id is None
    assert wms.Unit.query.count()==int(unit) and wms.MaterialCategory.query.count()==int(category)
    assert stock_snapshot()==before


@pytest.mark.parametrize('preferred',[True,False])
@pytest.mark.parametrize('empty',[None,0])
def test_available_registries_repair_and_repeat_is_idempotent(material_client,preferred,empty):
    material=seed_material(preferred=preferred,empty=empty); before=stock_snapshot()
    response=material_client.post('/material/fix_empty_fields',json={})
    assert response.status_code==200 and '已修复 1 条' in response.get_json()['msg']
    wms.db.session.expire_all()
    assert material.unit_id==wms.Unit.query.one().id
    assert material.category_id==wms.MaterialCategory.query.one().id
    repeat=material_client.post('/material/fix_empty_fields',json={})
    assert repeat.status_code==200 and '已修复 0 条' in repeat.get_json()['msg']
    assert stock_snapshot()==before


def test_empty_database_does_not_require_unused_registries(material_client):
    response=material_client.post('/material/fix_empty_fields',json={})
    assert response.status_code==200 and '已修复 0 条' in response.get_json()['msg']


@pytest.mark.parametrize('role',['anonymous','viewer'])
def test_registry_repair_preserves_access_control(material_client,role):
    material=seed_material(); before=stock_snapshot()
    if role=='anonymous':
        with material_client.session_transaction() as session: session.clear()
    else:
        wms.User.query.one().role=role; wms.db.session.commit()
    response=material_client.post('/material/fix_empty_fields',json={})
    assert response.status_code in (302,403)
    assert material.unit_id is None and material.category_id is None and stock_snapshot()==before


def test_repair_commit_error_rolls_back_fields(material_client,monkeypatch):
    material=seed_material(); before=stock_snapshot()
    from sqlalchemy.exc import SQLAlchemyError
    def fail(): raise SQLAlchemyError('SYNTHETIC COMMIT FAILURE')
    monkeypatch.setattr(wms.db.session,'commit',fail)
    response=material_client.post('/material/fix_empty_fields',json={})
    assert response.status_code==500 and response.get_json()['status']=='error'
    assert material.unit_id is None and material.category_id is None and stock_snapshot()==before
