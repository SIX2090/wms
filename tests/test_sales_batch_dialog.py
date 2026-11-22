"""新建、编辑销售订单均接入同一套明细批改。"""
import app as wms
from tests.test_document_create_number_conflicts import case  # noqa: F401


def test_sales_batch_dialog_on_add_and_edit(case):
    clients, ids = case
    with wms.app.app_context():
        customer = wms.Customer(code='BATCH-C', name='批改测试客户')
        wms.db.session.add(customer)
        wms.db.session.flush()
        order = wms.SalesOrder(order_no='SO-BATCH', customer_id=customer.id, warehouse_id=ids['a'])
        wms.db.session.add(order)
        wms.db.session.commit()
        order_id = order.id
    for path in ('/sales/add', f'/sales/{order_id}/edit'):
        response = clients[0].get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'openSalesBatchDialog(body, recalc)' in html
        assert 'window.prompt(\'批量修改字段' not in html
        assert html.count('id="salesBatchDialog"') == 1
        assert all(f'>{name}</option>' in html for name in ('数量', '单价', '税率（%）'))
        assert '/static/js/pages/sales-batch-dialog.js' in html
