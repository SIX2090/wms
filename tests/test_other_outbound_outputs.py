"""Other outbound documents retain their identity and warehouse through the real UI routes."""
from io import BytesIO

from bs4 import BeautifulSoup
from openpyxl import load_workbook

from tests.test_requisition_location_flow_integration import accepted, scene, wms


def test_other_outbound_entry_print_export_and_posting(scene):
    client, first, second, material, _ = scene
    wms.User.query.filter_by(username='u1-integration').one().role = 'warehouse'
    wms.db.session.commit()
    form = BeautifulSoup(client.get('/other_out_order/add').data, 'html.parser')
    assert form.select_one('[name=business_type] option[selected]')['value'] == '其他出库'
    oid = accepted(client.post('/out_order/add', json={
        'business_type': '其他出库', 'warehouse_id': second, 'location': 'Rack-1',
        'customer': '现场领用单位', 'items': [dict(code='U1-M', quantity=4, price=2)],
    }))['id']
    root = f'/out_order/{oid}'
    edit = BeautifulSoup(client.get('/other_out_order/add', query_string=dict(order_id=oid)).data, 'html.parser')
    assert '编辑其他出库单' in edit.title.get_text()
    assert edit.select_one('[name=customer]')['value'] == '现场领用单位'
    listing = BeautifulSoup(client.get('/other_out_order', query_string=dict(warehouse_id=second)).data, 'html.parser')
    for path in [listing.select_one('a[href^="/out_order/export?"]')['href'], root + '/export']:
        sheet = load_workbook(BytesIO(client.get(path).data)).active
        header, record = list(sheet.values)
        assert sheet.title == '其他出库单'
        assert dict(zip(header, record))['客户/领用单位'] == '现场领用单位'
    printout = BeautifulSoup(client.get(root + '/print').data, 'html.parser')
    assert '客户/领用单位：现场领用单位' in printout.get_text(strip=True)
    sheet = load_workbook(BytesIO(client.get(root + '/print_excel').data)).active
    assert sheet.title == '其他出库单' and sheet['A2'].value == '客户/领用单位：现场领用单位'
    def balances():
        return [wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse, wid))[material]
                for wid in (first, second)]
    assert balances() == [70, 80]
    accepted(client.post(root + '/complete?force=1'))
    assert balances() == [70, 76]
    accepted(client.post(root + '/revert'))
    assert balances() == [70, 80]
