"""Purchase receipt reports must use completed inbound facts, not pushed counters."""
from datetime import date
import pytest
import app as m
from app import db, Warehouse, Unit, Material, Supplier, PurchaseOrder, PurchaseOrderItem, InOrder, InOrderItem

REPORTS = ['purchase_order_execution', 'supplier_purchase_summary', 'material_purchase_summary']


@pytest.fixture
def receipt_case(monkeypatch):
    monkeypatch.setitem(m.app.config, 'TESTING', True)
    with m.app.app_context():
        assert str(db.engine.url) == 'sqlite:///:memory:'
        db.drop_all()
        db.create_all()
        a = Warehouse(code='WHA', name='仓库A', status='active', is_default=True)
        b = Warehouse(code='WHB', name='仓库B', status='active')
        unit = Unit(code='PCS', name='件')
        supplier = Supplier(code='S1', name='测试供应商')
        db.session.add_all([a, b, unit, supplier]); db.session.flush()
        material = Material(code='M1', name='测试物料', unit_id=unit.id, stock=0)
        db.session.add(material); db.session.flush()
        order = PurchaseOrder(order_no='PO1', date=date.today(), supplier_id=supplier.id, status='pending')
        db.session.add(order); db.session.flush()
        item = PurchaseOrderItem(purchase_order_id=order.id, material_id=material.id,
                                 quantity=10, received_quantity=8, price=2, amount=20)
        db.session.add(item); db.session.flush()
        counter = [0]
        def inbound(quantity, warehouse, status='completed', source=item, order_id=None):
            counter[0] += 1
            document = InOrder(order_no='IN'+str(counter[0]), date=date.today(),
                               warehouse=warehouse, status=status, business_type='采购入库',
                               source_purchase_order_id=order.id if order_id is None else order_id)
            db.session.add(document); db.session.flush()
            db.session.add(InOrderItem(in_order_id=document.id, material_id=material.id,
                                       source_purchase_order_item_id=source.id if source else None,
                                       quantity=quantity, price=2, amount=quantity*2))
            db.session.flush()
            return document
        draft = inbound(8, a.name, 'pending')
        db.session.commit()
        yield dict(a=a, b=b, material=material, order=order, item=item, draft=draft, inbound=inbound,
                   supplier=supplier)
        db.session.remove()


def filters(warehouse, **kw):
    result = dict(warehouse_id=warehouse.id, warehouse=warehouse.name, warehouse_code=warehouse.code,
                  start_date=None, end_date=None, supplier_id=0, supplier='', material_code='', status='',
                  sort_field='', sort_order='asc', page=1, page_size=20, export='')
    result.update(kw)
    return result


def rows(kind, warehouse, **kw):
    return m.SQL_PAGED_REPORT_BUILDERS[kind](filters(warehouse, **kw))[1]


@pytest.mark.parametrize('kind', REPORTS)
def test_draft_complete_revert_receipt_facts(receipt_case, kind):
    c = receipt_case
    for status, received in [('pending', 0), ('completed', 8), ('pending', 0)]:
        c['draft'].status = status; db.session.commit()
        for export in ('', 'excel'):
            row = rows(kind, c['a'], export=export)[0]
            assert row['received_quantity'] == received
            assert row['remaining_quantity'] == 10-received
            assert row['received_amount'] == received*2
            assert row['remaining_amount'] == (10-received)*2
    assert c['item'].received_quantity == 8, 'reporting must not rewrite the pushed counter'


@pytest.mark.parametrize('kind', REPORTS)
def test_receipts_are_scoped_to_warehouse_name_or_historical_code(receipt_case, kind):
    c = receipt_case
    c['inbound'](2, c['a'].code)
    c['inbound'](3, c['b'].name)
    db.session.commit()
    assert rows(kind, c['a'])[0]['received_quantity'] == 2
    assert rows(kind, c['b'])[0]['received_quantity'] == 3
    assert m.build_purchase_order_execution(c['order'])[c['item'].id]['completed_quantity'] == 5
    assert rows(kind, c['a'])[0]['received_quantity'] + rows(kind, c['b'])[0]['received_quantity'] == 5


def test_legacy_header_only_links_allocate_once_and_preserve_receipt_totals(receipt_case):
    c = receipt_case
    c['item'].quantity = 3; c['item'].amount = 6
    second = PurchaseOrderItem(purchase_order_id=c['order'].id, material_id=c['material'].id,
                               quantity=7, received_quantity=0, price=2, amount=14)
    db.session.add(second); db.session.flush()
    c['inbound'](1, c['a'].name)
    c['inbound'](2, c['a'].code, source=None)
    c['inbound'](3, c['b'].name, source=None)
    c['inbound'](100, c['a'].name, 'pending', source=None)
    db.session.commit()
    global_rows = m.build_purchase_order_execution(c['order'])
    assert global_rows[c['item'].id]['completed_quantity'] == 3
    assert global_rows[second.id]['completed_quantity'] == 3
    assert sum(r['received_quantity'] for r in rows('purchase_order_execution', c['a'])) == 3
    assert sum(r['received_quantity'] for r in rows('purchase_order_execution', c['b'])) == 3
    for kind in REPORTS[1:]:
        assert rows(kind, c['a'])[0]['received_quantity'] == 3
        assert rows(kind, c['b'])[0]['received_quantity'] == 3


def test_legacy_over_receipt_is_visible_instead_of_truncated(receipt_case):
    c = receipt_case
    c['inbound'](15, c['a'].name, source=None); db.session.commit()
    for kind in REPORTS:
        row = rows(kind, c['a'])[0]
        assert row['received_quantity'] == 15
        assert row['remaining_quantity'] == 0


def test_unresolved_historical_warehouse_is_preserved_without_assigning_default(receipt_case):
    c = receipt_case
    receipt = c['inbound'](2, '历史未知仓库', source=None); db.session.commit()
    assert m.build_purchase_order_execution(c['order'])[c['item'].id]['completed_quantity'] == 2
    assert rows('purchase_order_execution', c['a'])[0]['received_quantity'] == 0
    assert receipt.warehouse == '历史未知仓库'
    assert c['item'].received_quantity == 8


def test_received_sort_uses_facts_before_sql_pagination(receipt_case):
    c = receipt_case
    other = PurchaseOrder(order_no='PO2', date=date.today(), supplier_id=c['supplier'].id, status='partial')
    db.session.add(other); db.session.flush()
    item = PurchaseOrderItem(purchase_order_id=other.id, material_id=c['material'].id,
                             quantity=10, received_quantity=1, price=2, amount=20)
    db.session.add(item); db.session.flush()
    c['inbound'](4, c['a'].name, source=item, order_id=other.id); db.session.commit()
    columns, page, summary, total = m._sql_paged_purchase_execution_report(
        filters(c['a'], sort_field='received_quantity', sort_order='desc', page_size=1))
    assert page[0]['order_no'] == 'PO2'
    assert page[0]['received_quantity'] == 4
    assert total == 2 and summary['quantity'] == 20


@pytest.mark.parametrize('kind', REPORTS)
def test_sql_and_memory_receipt_paths_agree_without_n_plus_one(receipt_case, kind):
    from sqlalchemy import event
    c = receipt_case
    c['inbound'](2, c['a'].name); db.session.commit()
    query_filters = filters(c['a'])
    statements = []
    def record(conn, cursor, statement, parameters, context, many):
        statements.append(statement)
    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        sql_rows = m.SQL_PAGED_REPORT_BUILDERS[kind](query_filters)[1]
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)
    small_query_count = len(statements)
    memory_rows = m.REPORT_BUILDERS[kind](filters(c['a']))[1]
    assert [r['received_quantity'] for r in sql_rows] == [2]
    assert [r['received_quantity'] for r in memory_rows] == [2]
    # Compare sizes instead of assuming every existing report has the same fixed
    # number of aggregate/latest-supplier queries. No query may be added per row.
    document = InOrder(order_no='BULK', date=date.today(), warehouse=c['a'].name,
                       status='completed', business_type='采购入库', source_purchase_order_id=c['order'].id)
    db.session.add(document); db.session.flush()
    for index in range(10):
        material = Material(code='EXTRA'+str(index), name='其他物料'+str(index), stock=0)
        db.session.add(material); db.session.flush()
        item = PurchaseOrderItem(purchase_order_id=c['order'].id, material_id=material.id,
                                 quantity=10, received_quantity=9, price=2, amount=20)
        db.session.add(item); db.session.flush()
        db.session.add(InOrderItem(in_order_id=document.id, material_id=material.id,
                                   source_purchase_order_item_id=item.id, quantity=1, price=2, amount=2))
    db.session.commit(); statements.clear()
    event.listen(db.engine, 'before_cursor_execute', record)
    try:
        large_rows = m.SQL_PAGED_REPORT_BUILDERS[kind](query_filters)[1]
    finally:
        event.remove(db.engine, 'before_cursor_execute', record)
    assert len(statements) == small_query_count, 'query count must stay constant as receipt lines grow'
    assert sum(row['received_quantity'] for row in large_rows) == 12
