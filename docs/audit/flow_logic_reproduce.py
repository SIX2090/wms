import os,sys,json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT / 'app'))
os.environ.update(DATABASE_URL='sqlite:///:memory:',WMS_ALLOW_INSECURE_COOKIE='1',
                  WMS_NO_DB_TOUCH='1',WMS_SKIP_AUTO_UPDATE='1',WMS_THREE_LEDGER_ASSERT='0')
import app as w
from werkzeug.security import generate_password_hash
w.app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
results=[]

def setup():
    with w.app.app_context():
        assert str(w.db.engine.url)=='sqlite:///:memory:'
        w.db.session.remove();w.db.drop_all();w.db.create_all()
        user=w.User(username='logic-review-fixture',password_hash=generate_password_hash('test-only'),role='admin',status='active')
        each=w.Unit(code='EACH',name='个');box=w.Unit(code='BOX',name='箱')
        wh=w.Warehouse(code='WA',name='审计仓A',status='active',is_default=True)
        supplier=w.Supplier(code='S1',name='审计供应商');customer=w.Customer(code='C1',name='审计客户')
        w.db.session.add_all([user,each,box,wh,supplier,customer]);w.db.session.flush()
        mat=w.Material(code='M1',name='审计物料',unit_id=each.id,price=5,stock=100)
        w.db.session.add(mat);w.db.session.flush()
        w.db.session.add(w.StockTransaction(material_id=mat.id,quantity=100,transaction_type='opening',warehouse_id=wh.id,location=wh.name))
        bom=w.BOM(bom_no='B1',product_code='P1',product_name='审计产品',version='V1',status='active')
        w.db.session.add(bom);w.db.session.flush()
        w.db.session.add(w.BOMItem(bom_id=bom.id,material_id=mat.id,unit_id=each.id,quantity=2,unit_cost=5,total_cost=10))
        w.db.session.commit()
        ids=dict(user=user.id,each=each.id,box=box.id,wh=wh.id,mat=mat.id,bom=bom.id,supplier=supplier.id,customer=customer.id)
    client=w.app.test_client();client.environ_base['HTTP_X_REQUESTED_WITH']='XMLHttpRequest'
    with client.session_transaction() as session:session['_user_id']=str(ids['user']);session['_fresh']=True
    return client,ids

def call(client,url,body=None):
    response=client.post(url,json=body or {})
    return dict(http=response.status_code,body=response.get_json())

client,ids=setup()
data=dict(order_id=ids['bom'],order_no='B1',header=dict(product_code='P1',product_name='审计产品',version='V1',status='active'),
          items=[dict(code='M1',quantity=2,unit_id=ids['box'],price=5)])
saved=call(client,'/bom/save_table',data)
created=call(client,f"/bom/{ids['bom']}/create_requisition",dict(warehouse_id=ids['wh']))
rid=created['body'].get('id');completed=call(client,f'/requisition/{rid}/complete')
with w.app.app_context():
    req=w.db.session.get(w.ProductionRequisition,rid);mat=w.db.session.get(w.Material,ids['mat'])
    results.append(dict(case='bom_unit_mismatch',save=saved,create=created,complete=completed,stock=mat.stock,
                        material_unit=mat.unit.name,line_unit=req.items[0].unit.name,line_quantity=req.items[0].quantity))

client,ids=setup();created=call(client,f"/bom/{ids['bom']}/create_requisition",dict(warehouse_id=ids['wh']))
rid=created['body']['id']
with w.app.app_context():w.db.session.get(w.Warehouse,ids['wh']).status='inactive';w.db.session.commit()
completed=call(client,f'/requisition/{rid}/complete')
with w.app.app_context():results.append(dict(case='requisition_inactive_warehouse',create=created,complete=completed,stock=w.db.session.get(w.Material,ids['mat']).stock,warehouse_status=w.db.session.get(w.Warehouse,ids['wh']).status))

client,ids=setup()
with w.app.app_context():
    so=w.SalesOrder(order_no='SO1',customer_id=ids['customer'],warehouse='审计仓A',warehouse_id=ids['wh'],status='confirmed')
    w.db.session.add(so);w.db.session.flush()
    si=w.SalesOrderItem(sales_order_id=so.id,material_id=ids['mat'],quantity=10,price=5,amount=50,shipped_quantity=0)
    w.db.session.add(si);w.db.session.flush()
    out=w.OutOrder(order_no='OUT1',business_type='销售出库',warehouse='审计仓A',status='pending',source_sales_order_id=so.id)
    w.db.session.add(out);w.db.session.flush();w.db.session.add(w.OutOrderItem(out_order_id=out.id,material_id=ids['mat'],quantity=10,price=5,amount=50,source_sales_order_item_id=si.id));w.db.session.commit()
    oid=out.id;sid=si.id;soid=so.id
sold=call(client,f'/out_order/{oid}/complete')
with w.app.app_context():
    ret=w.InOrder(order_no='SR1',business_type='销售退货入库',warehouse='审计仓A',status='pending',customer_id=ids['customer'],source_sales_order_id=soid)
    w.db.session.add(ret);w.db.session.flush();w.db.session.add(w.InOrderItem(in_order_id=ret.id,material_id=ids['mat'],quantity=4,price=5,amount=20,source_sales_order_item_id=sid));w.db.session.commit();retid=ret.id
returned=call(client,f'/in_order/{retid}/complete');reverted=call(client,f'/out_order/{oid}/revert')
with w.app.app_context():results.append(dict(case='sales_source_revert_after_return',sale_complete=sold,return_complete=returned,original_revert=reverted,stock=w.db.session.get(w.Material,ids['mat']).stock,shipped_quantity=w.db.session.get(w.SalesOrderItem,sid).shipped_quantity,original_status=w.db.session.get(w.OutOrder,oid).status,return_status=w.db.session.get(w.InOrder,retid).status))

client,ids=setup()
with w.app.app_context():
    ino=w.InOrder(order_no='IN1',business_type='采购入库',warehouse='审计仓A',status='pending',supplier_id=ids['supplier'])
    w.db.session.add(ino);w.db.session.flush()
    item=w.InOrderItem(in_order_id=ino.id,material_id=ids['mat'],quantity=10,price=5,amount=50)
    w.db.session.add(item);w.db.session.commit();iid=ino.id;sourceid=item.id
received=call(client,f'/in_order/{iid}/complete')
with w.app.app_context():
    ret=w.OutOrder(order_no='PR1',business_type='采购退货出库',warehouse='审计仓A',status='pending',source_in_order_id=iid,source_in_order_no='IN1')
    w.db.session.add(ret);w.db.session.flush();w.db.session.add(w.OutOrderItem(out_order_id=ret.id,material_id=ids['mat'],quantity=4,price=5,amount=20,source_in_order_item_id=sourceid));w.db.session.commit();retid=ret.id
returned=call(client,f'/out_order/{retid}/complete');reverted=call(client,f'/in_order/{iid}/revert')
with w.app.app_context():results.append(dict(case='purchase_source_revert_after_return',receipt_complete=received,return_complete=returned,original_revert=reverted,stock=w.db.session.get(w.Material,ids['mat']).stock,original_status=w.db.session.get(w.InOrder,iid).status,return_status=w.db.session.get(w.OutOrder,retid).status))

for mode in ['sale','sales_return','purchase_return']:
    client,ids=setup()
    with w.app.app_context():
        if mode=='purchase_return':
            source=w.InOrder(order_no='SOURCE-IN',business_type='采购入库',warehouse='审计仓A',status='pending',supplier_id=ids['supplier'])
            w.db.session.add(source);w.db.session.flush()
            line=w.InOrderItem(in_order_id=source.id,material_id=ids['mat'],quantity=10,price=5,amount=50)
            w.db.session.add(line);w.db.session.commit();sourceid=source.id;lineid=line.id
        else:
            source=w.SalesOrder(order_no='SOURCE-SO',customer_id=ids['customer'],warehouse='审计仓A',warehouse_id=ids['wh'],status='confirmed')
            w.db.session.add(source);w.db.session.flush()
            line=w.SalesOrderItem(sales_order_id=source.id,material_id=ids['mat'],quantity=10,price=5,amount=50,shipped_quantity=0)
            w.db.session.add(line);w.db.session.flush()
            outbound=w.OutOrder(order_no='SOURCE-OUT',business_type='销售出库',warehouse='审计仓A',status='pending',source_sales_order_id=source.id)
            w.db.session.add(outbound);w.db.session.flush()
            if mode=='sales_return':w.db.session.add(w.OutOrderItem(out_order_id=outbound.id,material_id=ids['mat'],quantity=10,price=5,amount=50,source_sales_order_item_id=line.id))
            w.db.session.commit();sourceid=source.id;lineid=line.id;outid=outbound.id
    if mode=='purchase_return':call(client,f'/in_order/{sourceid}/complete')
    if mode=='sales_return':call(client,f'/out_order/{outid}/complete')
    items=[dict(code='M1',quantity=6,price=5) for _ in range(2)]
    payload=dict(order_no='DUPLICATE-ROWS',warehouse='审计仓A',items=items)
    if mode=='purchase_return':
        payload.update(business_type='采购退货出库',customer='审计供应商',source_in_order_id=sourceid)
        for item in items:item['source_in_order_item_id']=lineid
        created=call(client,'/out_order/add',payload);target='out_order'
    elif mode=='sales_return':
        payload.update(business_type='销售退货入库',customer_id=ids['customer'],source_sales_order_id=sourceid)
        for item in items:item['source_sales_order_item_id']=lineid
        created=call(client,'/in_order/add',payload);target='in_order'
    else:
        payload.update(order_id=outid,business_type='销售出库',customer='审计客户')
        for item in items:item['source_sales_order_item_id']=lineid
        created=call(client,'/out_order/add',payload);target='out_order'
    bid=(created.get('body') or {}).get('id');completed=call(client,f'/{target}/{bid}/complete') if bid else None
    with w.app.app_context():
        results.append(dict(case='duplicate_source_rows_'+mode,create=created,complete=completed,source_quantity=10,current_row_quantities=[6,6],stock=w.db.session.get(w.Material,ids['mat']).stock))

(ROOT / 'app' / 'logs' / 'flow_logic_proof.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(results,ensure_ascii=False))
