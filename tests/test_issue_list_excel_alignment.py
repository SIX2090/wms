from datetime import date
from io import BytesIO

from bs4 import BeautifulSoup
from openpyxl import load_workbook

from tests.test_requisition_location_flow_integration import scene, wms


def test_issue_list_and_export_sort_the_same_visible_rows(scene):
    client, warehouse, _, material, _ = scene
    wms.User.query.filter_by(username='u1-integration').one().role = 'warehouse'
    for code, name, amounts in [('A', 'A车间', [32, 2]), ('Z', 'Z车间', [11]), ('E', '空草稿', [])]:
        department = wms.Department(code=code, name=name)
        order = wms.OutOrder(order_no='LL-' + code, date=date.today(), warehouse='U1仓A',
                             department=department, business_type='领料单', purpose='试制',
                             contract_no='来源合同', project_name='试制工程', remark='仓管备注',
                             total_amount=sum(amounts), status='pending')
        wms.db.session.add(order)
        wms.db.session.flush()
        for amount in amounts:
            wms.db.session.add(wms.OutOrderItem(out_order_id=order.id, material_id=material,
                                                quantity=1, price=amount, amount=amount))
    wms.db.session.commit()
    for column in ['total_amount', 'customer']:
        page = client.get('/out_order', query_string={'warehouse_id': warehouse, 'sort': column,
                                                      'order': 'asc', 'search': 'LL-'})
        doc = BeautifulSoup(page.data, 'html.parser')
        link = doc.select_one('a[href^="/out_order/export?"]')['href']
        assert 'sort=' + column in link and 'order=asc' in link
        visible = [td.get_text(strip=True) for td in doc.select('tbody td[data-column-key=order_no]')]
        sheet = load_workbook(BytesIO(client.get(link).data)).active
        header, *values = sheet.values
        rows = [dict(zip(header, row)) for row in values]
        assert len(rows) == 4
        assert visible == [row['单据编号'] for row in rows]
        if column == 'customer':
            departments = [row['领料部门'] for row in rows]
            assert departments == sorted(departments)
        else:
            assert [row['金额'] for row in rows] == [None, 2, 11, 32]
        for row in rows:
            assert row['合同单号'] == '来源合同' and row['工程名称'] == '试制工程'
            assert row['用途'] == '试制' and row['备注'] == '仓管备注'
            assert row['状态'] == '未审核/待完成'


def test_manual_issue_accepts_blank_and_valid_department(scene):
    from tests.document_revision_client import document_post

    client, warehouse, _, _, _ = scene
    wms.User.query.filter_by(username='u1-integration').one().role = 'warehouse'
    dept = wms.Department(code='ISSUE', name='生产车间', status='active')
    wms.db.session.add(dept)
    wms.db.session.commit()
    payload = dict(business_type='领料单', warehouse_id=warehouse, location='Rack-1',
                   date=date.today().isoformat(), items=[dict(code='U1-M', quantity=1)])
    for invalid in ['xx', 999999]:
        assert client.post('/out_order/add', json=dict(payload, department_id=invalid)).status_code == 400
    assert wms.OutOrder.query.count() == 0
    response = client.post('/out_order/add', json=dict(payload, department_id=dept.id))
    assert response.status_code == 200, response.json
    oid = response.json['id']
    assert wms.db.session.get(wms.OutOrder, oid).department_id == dept.id
    update = f'/out_order/{oid}/update'
    assert document_post(client, update, json=dict(payload, department_id=999999)).status_code == 400
    assert wms.db.session.get(wms.OutOrder, oid).department_id == dept.id
    assert document_post(client, update, json=dict(payload, department_id='')).status_code == 200
    wms.db.session.expire_all()
    assert wms.db.session.get(wms.OutOrder, oid).department_id is None
