"""Current WMS models in fresh LPAC memory DB; selection is not reservation."""
from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import mysql, postgresql

from tests.test_money_route_synthetic_20261109 import money_case, unchanged_inventory

FAMILIES = [
    ('IN','InOrder','order_no'), ('PI','InOrder','order_no'), ('OI','InOrder','order_no'),
    ('OU','OutOrder','order_no'), ('SO','OutOrder','order_no'), ('OO','OutOrder','order_no'),
    ('CK','InventoryCheck','check_no'), ('CS','InventoryCheckScan','check_no'),
    ('SC','SubcontractOrder','order_no'), ('SUB','SubcontractOrder','order_no'),
    ('WW','SubcontractOrder','order_no'),
    ('SF','SubcontractIssue','issue_no'), ('SR','SubcontractReceive','receive_no'),
    ('PR','PurchaseRequest','request_no'), ('PO','PurchaseOrder','order_no'),
    ('ASO','AfterSaleOutOrder','order_no'), ('BOM','BOM','bom_no'),
    ('REQ','ProductionRequisition','req_no'), ('TF','TransferOrder','transfer_no'),
    ('ADJ','AdjustmentOrder','adjustment_no'), ('QS','OpeningStockDoc','doc_no'),
]


def add(case, model_name, field, number):
    extra = {}
    if model_name == 'BOM':
        extra.update(product_code='N-P', product_name='合成编号产品')
    elif model_name == 'TransferOrder':
        extra.update(from_location=case.warehouse, to_location='合成金额乙仓')
    elif model_name == 'AdjustmentOrder':
        extra['adjustment_type'] = 'increase'
    elif model_name == 'SalesOrder':
        extra['customer_id'] = case.customer
    row = getattr(case.w, model_name)(**{field:number}, **extra)
    case.w.db.session.add(row)
    case.w.db.session.commit()
    return row.id


@pytest.mark.parametrize('prefix,model_name,field', FAMILIES)
def test_all_current_model_families_use_full_maximum_without_writing(money_case, prefix, model_name, field):
    c = money_case;w = c.w;base = prefix + datetime.now().strftime('%y%m')
    add(c, model_name, field, base + '0077')
    add(c, model_name, field, base + '0004')
    model = getattr(w, model_name);column = getattr(model, field)
    before = model.query.order_by(model.id).with_entities(model.id, column).all()
    assert w.generate_order_no(prefix) == base + '0078'
    assert model.query.order_by(model.id).with_entities(model.id, column).all() == before
    unchanged_inventory(c)


def test_out_alias_preserves_the_existing_ou_format(money_case):
    c = money_case;base = 'OU' + datetime.now().strftime('%y%m')
    add(c, 'OutOrder', 'order_no', base + '0007')
    assert c.w.generate_order_no('OUT') == base + '0008'
    unchanged_inventory(c)


@pytest.mark.parametrize('entry', ['general', 'sales'])
@pytest.mark.parametrize('high_model', ['OutOrder', 'SalesOrder'])
def test_shared_so_prefix_sees_both_actual_tables(money_case, entry, high_model):
    c = money_case;base = 'SO' + datetime.now().strftime('%y%m')
    add(c, 'OutOrder', 'order_no', base + ('10000' if high_model == 'OutOrder' else '09999'))
    add(c, 'SalesOrder', 'order_no', base + ('10000' if high_model == 'SalesOrder' else '09999'))
    generate = c.w.generate_sales_order_no if entry == 'sales' else lambda: c.w.generate_order_no('SO')
    assert generate() == base + '10001'
    unchanged_inventory(c)


def test_sequence_lock_targets_one_counter_without_locking_historical_documents(money_case):
    c = money_case;w = c.w;base = 'OU' + datetime.now().strftime('%y%m')
    add(c, 'OutOrder', 'order_no', base + '0077')
    add(c, 'OutOrder', 'order_no', base + '0004')
    captured = []
    def record(conn, clause, multiparams, params, options):
        if getattr(clause, 'is_select', False) or getattr(clause, 'is_update', False):
            captured.append(clause)
    engine = w.db.engine
    event.listen(engine, 'before_execute', record)
    try:
        assert w.generate_order_no('OU') == base + '0078'
    finally:
        event.remove(engine, 'before_execute', record)
    assert not [statement for statement in captured if getattr(statement, '_for_update_arg', None) is not None]
    locks = [statement for statement in captured if getattr(statement, 'is_update', False)
             and statement.table.name == 'system_setting']
    assert len(locks) == 2  # Acquire one counter row, then advance it in this transaction.
    for dialect in (mysql.dialect(), postgresql.dialect()):
        compiled = str(locks[0].compile(dialect=dialect, compile_kwargs={'literal_binds':True}))
        assert 'UPDATE system_setting SET' in compiled and ' WHERE ' in compiled and ' LIKE ' not in compiled
        assert 'document_sequence:' + base in compiled
        assert base + '0077' not in compiled and base + '0004' not in compiled
    unchanged_inventory(c)
