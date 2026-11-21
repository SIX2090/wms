from datetime import date
from io import BytesIO
from bs4 import BeautifulSoup
from openpyxl import load_workbook
import pytest

from tests.test_requisition_location_flow_integration import accepted, scene, wms


@pytest.mark.parametrize('scene', [False, True], indirect=True)
def test_rendered_transfer_uses_warehouses_and_separate_bins(scene):
    client, first, second, material, unit = scene
    wms.User.query.filter_by(username='u1-integration').one().role = 'warehouse'
    wms.db.session.commit()
    bins = wms.location_management_enabled()
    page = BeautifulSoup(client.get('/transfer/add').data, 'html.parser')
    header = {}
    for key, warehouse, location in [('from', 'U1仓A', 'Rack-1'), ('to', 'U1仓B', 'Rack-2')]:
        field = page.select_one(f'select[name={key}_warehouse][required]')
        assert field and field.select_one(f'option[value="{warehouse}"]')
        header[key + '_warehouse'] = warehouse
        control = page.select_one(f'input[name={key}_location][required]')
        assert bool(control) == bins
        if bins:
            header[key + '_location'] = location
    data = dict(date=date.today().isoformat(), header=header, items=[dict(material_id=material, unit_id=unit, quantity=4)])
    if bins:
        # A bin text that happens to equal a warehouse must not fill a missing warehouse.
        missing = dict(header, from_warehouse='', from_location='U1仓A')
        assert client.post('/transfer/save_table', json=dict(data, header=missing)).status_code == 400
        assert client.post('/transfer/save_table', json=dict(data, header=dict(header, to_location=''))).status_code == 400
    else:
        same = dict(header, to_warehouse=header['from_warehouse'], from_location='a', to_location='b')
        assert client.post('/transfer/save_table', json=dict(data, header=same)).status_code == 400
    oid = accepted(client.post('/transfer/save_table', json=data))['id']
    path = f'/transfer/{oid}'
    doc = BeautifulSoup(client.get(path).data, 'html.parser')
    for key, value in header.items():
        control = doc.select_one(f'[name={key}]')
        current = control.select_one('option[selected]')['value'] if control.name == 'select' else control['value']
        assert current == value
    records = BeautifulSoup(client.get('/transfer', query_string={'search': 'U1仓B'}).data, 'html.parser')
    assert records.select_one(f'a[href="{path}"]')
    for url in ('/transfer/export', path + '/export'):
        sheet = load_workbook(BytesIO(client.get(url).data)).active
        names, values = list(sheet.values)
        row = dict(zip(names, values))
        assert (row['调出仓库'], row['调入仓库']) == ('U1仓A', 'U1仓B')
        if bins:
            assert (row['调出库位'], row['调入库位']) == ('Rack-1', 'Rack-2')
    def balances():
        return [wms.get_warehouse_stock_quantities(wms.db.session.get(wms.Warehouse, wid))[material]
                for wid in (first, second)]
    assert balances() == [70, 80]
    accepted(client.post(path + '/complete'))
    assert balances() == [66, 84]
    assert client.post(path + '/complete').json['status'] == 'error'
    accepted(client.post(path + '/revert'))
    assert balances() == [70, 80]
