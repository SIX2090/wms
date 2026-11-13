"""BUG-2026-11-13-004: actual five WMS removal paths under verified OS isolation."""
from datetime import date

from scripts.verify_db_guard import require_isolated_test_runtime

require_isolated_test_runtime()

from flask import g  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app as w  # noqa: E402
from tests.document_revision_client import document_post  # noqa: E402


@pytest.fixture
def source_scene(monkeypatch):
    monkeypatch.setitem(w.app.config,'TESTING',True)
    monkeypatch.setitem(w.app.config,'WTF_CSRF_ENABLED',False)
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url)=='sqlite:///:memory:'
        assert all(not row[2] for row in w.db.session.execute(text('PRAGMA database_list')))
        w.db.session.rollback()
        w.db.drop_all()
        w.db.create_all()
        def fresh_user(): g.pop('_login_user',None)
        hooks=dict(w.app.before_request_funcs)
        hooks[None]=[fresh_user,*hooks.get(None,[])]
        monkeypatch.setattr(w.app,'before_request_funcs',hooks)
        user=w.User(username='synthetic-sources',password_hash='non-login-test-value',
                    role='admin',must_change_password=False)
        a=w.Warehouse(code='SYN-A',name='合成甲仓',status='active',is_default=True)
        b=w.Warehouse(code='SYN-B',name='合成乙仓',status='active')
        w.db.session.add_all([user,a,b])
        w.db.session.commit()
        client=w.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'],session['_fresh']=str(user.id),True
        yield client,a,b
        w.db.session.remove()


def _seed(scene, location_on, legacy):
    client,a,b=scene
    w.set_system_setting('location_management_enabled','1' if location_on else '0')
    w.db.session.commit()
    first=client.post('/material/add',data={'code':'SYN-INITIAL','name':'合成初始','stock':'5','price':'0'})
    second=client.post('/material/add',data={'code':'SYN-KEEP','name':'合成保留','stock':'0','price':'0'})
    assert first.status_code==200 and first.get_json()['status']=='success',first.get_json()
    assert second.status_code==200 and second.get_json()['status']=='success',second.get_json()
    material=w.Material.query.filter_by(code='SYN-INITIAL').one()
    keep=w.Material.query.filter_by(code='SYN-KEEP').one()
    initial=w.StockTransaction.query.filter_by(material_id=material.id).one()
    assert initial.reference_type=='material_initial'
    initial_id=initial.id
    saved=document_post(client,'/opening_stock/save',json={
        'date':'2020-01-01','warehouse_id':a.id,'remark':'合成原表头',
        'items':[{'material_id':material.id,'warehouse_id':a.id,'quantity':7,'price':0,
                  'remark':'合成原期初','location':a.name if location_on else ''},
                 {'material_id':keep.id,'warehouse_id':a.id,'quantity':2,'price':0,
                  'remark':'合成保留行','location':a.name if location_on else ''}]})
    assert saved.status_code==200 and saved.get_json()['status']=='success',saved.get_json()
    doc_id=saved.get_json()['doc_id']
    line=w.OpeningStock.query.filter_by(doc_id=doc_id,material_id=material.id).one()
    kept=w.OpeningStock.query.filter_by(doc_id=doc_id,material_id=keep.id).one()
    assert line.id==material.id, 'The synthetic fixture must really collide in the numeric ID domain'
    if legacy:
        initial.reference_type='opening_stock'
        w.db.session.commit()
    return dict(client=client,doc_id=doc_id,line_id=line.id,keep_line_id=kept.id,
                material_id=material.id,keep_material_id=keep.id,initial_id=initial_id,
                warehouse_id=a.id,location=a.name if location_on else '')


def _state():
    w.db.session.expire_all()
    return (
        [(row.id,row.stock) for row in w.Material.query.order_by(w.Material.id)],
        [(row.id,row.material_id,row.warehouse_id,row.quantity,row.reference_type,row.reference_id,row.remark)
         for row in w.StockTransaction.query.order_by(w.StockTransaction.id)],
        [(row.id,row.doc_id,row.material_id,row.quantity,row.remark,row.date)
         for row in w.OpeningStock.query.order_by(w.OpeningStock.id)],
        [(row.id,row.remark,row.date) for row in w.OpeningStockDoc.query.order_by(w.OpeningStockDoc.id)],
        [(row.material_id,row.warehouse_id,row.location,row.quantity)
         for row in w.LocationInventory.query.order_by(w.LocationInventory.id)],
    )


def _remove(case, mode):
    client=case['client']
    if mode=='doc':
        return document_post(client,f"/opening_stock/{case['doc_id']}/delete")
    if mode=='lines':
        return document_post(client,f"/opening_stock/{case['doc_id']}/lines/delete",json={'line_ids':[case['line_id']]})
    if mode=='all':
        from routes.opening_stock import OPENING_STOCK_PURGE_PHRASE
        return document_post(client,'/opening_stock/delete_all',
            json={'confirm':True,'confirm_phrase':OPENING_STOCK_PURGE_PHRASE})
    return document_post(client,'/opening_stock/'+mode,json={
        'doc_id':case['doc_id'],'date':'2021-01-01','warehouse_id':case['warehouse_id'],'remark':'尝试新表头',
        'items':[{'line_id':case['keep_line_id'],'material_id':case['keep_material_id'],
                  'warehouse_id':case['warehouse_id'],'quantity':2,'price':0,
                  'location':case['location'],'remark':'尝试修改保留行'}]})


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_paths_preserve_material_initial_transactions(source_scene,mode,location_on):
    case=_seed(source_scene,location_on,legacy=False)
    response=_remove(case,mode)
    assert response.status_code==200 and response.get_json()['status']=='success',response.get_json()
    assert w.db.session.get(w.Material,case['material_id']).stock==5
    initial=w.db.session.get(w.StockTransaction,case['initial_id'])
    assert initial is not None and initial.quantity==5 and initial.reference_type=='material_initial'
    assert w.db.session.get(w.OpeningStock,case['line_id']) is None
    assert w.StockTransaction.query.filter_by(reference_type='opening_stock',reference_id=case['line_id'],
        material_id=case['material_id']).count()==0
    if location_on:
        assert w.LocationInventory.query.filter_by(material_id=case['material_id'],warehouse_id=case['warehouse_id']).one().quantity==5
    assert w.StockTransaction.query.filter(w.StockTransaction.warehouse_id!=case['warehouse_id']).count()==0


@pytest.mark.parametrize('location_on',[False,True])
@pytest.mark.parametrize('mode',['doc','lines','all','save','batch_save'])
def test_five_real_paths_reject_ambiguous_legacy_sources_and_rollback_everything(source_scene,mode,location_on):
    case=_seed(source_scene,location_on,legacy=True)
    before=_state()
    response=_remove(case,mode)
    assert response.status_code==400 and response.get_json()['status']=='error',response.get_json()
    assert '无法安全区分' in response.get_json()['msg']
    assert _state()==before


def test_new_same_id_line_with_reserved_marker_remains_explicitly_unverified(source_scene):
    case=_seed(source_scene,False,legacy=False)
    transaction=w.StockTransaction.query.filter_by(reference_type='opening_stock',
        reference_id=case['line_id'],material_id=case['material_id']).one()
    transaction.remark='新增物料初始库存'
    w.db.session.commit()
    before=_state()
    response=_remove(case,'lines')
    assert response.status_code==400
    assert '无法安全区分' in response.get_json()['msg']
    assert _state()==before
