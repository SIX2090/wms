"""BTN-PENDING-008: new session rereads the committed repair, no inventory writes."""
import app as m
from tests.test_round26_input_http import http_case

def test_empty_fields_reopen_through_fresh_http_session_keeps_stock(http_case):
    clients, ids, _ = http_case
    with m.app.app_context():
        default=m.MaterialCategory(code='QA30-DEFAULT',name='默认分类')
        custom=m.MaterialCategory(code='QA30-KEEP',name='已有分类')
        other_unit=m.Unit(code='QA30-BOX',name='盒')
        m.db.session.add_all([default,custom,other_unit]);m.db.session.flush()
        m.db.session.get(m.Material,ids['material']).category_id=default.id
        a=m.Material(code='QA30-EMPTY-A',name='空字段A',unit_id=None,category_id=None,stock=0)
        b=m.Material(code='QA30-EMPTY-B',name='空字段B',unit_id=0,category_id=custom.id,stock=0)
        c=m.Material(code='QA30-KEEP-C',name='完整字段C',unit_id=other_unit.id,category_id=custom.id,stock=0)
        m.db.session.add_all([a,b,c]);m.db.session.commit()
        expected={a.id:(ids['unit'],default.id),b.id:(ids['unit'],custom.id),c.id:(other_unit.id,custom.id)}
    def inventory():
        with m.app.app_context():
            return ([(x.id,x.stock) for x in m.Material.query.order_by(m.Material.id)],
                    [(x.material_id,x.warehouse_id,x.quantity) for x in m.StockTransaction.query.order_by(m.StockTransaction.id)],
                    [(x.material_id,x.warehouse_id,x.quantity) for x in m.LocationInventory.query.order_by(m.LocationInventory.id)])
    before=inventory()
    response=clients('warehouse').post('/material/fix_empty_fields',json={})
    assert response.status_code==200 and '已修复 2 条' in response.json['msg']
    reopened=clients('warehouse')
    for material_id,(unit,category) in expected.items():
        record=reopened.get(f'/material/{material_id}')
        assert record.status_code==200 and record.json['status']=='success'
        assert (record.json['material']['unit_id'],record.json['material']['category_id'])==(unit,category)
    assert inventory()==before
