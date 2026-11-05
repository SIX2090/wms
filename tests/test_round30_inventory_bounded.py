"""043/044/072, fresh RAM per case; exact quantities, no nonempty deletes."""
from tests.document_revision_client import document_post
from contextlib import contextmanager
from datetime import datetime
import pytest
from sqlalchemy import event
import app as m
from tests.test_round26_input_http import http_case

@pytest.fixture
def bounded(http_case):
    clients,ids,_=http_case
    with m.app.app_context():engine=m.db.engine
    active=[False]
    def before(conn,cursor,statement,parameters,context,many):
        if active[0] and statement.lstrip().upper().startswith(('DROP ','ALTER ','CREATE ')):
            raise AssertionError('No schema changes in bounded request')
    def after(conn,cursor,statement,parameters,context,many):
        if active[0] and statement.lstrip().upper().startswith('DELETE ') and cursor.rowcount:
            raise AssertionError('No nonempty deletion is allowed; request must roll back')
    event.listen(engine,'before_cursor_execute',before);event.listen(engine,'after_cursor_execute',after)
    @contextmanager
    def requests():
        active[0]=True
        try:yield
        finally:active[0]=False
    try:yield clients,ids,requests
    finally:
        event.remove(engine,'before_cursor_execute',before);event.remove(engine,'after_cursor_execute',after)

def stock(ids):
    with m.app.app_context():
        warehouses=[m.db.session.get(m.Warehouse,ids[k]) for k in ('a','b')]
        return ([m.get_warehouse_stock_quantities(w).get(ids['material'],0) for w in warehouses],
                m.db.session.get(m.Material,ids['material']).stock,
                [(x.id,x.material_id,x.warehouse_id,x.quantity) for x in m.StockTransaction.query.order_by(m.StockTransaction.id)])

def seed_locations(ids,a,b):
    m.set_system_setting('location_management_enabled','0')
    for key,quantity in [('a',a),('b',b)]:
        wh=m.db.session.get(m.Warehouse,ids[key])
        m.db.session.add(m.LocationInventory(material_id=ids['material'],warehouse_id=wh.id,location=wh.name,quantity=quantity))

def test_043_period_movement_force_only_creates_plus_two_draft(bounded):
    clients,ids,requests=bounded
    with m.app.app_context():
        check=m.db.session.get(m.InventoryCheck,ids['check']);check.check_no='QA30-043-ONLY'
        item=m.InventoryCheckItem.query.filter_by(inventory_check_id=check.id).one()
        item.actual_stock=12;item.difference=2
        m.db.session.add(m.StockTransaction(material_id=ids['material'],warehouse_id=ids['a'],
            location='QA27-A',quantity=3,transaction_type='in',created_at=datetime.now()))
        m.db.session.get(m.Material,ids['material']).stock=33
        seed_locations(ids,13,20);m.db.session.commit()
    before=stock(ids)
    with requests():
        warning=document_post(clients('warehouse'),f"/check/{ids['check']}/complete",json={'force':False})
        assert warning.status_code==200 and warning.json['code']=='period_movement'
        assert warning.json['status']=='confirm' and warning.json['count']==1
        assert stock(ids)==before
        done=document_post(clients('warehouse'),f"/check/{ids['check']}/complete",json={'force':True})
        assert done.status_code==200 and done.json['status']=='success',done.json
    assert stock(ids)==before and before[0]==[13,20]
    with m.app.app_context():
        assert m.db.session.get(m.InventoryCheck,ids['check']).status=='completed'
        draft=m.AdjustmentOrder.query.filter_by(source_type='check',source_id=ids['check']).one()
        assert draft.status=='pending' and draft.warehouse=='QA27-A'
        assert m.AdjustmentOrderItem.query.filter_by(adjustment_order_id=draft.id).one().quantity==2
    # Deliberately do not revert the check: that would delete its draft.

def test_044_save_complete_and_reverse_plus_two_only_in_warehouse_a(bounded):
    clients,ids,requests=bounded
    with m.app.app_context():
        seed_locations(ids,10,20);m.db.session.commit()
    before=stock(ids)
    with requests():
        saved=document_post(clients('warehouse'),'/adjustment/add',json={'adjustment_type':'surplus',
            'warehouse':'QA27-A','warehouse_id':ids['a'],
            'items':[{'material_id':ids['material'],'quantity':2,'location':'QA27-A','reason':'QA30 +2'}]})
        assert saved.status_code==200 and saved.json['status']=='success',saved.json
        adjustment_id=saved.json['id']
        with m.app.app_context():
            assert m.db.session.get(m.AdjustmentOrder,adjustment_id).status=='pending'
        assert stock(ids)==before
        complete=document_post(clients('warehouse'),f'/adjustment/{adjustment_id}/complete',json={})
        assert complete.status_code==200 and complete.json['status']=='success',complete.json
        assert stock(ids)[0:2]==([12,20],32)
        with m.app.app_context():
            assert m.db.session.get(m.AdjustmentOrder,adjustment_id).status=='completed'
        reversed=document_post(clients('warehouse'),f'/adjustment/{adjustment_id}/revert',json={})
        assert reversed.status_code==200 and reversed.json['status']=='success',reversed.json
    assert stock(ids)[0:2]==([10,20],30)
    with m.app.app_context():
        assert m.db.session.get(m.AdjustmentOrder,adjustment_id).status=='pending'
    after=stock(ids)[2]
    assert after[:len(before[2])]==before[2] and len(after)==len(before[2])+2

def test_072_reverse_exact_three_transfer_restores_both_warehouses(bounded):
    clients,ids,requests=bounded
    with m.app.app_context():
        transfer=m.TransferOrder(transfer_no='QA30-072-ONLY',status='completed',
            from_warehouse='QA27-A',to_warehouse='QA27-B',from_location='QA27-A',to_location='QA27-B')
        m.db.session.add(transfer);m.db.session.flush();transfer_id=transfer.id
        m.db.session.add(m.TransferOrderItem(transfer_order_id=transfer.id,material_id=ids['material'],quantity=3,unit_id=ids['unit']))
        for key,delta,kind in [('a',-3,'transfer_out'),('b',3,'transfer_in')]:
            m.db.session.add(m.StockTransaction(material_id=ids['material'],warehouse_id=ids[key],
                location='QA27-'+key.upper(),quantity=delta,transaction_type=kind,reference_type='transfer',reference_id=transfer.id))
        seed_locations(ids,7,23);m.db.session.commit()
    before=stock(ids)
    assert before[0:2]==([7,23],30)
    with requests():
        response=document_post(clients('warehouse'),f'/transfer/{transfer_id}/revert',json={})
        assert response.status_code==200 and response.json['status']=='success',response.json
    after=stock(ids)
    assert after[0:2]==([10,20],30)
    assert after[2][:len(before[2])]==before[2] and len(after[2])==len(before[2])+2
    with m.app.app_context():
        assert m.db.session.get(m.TransferOrder,transfer_id).status=='pending'
        assert m.TransferOrderItem.query.filter_by(transfer_order_id=transfer_id).count()==1


def test_044_existing_detail_rebuild_stops_before_deletion(http_case,monkeypatch):
    clients,ids,_=http_case
    with m.app.app_context():
        draft=m.AdjustmentOrder(adjustment_no='QA30-044-GUARD',adjustment_type='surplus',
            source_type='manual',warehouse='QA27-A',status='pending')
        m.db.session.add(draft);m.db.session.flush();draft_id=draft.id
        detail=m.AdjustmentOrderItem(adjustment_order_id=draft.id,material_id=ids['material'],quantity=2,location='QA27-A')
        m.db.session.add(detail);m.db.session.commit();detail_id=detail.id
        query_type=type(m.AdjustmentOrderItem.query)
    original=query_type.delete
    attempts=[]
    def refuse_existing(query,*a,**k):
        if query.column_descriptions[0].get('entity') is m.AdjustmentOrderItem:
            attempts.extend(row.id for row in query.all())
            raise RuntimeError('QA30 stop before detail deletion')
        return original(query,*a,**k)
    monkeypatch.setattr(query_type,'delete',refuse_existing)
    before=stock(ids)
    response=document_post(clients('warehouse'),'/adjustment/add',json={'id':draft_id,
        'adjustment_type':'surplus','warehouse_id':ids['a'],'warehouse':'QA27-A',
        'items':[{'material_id':ids['material'],'quantity':3,'location':'QA27-A'}]})
    # This controlled failure is caused by the explicit no-delete stand-in.
    assert response.status_code==400 and response.json['status']=='error'
    assert attempts==[detail_id] and stock(ids)==before
    with m.app.app_context():
        assert m.db.session.get(m.AdjustmentOrder,draft_id).status=='pending'
        assert m.db.session.get(m.AdjustmentOrderItem,detail_id).quantity==2
