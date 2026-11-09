"""Actual opening XLSX import; owned LPAC and literal-memory fixture required."""
from io import BytesIO
import pytest
from tests.test_money_route_synthetic_20261109 import money_case
from tests.test_opening_money_routes_20261109 import seed, state

@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('dry_run', [False, True])
@pytest.mark.parametrize('bad', [{'price': -1}, {'price': 'nan'}, {'price': 'bad'},
                                 {'price': '1e100'}, {'quantity': '1e100'}])
def test_bad_number_skips_only_its_row_without_hiding_the_following_valid_row(money_case, enabled, dry_run, bad):
    from openpyxl import Workbook
    c = money_case
    seed(c, enabled)
    before = state(c)
    before_doc_count = c.w.OpeningStockDoc.query.count()
    before_line_ids = {row.id for row in c.w.OpeningStock.query.all()}
    mat = c.w.db.session.get(c.w.Material, c.ids['material'])
    wh = c.w.db.session.get(c.w.Warehouse, c.wh1)
    invalid = dict(quantity=1, price=5, **{})
    invalid.update(bad)
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(['仓库编码', '物料编码', '数量', '单价'])
    sheet.append([wh.code, mat.code, invalid['quantity'], invalid['price']])
    sheet.append([wh.code, mat.code, 1.15, 3.5])
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    response = c.client.post('/opening_stock/import', data={
        'file': (stream, 'owned-synthetic.xlsx'), 'dry_run': '1' if dry_run else '0'})
    assert response.status_code == 200, response.json
    assert response.json['status'] == 'success', response.json
    assert (response.json['imported'], response.json['skipped']) == (1, 1), response.json
    c.w.db.session.remove()
    if dry_run:
        accepted = [row for row in response.json['rows'] if row['action'] == 'import']
        assert [(row['quantity'], row['price']) for row in accepted] == [(1.15, 3.5)], response.json
        assert state(c) == before
        assert c.w.OpeningStockDoc.query.count() == before_doc_count
    else:
        assert c.w.OpeningStockDoc.query.count() == before_doc_count + 1
        created = c.w.OpeningStock.query.filter(c.w.OpeningStock.id.notin_(before_line_ids)).one()
        assert (created.quantity, created.price, created.amount) == (1.15, 3.5, 4.03)
        assert c.w.db.session.get(c.w.Material, c.ids['material']).stock == pytest.approx(4.15)
        other = c.w.db.session.get(c.w.Warehouse, c.wh2)
        assert c.w.get_warehouse_stock_quantities(other)[c.ids['material']] == 2
        assert state(c)[3][:2] == before[3]
