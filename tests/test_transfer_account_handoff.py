"""Two real database connections share one draft and reconcile both warehouses."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine

import app as w
from tests.test_document_create_number_conflicts import case, payload
from tests.test_document_edit_conflicts import revision
from tests.test_web_stock_posting_audit import posting_actors


@pytest.fixture
def file_accounts(posting_actors, tmp_path, monkeypatch):
    engine = create_engine('sqlite:///' + str(tmp_path / 'transfer.db'), connect_args={'timeout': 15})
    with w.app.app_context():
        w.db.session.remove()
        assert str(w.db.engine.url) == 'sqlite:///:memory:'
        with w.db.engine.connect() as source, engine.connect() as target:
            source.connection.driver_connection.backup(target.connection.driver_connection)
        monkeypatch.setitem(w.db.engines, None, engine)
    try:
        yield posting_actors
    finally:
        with w.app.app_context():
            w.db.session.remove()
        engine.dispose()


def new_transfer(client, ids):
    data = payload('transfer', ids, '')
    data['items'][0]['quantity'] = 10
    response = client.post('/transfer/save_table', json=data)
    assert response.json['status'] == 'success', response.json
    return response.json['id'], response.json['order_no'], data


def test_two_operators_edit_complete_and_revert_transfer(file_accounts):
    first, second, ids = file_accounts
    oid, number, data = new_transfer(first, ids)
    base = f'/transfer/{oid}'
    header = 'X-WMS-Document-Revision'
    current, stale = [revision(client, base) for client in (first, second)]
    assert current and stale
    data['order_id'] = oid
    data['items'][0]['quantity'] = 8
    edited = first.post('/transfer/save_table', json=data, headers={header: current})
    assert edited.json['status'] == 'success', edited.json
    data['items'][0]['quantity'] = 10
    rejected = second.post('/transfer/save_table', json=data, headers={header: stale})
    assert (rejected.status_code, rejected.json['code']) == (409, 'DOCUMENT_EDIT_CONFLICT')
    rejected = second.post(base + '/complete', headers={header: stale})
    assert (rejected.status_code, rejected.json['code']) == (409, 'DOCUMENT_EDIT_CONFLICT')

    mid = ids['mats'][0]
    for action, status, balances in [('complete', 'completed', (12, 18)), ('revert', 'pending', (20, 10))]:
        gate = Barrier(2)

        def submit(client):
            gate.wait(timeout=10)
            return client.post(f'{base}/{action}').json

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(submit, [first, second]))
        assert sorted(reply['status'] for reply in responses) == ['error', 'success'], responses
        actor = [ids['user'], ids['poster']][next(i for i, r in enumerate(responses) if r['status'] == 'success')]
        replay = second.post(f'{base}/{action}')
        assert replay.json['status'] == 'error'
        with w.app.app_context():
            doc = w.db.session.get(w.TransferOrder, oid)
            assert (doc.status, doc.operator_id, doc.items[0].quantity) == (status, ids['user'], 8)
            assert w.db.session.get(w.Material, mid).stock == 30
            audit = w.OperationAudit.query.filter_by(operation=f'{action}_transfer', target_id=oid).one()
            assert audit.user_id == actor
            txns = w.StockTransaction.query.filter_by(reference_type='transfer', reference_id=oid).order_by(w.StockTransaction.id).all()
            assert len(txns) == (2 if action == 'complete' else 4)
            assert [row.operator_id for row in txns[-2:]] == [actor, actor]
            for idx, wid in enumerate([ids['a'], ids['b']]):
                wh = w.db.session.get(w.Warehouse, wid)
                assert w.get_warehouse_stock_quantities(wh)[mid] == balances[idx]
                filters = {'warehouse_id': wid, 'warehouse': wh.name, 'material_id': mid,
                           'material_code': w.db.session.get(w.Material, mid).code}
                ledger = [r for r in w._collect_ledger_rows(filters) if r['reference_no'] == number]
                expected = [-8, 8] if idx == 0 else [8, -8]
                assert [r['quantity'] for r in ledger] == expected[:len(txns) // 2]
                assert ledger[-1]['balance_quantity'] == balances[idx]
                _, monthly, _ = w._build_warehouse_monthly_report(filters)
                assert len(monthly) == 1 and monthly[0]['ending_quantity'] == balances[idx]


@pytest.mark.parametrize('kind,side', [
    ('transfer', 'a'), ('transfer', 'b'), ('after_sale_out', 'a'),
    ('subcontract_receive', 'a'), ('subcontract_issue', 'a'),
])
def test_warehouse_disabled_before_posting_lock(file_accounts, monkeypatch, kind, side):
    creator, _, ids = file_accounts
    mid = ids['mats'][0]
    if kind == 'transfer':
        oid, _, _ = new_transfer(creator, ids)
        model = w.TransferOrder
    else:
        with w.app.app_context():
            header = dict(warehouse=ids['names'][0], operator_id=ids['user'], status='pending')
            if kind == 'after_sale_out':
                model = w.AfterSaleOutOrder
                order = model(order_no='HANDOFF-AFTER', **header)
                line = w.AfterSaleOutOrderItem(material_id=mid, quantity=1, price=1, amount=1)
            else:
                parent = w.SubcontractOrder(order_no='HANDOFF-SUB', **header)
                w.db.session.add(parent)
                w.db.session.flush()
                w.db.session.add(w.SubcontractItem(subcontract_order_id=parent.id, material_id=mid, quantity=1))
                if kind == 'subcontract_receive':
                    model = w.SubcontractReceive
                    order = model(receive_no='HANDOFF-R', subcontract_order_id=parent.id, **header)
                    line = w.SubcontractReceiveItem(material_id=mid, quantity=1)
                else:
                    model = w.SubcontractIssue
                    order = model(issue_no='HANDOFF-I', subcontract_order_id=parent.id, **header)
                    line = w.SubcontractIssueItem(material_id=mid, quantity=1)
            order.items.append(line)
            w.db.session.add(order)
            w.db.session.commit()
            oid = order.id

    lock = w._acquire_order_write_lock
    changed = []
    def disable_then_lock(*args, **kwargs):
        with w.db.engine.begin() as other:
            result = other.execute(w.Warehouse.__table__.update().where(
                w.Warehouse.id == ids[side]).values(status='inactive'))
            changed.append(result.rowcount)
        return lock(*args, **kwargs)

    monkeypatch.setattr(w, '_acquire_order_write_lock', disable_then_lock)
    with w.app.app_context():
        before = w.StockTransaction.query.count(), w.OperationAudit.query.count()
    response = creator.post(f'/{kind}/{oid}/complete')
    assert changed == [1]
    assert response.json['status'] == 'error' and '停用' in response.json['msg'], response.json
    with w.app.app_context():
        assert w.db.session.get(model, oid).status == 'pending'
        assert (w.StockTransaction.query.count(), w.OperationAudit.query.count()) == before
        assert w.db.session.get(w.Material, mid).stock == 30
