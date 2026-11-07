"""Two real SQLite connections and two management requests share one alias namespace."""
from pathlib import Path
import threading

import pytest
from flask import request
from flask_login import current_user
from sqlalchemy import event
from werkzeug.security import generate_password_hash

import app as w


@pytest.mark.parametrize('mode', ['add_add', 'add_edit', 'edit_edit'])
def test_lock_warehouse_namespace(monkeypatch, mode):
    monkeypatch.setitem(w.app.config, 'TESTING', True)
    monkeypatch.setitem(w.app.config, 'WTF_CSRF_ENABLED', False)
    with w.app.app_context():
        database = w.db.engine.url.database
        if database == ':memory:':
            pytest.skip('Dedicated two-connection run requires its explicitly allowlisted synthetic SQLite file')
        lab = Path(r'C:\Users\Administrator\Documents\Codex\2026-11-07\wms-improvement-90\lab')
        assert Path(database).resolve().is_relative_to(lab.resolve())
        assert Path(database).name == 'synthetic.sqlite'
        w.db.create_all()
        user = w.User(username='namespace-' + mode, role='admin', must_change_password=False,
                      password_hash=generate_password_hash('synthetic-only'))
        w.db.session.add(user)
        originals = []
        for index in range(mode.count('edit')):
            warehouse = w.Warehouse(code=f'OLD-{mode}-{index}', name=f'旧仓-{mode}-{index}', status='active')
            w.db.session.add(warehouse)
            originals.append(warehouse)
        w.db.session.commit()
        user_id = user.id
        ids = [warehouse.id for warehouse in originals]
        engine = w.db.engine
        before_count = w.Warehouse.query.count()
        w.db.session.remove()
    clients = [w.app.test_client(), w.app.test_client()]
    for client in clients:
        client.environ_base['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        with client.session_transaction() as session:
            session['_user_id'] = str(user_id)
            session['_fresh'] = True
    barrier = threading.Barrier(2)
    connections, errors, responses = set(), [], []
    mutex = threading.Lock()

    def capture(connection, cursor, statement, parameters, context, executemany):
        if threading.current_thread().name.startswith('namespace-request-'):
            with mutex:
                connections.add(id(connection.connection.driver_connection))

    def align_requests():
        if request.method == 'POST' and request.path.startswith('/warehouse/'):
            assert current_user.is_authenticated
            barrier.wait(timeout=10)

    hooks = dict(w.app.before_request_funcs)
    hooks[None] = [*hooks.get(None, []), align_requests]
    monkeypatch.setattr(w.app, 'before_request_funcs', hooks)
    event.listen(engine, 'before_cursor_execute', capture)
    first_path = '/warehouse/add' if mode != 'edit_edit' else f'/warehouse/{ids[0]}/edit'
    second_path = '/warehouse/add' if mode == 'add_add' else f'/warehouse/{ids[-1]}/edit'
    alias = 'RACE-' + mode
    requests = [(first_path, {'code': alias, 'name': '新甲仓-' + mode}),
                (second_path, {'code': 'SECOND-' + mode, 'name': alias})]

    def submit(index):
        try:
            path, payload = requests[index]
            response = clients[index].post(path, data=payload)
            with mutex:
                responses.append((index, response.status_code, response.get_json()))
        except Exception as exc:
            with mutex:
                errors.append(repr(exc))

    threads = [threading.Thread(target=submit, args=(index,), name=f'namespace-request-{index}')
               for index in range(2)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=40)
        assert not any(thread.is_alive() for thread in threads)
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert not errors, errors
    assert len(connections) >= 2, 'The requests must actually use separate SQLite connections'
    assert sorted(code for _, code, _ in responses) == [200, 400], responses
    assert sorted(body['status'] for _, _, body in responses) == ['error', 'success']
    with w.app.app_context():
        warehouses = w.Warehouse.query.all()
        for left in warehouses:
            for right in warehouses:
                if left.id != right.id:
                    assert not {left.code, left.name}.intersection((right.code, right.name))
        added = sum(requests[index][0] == '/warehouse/add' and body['status'] == 'success'
                    for index, _, body in responses)
        assert len(warehouses) == before_count + added
        assert w.StockTransaction.query.count() == 0
        w.db.session.remove()
