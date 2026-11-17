"""本年/跨月查询按物料汇总，页面、导出和联查使用同一期间。"""
from datetime import datetime
import io
from urllib.parse import parse_qs, urlparse

from openpyxl import load_workbook
import app as m

from tests.test_bug_2026_10_26_003_monthly_report import monthly, query


def test_year_query_has_one_period_row_per_material(monthly):
    data = query(monthly, start_month='2026-01', end_month='2026-10')
    rows = data['data']
    assert len({r['material_code'] for r in rows}) == len(rows)
    assert data['total'] == data['summary']['material_count'] == len(rows)
    assert 'month' not in {c['field'] for c in data['columns']}
    assert all('month' not in row for row in rows)
    row = next(r for r in rows if r['material_code'] == 'MONTH-A')
    assert [row[k] for k in ('beginning_quantity', 'in_quantity', 'out_quantity', 'ending_quantity')] == [0, 125, 40, 85]
    assert row['in_amount'] == 120 * 99 + 10
    args = parse_qs(urlparse(row['ledger_url']).query)
    assert args['start_date'] == ['2026-01-01']
    assert args['end_date'] == ['2026-10-31']
    assert 'MONTH-FUTURE' not in {r['material_code'] for r in rows}
    for total in data['summary']['unit_totals']:
        for field in ('beginning_quantity', 'in_quantity', 'out_quantity', 'ending_quantity'):
            assert total[field] == sum(r[field] for r in rows if r['unit'] == total['unit'])
    assert data['summary']['amount'] == sum(r['inventory_amount'] for r in rows)


def test_period_opening_and_document_count_are_not_month_sums(monthly):
    with m.app.app_context():
        for quantity, day in [(7, '2025-12-10'), (2, '2026-01-10'), (3, '2026-08-10'), (999, '2027-01-10')]:
            m.db.session.add(m.StockTransaction(
                material_id=monthly['mats']['CARRY'], warehouse_id=monthly['a'],
                quantity=quantity, transaction_type='in', created_at=datetime.fromisoformat(day),
                reference_type='period_test', reference_id=123))
        m.db.session.commit()
    data = query(monthly, start_month='2026-01', end_month='2026-10', material_code='MONTH-CARRY')
    assert data['total'] == 1
    row = data['data'][0]
    assert [row[k] for k in ('beginning_quantity', 'in_quantity', 'out_quantity', 'ending_quantity')] == [7, 14, 0, 21]
    assert row['document_count'] == 2  # 两笔跨月同来源只计一单，另有原始无来源流水。
    assert row['transaction_count'] == 3


def test_year_export_and_print_have_no_month_column(monthly):
    for url in ('/report/api/warehouse_monthly', '/report/warehouse_monthly/print_excel'):
        response = monthly['client'].get(url, query_string={
            'warehouse_id': monthly['a'], 'start_month': '2026-01', 'end_month': '2026-10',
            'export': 'excel', 'page_size': 1})
        assert response.status_code == 200
        book = load_workbook(io.BytesIO(response.data), read_only=True)
        try:
            cells = list(book.active.iter_rows(values_only=True))
        finally:
            book.close()
        assert not any('月份' in row for row in cells)
        hits = [row for row in cells if 'MONTH-A' in row]
        assert len(hits) == 1
        assert hits[0][0] == 'MONTH-A'
