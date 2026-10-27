"""Regression locks for the confirmed browser audit (isolated database only)."""
from pathlib import Path
import re

import pytest
from flask import template_rendered

ROOT = Path(__file__).resolve().parents[1]


def _context(client, url):
    from app import app
    contexts = []
    def capture(sender, template, context, **extra):
        contexts.append(context)
    template_rendered.connect(capture, app)
    try:
        response = client.get(url)
        assert response.status_code == 200
        return response.get_data(as_text=True), contexts[-1]
    finally:
        template_rendered.disconnect(capture, app)


def test_filtered_category_keeps_full_tree_depth(bom_case):
    from app import db, MaterialCategory
    client, _ = bom_case
    root = MaterialCategory(code='PARENT', name='上级分类')
    db.session.add(root)
    db.session.flush()
    child = MaterialCategory(code='CHILD', name='子级分类', parent_id=root.id)
    db.session.add(child)
    db.session.commit()
    _, context = _context(client, '/category?search=CHILD&embedded=1')
    assert len(context['category_rows']) == 1
    assert context['category_rows'][0]['level'] == 1


def test_employee_blank_code_is_assigned_and_unique(bom_case):
    from app import Employee
    client, _ = bom_case
    for name in ('自动编号甲', '自动编号乙'):
        assert client.post('/employee/add', data={'name':name}).status_code == 200
    employees = Employee.query.order_by(Employee.id).all()
    assert len(employees) == 2
    assert all(e.code for e in employees)
    assert employees[0].code != employees[1].code


def test_manual_check_records_counting_without_changing_stock(bom_case):
    from app import db, Warehouse, Material, InventoryCheckItem, StockTransaction
    client, ids = bom_case
    wh = Warehouse(code='COUNT', name='盘点仓', status='active')
    db.session.add(wh)
    db.session.commit()
    r = client.post('/check/save_table', json={'header':{'warehouse':wh.name},
        'items':[{'material_id':ids['material'], 'actual_stock':0}]})
    assert r.status_code == 200, r.get_json()
    item = InventoryCheckItem.query.one()
    assert item.counted_by == ids['user']
    assert item.counted_at is not None
    assert item.actual_stock == 0
    assert db.session.get(Material, ids['material']).stock == 10
    assert StockTransaction.query.count() == 0


@pytest.mark.parametrize('url', ['/approval?embedded=1', '/sales/execution_report?embedded=1'])
def test_get_query_forms_do_not_submit_csrf(bom_case, url):
    client, _ = bom_case
    html, _ = _context(client, url)
    for method, body in re.findall(r'<form\b[^>]*method=["\'](get)["\'][^>]*>(.*?)</form>', html, re.I|re.S):
        assert 'name="csrf_token"' not in body


def test_user_create_and_edit_offer_same_roles(bom_case):
    client, _ = bom_case
    html, _ = _context(client, '/user?embedded=1')
    add = re.search(r'id="addForm"(.*?)</form>', html, re.S).group(1)
    edit = re.search(r'id="editForm"(.*?)</form>', html, re.S).group(1)
    assert 'value="sales"' in add and 'value="sales"' in edit


def test_contract_batch_import_uses_working_import_dialog(bom_case):
    client, _ = bom_case
    html, _ = _context(client, '/contract?embedded=1')
    assert '/batch_import?type=contract' not in html
    assert 'showImportModal()' in html


def test_check_report_names_absolute_difference(bom_case):
    client, _ = bom_case
    _, context = _context(client, '/report/view/check?embedded=1')
    assert context['summary_labels']['amount'] == '绝对差异合计'


def test_material_selection_header_has_readable_label(bom_case):
    client, _ = bom_case
    html, _ = _context(client, '/material?embedded=1')
    header = re.search(r'<th[^>]*data-column-key="select"[^>]*>(.*?)</th>', html, re.S).group(1)
    assert '选择' in header


def test_opening_gap_filter_runs_before_pagination(bom_case):
    from app import db, Warehouse
    client, ids = bom_case
    wh = Warehouse(code='PROGRESS', name='建账仓', status='active')
    db.session.add(wh)
    db.session.commit()
    r = client.post('/opening_stock/save', json={'warehouse_id':wh.id,
        'date':'2026-10-27', 'items':[{'material_id':ids['material'],
        'warehouse_id':wh.id, 'quantity':3, 'price':1}]})
    assert r.status_code == 200, r.get_json()
    _, context = _context(client, '/opening_stock/progress?search=B-M&only_gap=1')
    assert context['pagination'].total == 0
    assert not context['rows']
    html, context = _context(client, '/opening_stock/progress?search=B-M&only_gap=0')
    assert context['pagination'].total == 1
    assert '导出建账清单' in html


def test_purchase_summary_counts_pushed_but_not_received(bom_case):
    from app import db, Supplier, PurchaseOrder, PurchaseOrderItem
    client, ids = bom_case
    supplier = Supplier(code='PO-S', name='汇总供应商')
    db.session.add(supplier)
    db.session.flush()
    order = PurchaseOrder(order_no='PO-AUDIT', supplier_id=supplier.id, status='pending')
    db.session.add(order)
    db.session.flush()
    db.session.add(PurchaseOrderItem(purchase_order_id=order.id,
        material_id=ids['material'], quantity=2, received_quantity=2, price=1))
    db.session.commit()
    _, context = _context(client, '/purchase_order?embedded=1')
    assert context['summary']['pending_receive_qty'] == 2
    assert context['qty_stats'][order.id]['pending_receive_qty'] == 2
    from app import InOrder
    order.status = 'partial'
    inbound = InOrder(order_no='IN-SOURCE-AUDIT', source_purchase_order_id=order.id,
                      supplier_id=supplier.id, status='pending')
    db.session.add(inbound)
    db.session.commit()
    html, _ = _context(client, f'/in_order/{inbound.id}?embedded=1')
    assert '<td>部分入库</td>' in html
    assert '<td>partial</td>' not in html


def test_saving_untouched_check_does_not_count_default_quantity(bom_case):
    from app import db, Warehouse, InventoryCheckItem
    client, ids = bom_case
    wh = Warehouse(code='UNTOUCHED', name='未盘仓', status='active')
    db.session.add(wh)
    db.session.commit()
    r = client.post('/check/save_table', json={'header':{'warehouse':wh.name},
        'items':[{'material_id':ids['material'], 'actual_stock':None}]})
    assert r.status_code == 200
    item = InventoryCheckItem.query.one()
    assert item.counted_at is None and item.counted_by is None


def test_report_unit_totals_remain_readable_without_unbounded_cards():
    css = (ROOT / 'app/templates/report_view.html').read_text(encoding='utf-8')
    rule = re.search(r'\.summary-value\s*\{([^}]+)', css).group(1)
    assert 'overflow-y: auto' in rule
    assert 'max-height:' in rule


def test_sales_outbound_detail_does_not_claim_requisition(bom_case):
    from app import db, OutOrder
    client, _ = bom_case
    order = OutOrder(order_no='SO-OUT-AUDIT', business_type='销售出库', status='pending')
    db.session.add(order)
    db.session.commit()
    html, _ = _context(client, f'/out_order/{order.id}?embedded=1')
    assert '出库日期' in html and '出库明细' in html
    assert '领料日期' not in html and '完成领料' not in html

