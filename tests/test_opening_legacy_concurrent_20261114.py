"""Real independent connections, owned fresh synthetic file only."""
from datetime import date
import threading

from scripts.verify_db_guard import require_isolated_test_runtime
require_isolated_test_runtime()

import pytest
import app as w
from tests.test_native_request_concurrent import file_case


@pytest.mark.parametrize('with_keys', [False, True])
@pytest.mark.parametrize('ambiguous', [False, True])
def test_legacy_native_writers_resolve_ownership_under_sqlite_fence(file_case, with_keys, ambiguous):
    engine, _, uid, mid, warehouse, code = file_case
    with w.app.app_context():
        wh = w.Warehouse.query.filter_by(code=warehouse).one()
        if ambiguous:
            for index in range(2):
                doc = w.OpeningStockDoc(doc_no='SYN-OWNER-' + str(index), date=date(2020, 1, 1),
                                       status='active', warehouse_id=wh.id, operator_id=uid)
                w.db.session.add(doc)
                w.db.session.flush()
                w.db.session.add(w.OpeningStock(doc_id=doc.id, material_id=mid,
                    warehouse_id=wh.id, date=doc.date, quantity=0, price=0, amount=0, operator_id=uid))
            w.db.session.commit()
        w.db.session.remove()
    barrier = threading.Barrier(2)
    results, errors, connections = [], [], set()
    lock = threading.Lock()
    def submit(index):
        try:
            with w.app.app_context():
                connection = w.db.session.connection()
                with lock:
                    connections.add(id(connection.connection.driver_connection))
                barrier.wait(timeout=10)
                body = {'date': '2026-11-14', 'warehouse_code': warehouse,
                        'lines': [{'material_code': code, 'quantity': index + 3, 'price': 2}]}
                if with_keys:
                    body['request_id'] = 'synthetic-competing-' + str(index)
                response = w.app.test_client().post('/api/opening_stock', json=body)
                with lock:
                    results.append((response.status_code, response.get_json()))
                w.db.session.remove()
        except Exception as exc:
            errors.append(repr(exc))
    threads = [threading.Thread(target=submit, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not errors and all(not thread.is_alive() for thread in threads), errors
    assert len(connections) == 2
    assert [status for status, _ in results] == ([400, 400] if ambiguous else [200, 200]), results
    with w.app.app_context():
        if ambiguous:
            assert w.OpeningStock.query.count() == 2
            assert w.OpeningStockDoc.query.count() == 2
            assert all(row.quantity == 0 for row in w.OpeningStock.query)
            assert w.StockTransaction.query.count() == 0
            assert w.MobileApiRequest.query.count() == 0
        else:
            row = w.OpeningStock.query.one()
            assert row.quantity in (3, 4) and row.amount == row.quantity * 2
            assert w.db.session.get(w.Material, mid).stock == row.quantity
            assert w.OpeningStockDoc.query.one().id == row.doc_id
            assert sum(t.quantity for t in w.StockTransaction.query) == row.quantity
            assert w.MobileApiRequest.query.count() == (2 if with_keys else 0)
        w.db.session.remove()
