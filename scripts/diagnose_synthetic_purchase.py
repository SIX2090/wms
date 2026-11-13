"""Finite synthetic purchase-receipt diagnostic; standard isolated Linux CI only.

No URLs, accounts, databases, quantities or real document IDs are accepted.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]


def diagnose():
    # Shared initializer verifies the authentic OS boundary, rejects preloaded
    # app/config and inherited targets, then proves the new memory engine.
    sys.path.insert(0, str(ROOT / 'scripts'))
    from perf_runtime import initialize_synthetic_app, relative_target
    from diagnose_synthetic_push import _check
    w, username, password = initialize_synthetic_app()
    stages, snapshots = [], []
    nonce = uuid.uuid4().hex
    with w.app.app_context():
        # This finite positive scenario explicitly selects these settings only
        # inside the newly-created synthetic memory database.
        w.set_system_setting('location_management_enabled', '0')
        w.set_system_setting('purchase_order_to_in_order_enabled', '1')
        unit = w.Unit(code='PD-U-' + nonce, name='合成个-' + nonce)
        supplier = w.Supplier(code='PD-S-' + nonce, name='合成供应商-' + nonce)
        warehouses = [w.Warehouse(code='PD-'+letter+'-'+nonce, name='合成采购仓'+letter+'-'+nonce,
                                  is_default=letter=='A', status='active') for letter in ('A','B')]
        material = w.Material(code='PD-M-' + nonce, name='合成采购物料', unit=unit,
                              supplier=supplier, stock=0, price=2)
        w.db.session.add_all([unit,supplier,*warehouses,material]);w.db.session.commit()
        material_id, supplier_id, unit_id = material.id, supplier.id, unit.id
        warehouse_ids = [warehouse.id for warehouse in warehouses]
        warehouse_name = warehouses[0].name
        client = w.app.test_client()
        login = client.post('/login',data={'username':username,'password':password},follow_redirects=False)
        _check(login.status_code in (200,302), '合成登录失败')
        with client.session_transaction() as session:
            _check(bool(session.get('_user_id')), '合成登录未生效')

        def request(stage, path, method='post', **kwargs):
            relative_target(path)
            _check(method in ('get','post'), '只允许有限诊断请求方法')
            start = time.perf_counter()
            response = getattr(client,method)(path,follow_redirects=False,**kwargs)
            stages.append(dict(stage=stage,http_status=response.status_code,
                               elapsed_ms=round((time.perf_counter()-start)*1000,3)))
            _check(response.status_code==200, stage+' HTTP失败')
            if method=='get':
                return response
            result = response.get_json()
            _check(isinstance(result,dict) and result.get('status')=='success',stage+' 业务失败')
            return result

        body = dict(applicant='合成申请人',department='合成采购',reason='独立合成诊断',
                    items=[dict(material_id=material_id,quantity=10,estimated_price=2,
                                unit_id=unit_id,supplier_id=supplier_id)])
        headers = {'X-Idempotency-Key':'purchase-diag-'+nonce}
        saved = request('save_request','/purchase_request/add',json=body,headers=headers)
        request_id = saved['id']
        replay = request('replay_save','/purchase_request/add',json=body,headers=headers)
        _check(replay.get('id')==request_id and w.PurchaseRequest.query.count()==1,'同键保存生成重复申请')
        request('approve_request',f'/purchase_request/{request_id}/approve')
        pushed = request('push_purchase_order',f'/purchase_request/{request_id}/create_purchase_order',json={})
        order_id = pushed['id']
        repeated = request('repeat_purchase_push',f'/purchase_request/{request_id}/create_purchase_order',json={})
        _check(repeated.get('id')==order_id and w.PurchaseOrder.query.count()==1,'全部下推重试产生重复采购单')
        order = w.db.session.get(w.PurchaseOrder,order_id)
        _check(len(order.items)==1 and order.purchase_request_id==request_id,'采购来源或行数错误')
        order_item_id = order.items[0].id

        def snapshot(stage, received, pushed_quantity):
            w.db.session.expire_all()
            req = w.db.session.get(w.PurchaseRequest,request_id)
            po = w.db.session.get(w.PurchaseOrder,order_id)
            item = w.db.session.get(w.PurchaseOrderItem,order_item_id)
            _check(len(req.items)==1 and item.purchase_request_item_id==req.items[0].id,'申请/采购来源关联丢失')
            request_row = w.build_purchase_request_execution(list(req.items),req)[req.items[0].id]
            order_row = w.build_purchase_order_execution(po)[item.id]
            stock = float(w.db.session.get(w.Material,material_id).stock)
            wh = [w.db.session.get(w.Warehouse,identity) for identity in warehouse_ids]
            balances = [float(w.get_warehouse_stock_quantities(warehouse).get(material_id,0)) for warehouse in wh]
            _check(request_row['request_quantity']==10 and request_row['ordered_quantity']==10,'申请或下单数量变化')
            _check(request_row['received_quantity']==received and request_row['remaining_to_receive']==10-received,
                   '申请实收/待收不跟随实际完成状态')
            _check(order_row['pushed_quantity']==pushed_quantity and order_row['completed_quantity']==received,
                   '采购预留与实际完成数量混淆')
            _check(order_row['pending_receive_quantity']==pushed_quantity-received
                   and order_row['remaining_to_push']==10-pushed_quantity,'采购待收/待推数量异常')
            _check(stock==received and balances==[received,0],'入库/反提交库存或双仓归属异常')
            filters = dict(warehouse_id=wh[0].id,warehouse=wh[0].name,warehouse_code=wh[0].code,
                           start_date=None,end_date=None,supplier_id=0,supplier='',material_code='',status='',
                           sort_field='',sort_order='asc',page=1,page_size=20,export='')
            receipts = w.InOrder.query.filter_by(source_purchase_order_id=order_id).all()
            report = w.SQL_PAGED_REPORT_BUILDERS['purchase_order_execution'](filters)[1]
            # Before an inbound assigns a warehouse, the established report
            # deliberately excludes unassigned purchase orders; do not change it.
            _check(len(report)==int(bool(receipts)),'报表错误归属尚无入库仓库的采购单')
            if report:
                _check(report[0]['received_quantity']==received and report[0]['remaining_quantity']==10-received,
                       '采购执行报表实收/待收异常')
            other_filters=dict(filters,warehouse_id=wh[1].id,warehouse=wh[1].name,warehouse_code=wh[1].code)
            other_report=w.SQL_PAGED_REPORT_BUILDERS['purchase_order_execution'](other_filters)[1]
            _check(not other_report,'采购执行报表错误归属另一仓库')
            _check(all(len(receipt.items)==1 and receipt.items[0].source_purchase_order_item_id==item.id
                       for receipt in receipts),'入库来源行关联丢失')
            snapshots.append(dict(stage=stage,request_received=float(request_row['received_quantity']),
                                  request_remaining=float(request_row['remaining_to_receive']),
                                  purchase_pushed=float(order_row['pushed_quantity']),
                                  purchase_completed=float(order_row['completed_quantity']),
                                  purchase_pending=float(order_row['pending_receive_quantity']),
                                  purchase_remaining_to_push=float(order_row['remaining_to_push']),
                                  global_stock=stock,warehouse_a=balances[0],warehouse_b=balances[1],
                                  report_received=float(report[0]['received_quantity']) if report else None,
                                  report_remaining=float(report[0]['remaining_quantity']) if report else None,
                                  report_has_warehouse_assignment=bool(receipts),report_b_rows=len(other_report),
                                  receipt_count=len(receipts)))

        snapshot('ordered_no_receipt',0,0)
        partial = request('create_partial_receipt',f'/purchase_order/{order_id}/create_in_order',json={
            'warehouse':warehouse_name,'items':[dict(item_id=order_item_id,quantity=4)]})['id']
        snapshot('partial_draft',0,4)
        request('complete_partial',f'/in_order/{partial}/complete?force=1')
        snapshot('partial_completed',4,4)
        request('revert_partial',f'/in_order/{partial}/revert')
        snapshot('partial_reverted',0,4)
        request('recomplete_partial',f'/in_order/{partial}/complete?force=1')
        snapshot('partial_recompleted',4,4)
        final = request('create_remaining_receipt',f'/purchase_order/{order_id}/create_in_order',json={
            'warehouse':warehouse_name,'items':[dict(item_id=order_item_id,quantity=6)]})['id']
        _check(final!=partial,'后续收货错误复用了前单')
        snapshot('remaining_draft',4,10)
        request('complete_remaining',f'/in_order/{final}/complete?force=1')
        snapshot('all_completed',10,10)
        report_url='/report/view/purchase_order_execution?'+urlencode(dict(warehouse_id=warehouse_ids[0],warehouse=warehouse_name))
        request('render_execution_report',report_url,method='get')
        _check(w.PurchaseRequest.query.count()==1 and w.PurchaseOrder.query.count()==1,'重复生成来源单据')
        receipt_count=w.InOrder.query.filter_by(source_purchase_order_id=order_id).count()
        _check(receipt_count==2,'生成了非预期入库单')
        return dict(schema=1,scenario='purchase-receipt',transport='flask-test-client',
                    database='sqlite:///:memory:',request_count=w.PurchaseRequest.query.count(),
                    purchase_order_count=w.PurchaseOrder.query.count(),receipt_count=receipt_count,
                    location_management=False,stages=stages,snapshots=snapshots)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario',required=True,choices=('purchase-receipt',))
    parser.parse_args(argv)
    result=diagnose()
    print('WMS_SYNTHETIC_PURCHASE_DIAGNOSTIC='+json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':
    sys.exit(main())
