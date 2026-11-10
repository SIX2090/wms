"""Formal numbers belong to the successful save transaction, not a preview."""
from datetime import datetime

import pytest

import app as w


@pytest.fixture
def sequence_case():
    with w.app.app_context():
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        w.db.session.remove()
        w.db.drop_all()
        w.db.create_all()
        yield
        w.db.session.remove()


def test_reserve_document_number(sequence_case):
    first = w.generate_order_no('IN')
    second = w.generate_order_no('IN')
    assert first != second
    assert int(second[6:]) == int(first[6:]) + 1


def test_reserve_document_number_retains_deleted_number(sequence_case):
    number = w.generate_order_no('IN')
    order = w.InOrder(order_no=number)
    w.db.session.add(order)
    w.db.session.commit()
    w.db.session.delete(order)
    w.db.session.commit()
    assert w.generate_order_no('IN') != number


def test_reserve_document_number_rollback_does_not_consume_number(sequence_case):
    number = w.generate_order_no('IN')
    w.db.session.rollback()
    assert w.generate_order_no('IN') == number


@pytest.mark.parametrize('prefix', ['IN', 'PI', 'OI', 'OUT', 'SO', 'OO', 'CK', 'CS',
                                   'SC', 'SUB', 'SF', 'SR', 'PR', 'PO', 'ASO',
                                   'BOM', 'REQ', 'TF', 'ADJ', 'QS', 'WW'])
def test_reserve_document_number_covers_every_current_family(sequence_case, prefix):
    first = w.generate_order_no(prefix)
    w.db.session.commit()
    second = w.generate_order_no(prefix)
    assert first != second
    assert first.startswith(('OU' if prefix == 'OUT' else prefix) + datetime.now().strftime('%y%m'))


def test_existing_maximum(sequence_case):
    base = 'SO' + datetime.now().strftime('%y%m')
    w.db.session.add_all([w.OutOrder(order_no=base+'10000'),
                         w.OutOrder(order_no=base+'9999')])
    w.db.session.commit()
    assert w.generate_sales_order_no() == base+'10001'


def test_retain_document_sequences(sequence_case):
    base = 'SR' + datetime.now().strftime('%y%m')
    order = w.InOrder(order_no=base+'12345', business_type='销售退货入库')
    w.db.session.add(order)
    w.db.session.commit()
    w.db.session.delete(order)
    w.db.session.commit()
    assert w.generate_order_no('SR') == base+'12346'


def test_preview_document_number(sequence_case):
    with w.app.test_request_context('/in_order/add', method='GET'):
        first = w.generate_order_no('IN')
        w.db.session.commit()
        assert w.generate_order_no('IN') == first
        assert w.SystemSetting.query.filter(w.SystemSetting.key.like('document_sequence:%')).count() == 0


def test_locked_sequence_refuses_corrupt_sequence(sequence_case):
    base = 'IN' + datetime.now().strftime('%y%m')
    w.db.session.add(w.SystemSetting(key='document_sequence:'+base, value='broken'))
    w.db.session.commit()
    with pytest.raises(ValueError, match='编号记录异常'):
        w.generate_order_no('IN')


def test_preview_document_number_reads_retained_sequence(sequence_case):
    base = 'IN' + datetime.now().strftime('%y%m')
    w.db.session.add(w.SystemSetting(key='document_sequence:'+base, value='10000'))
    w.db.session.commit()
    with w.app.test_request_context('/in_order/add', method='GET'):
        assert w.generate_order_no('IN') == base+'10001'


def test_reserve_document_number_accounts_for_unflushed_import(sequence_case):
    base = 'IN' + datetime.now().strftime('%y%m')
    w.db.session.add(w.InOrder(order_no=base+'10000'))
    assert w.generate_order_no('IN') == base+'10001'
    w.db.session.rollback()
    assert w.InOrder.query.count() == 0
    assert w.SystemSetting.query.count() == 0


def test_reserve_document_number_keeps_each_month_sequence(sequence_case, monkeypatch):
    class Clock(datetime):
        month = 11

        @classmethod
        def now(cls, tz=None):
            return datetime(2026, cls.month, 10, tzinfo=tz)

    monkeypatch.setattr(w, 'datetime', Clock)
    assert w.generate_order_no('IN') == 'IN26110001'
    w.db.session.commit()
    Clock.month = 12
    assert w.generate_order_no('IN') == 'IN26120001'
    w.db.session.commit()
    Clock.month = 11
    assert w.generate_order_no('IN') == 'IN26110002'


def test_retain_document_number(sequence_case):
    from services.document_numbering import retain_document_number
    connection = w.db.session.connection()
    retain_document_number(connection, 'HISTORICAL-CUSTOM', ('IN',))
    assert w.SystemSetting.query.count() == 0
    base = 'IN' + datetime.now().strftime('%y%m')
    retain_document_number(connection, base+'12345', ('IN',))
    w.db.session.commit()
    assert w.generate_order_no('IN') == base+'12346'


def test_reserve_document_number_respects_caller_no_autoflush(sequence_case):
    pending = w.InOrder()
    w.db.session.add(pending)
    with w.db.session.no_autoflush:
        number = w.generate_order_no('IN')
        assert pending.id is None
        pending.order_no = number
    w.db.session.commit()
    assert w.InOrder.query.one().order_no == number
