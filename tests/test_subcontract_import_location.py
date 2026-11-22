"""委外发料和收货逐单保留库位并按原库位过账。"""
from io import BytesIO

import pytest
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook

import app as wms
from tests.test_bug_2026_08_16_001_subcontract_location_inventory import client, _enable_location_mgmt


@pytest.mark.parametrize('kind,number,quantity,code,model,number_field', [
    ('issue', '发料单号', '数量', 'M-RAW', wms.SubcontractIssue, 'issue_no'),
    ('receive', '入库单号', '收货数量', 'M-FG', wms.SubcontractReceive, 'receive_no'),
])
def test_import_post_print_and_reverse_at_the_selected_bin(client, kind, number, quantity, code, model, number_field):
    _enable_location_mgmt(True)
    base = '/subcontract_' + kind
    location = '主仓-A1'
    def upload(bins):
        book = Workbook()
        book.active.append([number, '委外加工单号', '物料编码', quantity, '库位'])
        for bin_name in bins:
            book.active.append(['BIN-TEST', 'SC001', code, 2, bin_name])
        stream = BytesIO()
        book.save(stream)
        stream.seek(0)
        return client.post(base + '/import', data={'file': (stream, 'bins.xlsx')})
    for bins in ([''], [location, 'B2']):
        response = upload(bins)
        assert response.status_code == 400 and '库位' in response.json['msg']
        with wms.app.app_context():
            assert model.query.filter_by(**{number_field: 'BIN-TEST'}).count() == 0
    response = upload([location, ''])
    assert response.json['status'] == 'success', response.json
    with wms.app.app_context():
        order = model.query.filter_by(**{number_field: 'BIN-TEST'}).one()
        key = order.id
        assert order.location == location and len(order.items) == 2
        order.location = ''
        wms.db.session.commit()
    page = BeautifulSoup(client.get(base).data, 'html.parser')
    assert page.select_one('input[data-posting-location][required]')
    path = f'{base}/{key}'
    assert client.post(path + '/complete').status_code == 400
    assert client.post(path + '/complete', json={'location': location}).json['status'] == 'success'
    for url in (base + '/export', path + '/print_excel'):
        data = client.get(url)
        assert data.status_code == 200
        sheet = load_workbook(BytesIO(data.data), read_only=True).active
        assert any(location in str(value) for row in sheet.values for value in row)
    assert location in client.get(path + '/print').get_data(as_text=True)
    assert client.post(path + '/revert').json['status'] == 'success'
    with wms.app.app_context():
        assert wms.db.session.get(model, key).location == location
