"""Finance can reconcile opening lines and print their document across clients."""
from datetime import datetime, timedelta
from io import BytesIO

from bs4 import BeautifulSoup
from openpyxl import load_workbook

import app as w
from tests.test_document_print_flow import print_case
from tests.test_purchase_order_read_permissions import sign_in


def test_finance_opening_stock_reads_and_navigation(print_case):
    client, docs, _ = print_case
    sign_in(client, 'finance')
    with w.app.app_context():
        doc = w.db.session.get(w.OpeningStockDoc, docs['opening_stock'])
        doc_no = doc.doc_no
        line = doc.lines[0]
        line.remark = '甲仓期初行'
        w.db.session.add(w.OpeningStock(material_id=line.material_id, warehouse_id=2,
                                        quantity=0, price=3, amount=0, remark='乙仓未归单'))
        actor = w.User.query.filter_by(role='finance').one()
        token = 'synthetic-opening-reader'
        w.db.session.add(w.ApiToken(user_id=actor.id, token=w.hash_access_token(token),
                                    expires_at=datetime.now() + timedelta(days=1)))
        w.db.session.commit()

    home = BeautifulSoup(client.get('/mobile/').data, 'html.parser')
    mobile_link = home.select_one('main a[href^="/opening_stock"]')
    assert mobile_link and client.get(mobile_link['href']).status_code == 200
    assert not home.select('main a[href^="/opening_stock/add"]')
    mobile = w.app.test_client()
    headers = {'Authorization': f'Bearer {token}'}
    for wh, expected, excluded in [(1, '甲仓期初行', '乙仓未归单'), (2, '乙仓未归单', '甲仓期初行')]:
        page = client.get('/opening_stock', query_string={'warehouse_id': wh, 'search': 'PRINT-M'})
        assert page.status_code == 200
        table = BeautifulSoup(page.data, 'html.parser').table
        assert expected in table.get_text() and excluded not in table.get_text()
        result = mobile.get('/api/opening_stock', query_string={'warehouse_id': wh}, headers=headers)
        assert result.status_code == 200
        assert [item['remark'] for item in result.json['data']['items']] == [expected]
        if wh == 2:
            assert '未归单' in table.get_text() and result.json['data']['items'][0]['quantity'] == 0
    empty = client.get('/opening_stock?warehouse_id=999')
    assert '甲仓期初行' not in empty.get_data(as_text=True) and '仓库不存在' in empty.get_data(as_text=True)

    base = f"/opening_stock/{docs['opening_stock']}"
    detail = client.get(base)
    assert detail.status_code == 200
    html = BeautifulSoup(detail.data, 'html.parser')
    assert '甲仓期初行' in html.table.get_text() and '乙仓未归单' not in html.table.get_text()
    assert not html.select('button[onclick="saveDocument()"], a[href="/opening_stock/add"]')
    for path in [html.select_one('[data-wms-document-print]')['href'], base + '/print_preview']:
        response = client.get(path)
        assert response.status_code == 200 and doc_no in response.get_data(as_text=True)
    for path in [base + '/print_file', base + '/print_excel']:
        response = client.get(path)
        assert response.status_code == 200
        workbook = load_workbook(BytesIO(response.data), read_only=True)
        try:
            assert any(doc_no in str(cell) for row in workbook.active.values for cell in row)
        finally:
            workbook.close()
    for path in ['/opening_stock/save', base + '/date', base + '/delete', '/opening_stock/import']:
        assert client.post(path, json={}).status_code == 403
    assert client.get('/opening_stock/add', headers={'Accept': 'application/json'}).status_code == 403
    for path in ['/api/opening_stock', '/api/opening_stock/1']:
        assert mobile.post(path, headers=headers, json={}).status_code == 403

    sign_in(client, 'warehouse')
    assert 'saveDocument()' in client.get(base).get_data(as_text=True)
    assert client.get('/opening_stock/add').status_code == 200


def test_opening_stock_lines_query(print_case):
    from routes.opening_stock import opening_stock_lines_query

    with w.app.app_context():
        for search in ('PRINT-M', '打印物料', '样例规格'):
            assert [row.material.code for row in opening_stock_lines_query(1, search)] == ['PRINT-M']
        assert opening_stock_lines_query(2, '样例规格').all() == []
        assert opening_stock_lines_query(1, '查无此料').all() == []
