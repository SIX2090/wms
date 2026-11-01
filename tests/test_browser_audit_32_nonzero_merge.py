from tests.audit_regressions.conftest import audit_boundaries
from tests.audit_regressions.support import evidence_dir
"""Fresh synthetic file SQLite only. Every DELETE is rejected before execution.

HTTP tests use Flask dispatch, synthetic sessions and real CSRF, not a browser.
The inflight duplicate uses a nonmutating domain sentinel; rollback uses real
domain updates and stops before the first DELETE. Neither proves full merging.
"""
import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

import pytest
from flask import has_request_context, request
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

import app as m
from tests.audit_regressions.http_fixture import http_case

ROOT = Path(__file__).resolve().parents[1]


def evidence(name, value):
    (evidence_dir() / (os.environ.get('QA32_EVIDENCE_PREFIX', '') + name + '.json')).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')


@pytest.fixture
def lab(http_case, tmp_path):
    clients, ids, _ = http_case
    dbpath = tmp_path / 'case.sqlite'
    with m.app.app_context():
        memory = m.db.engines[None]
        m.db.session.remove()
        with memory.connect() as connection, sqlite3.connect(dbpath) as dest:
            connection.connection.driver_connection.backup(dest)
        engine = create_engine('sqlite:///' + str(dbpath), poolclass=NullPool,
            connect_args={'check_same_thread': False, 'timeout': 0.25})
        m.db.engines[None] = engine
        for key in ('a', 'b'):
            wh = m.db.session.get(m.Warehouse, ids[key])
            wh.code = wh.name = 'QA32-' + key.upper()
        keep = m.db.session.get(m.Material, ids['material'])
        keep.code, keep.name, keep.spec, keep.brand, keep.stock = (
            'QA32-KEEP', 'QA32合并保留', 'QA32-SPEC', 'QA32-BRAND', 10)
        source = m.Material(code='QA32-SOURCE', name='QA32合并源',
            spec=keep.spec, brand=keep.brand, unit_id=keep.unit_id, stock=5)
        m.db.session.add(source)
        m.db.session.flush()
        ids['source'] = source.id
        flows = m.StockTransaction.query.order_by(m.StockTransaction.id).all()
        for row, qty in zip(flows, (4, 0, 6)):
            row.quantity = qty
            row.location = 'QA32-A' if row.warehouse_id == ids['a'] else 'QA32-B'
        for key, qty in (('a', 3), ('b', 2)):
            m.db.session.add(m.StockTransaction(material_id=source.id,
                warehouse_id=ids[key], location='QA32-' + key.upper(), quantity=qty,
                transaction_type='in'))
        for material, a, b in ((keep, 4, 6), (source, 3, 2)):
            for key, qty in (('a', a), ('b', b)):
                m.db.session.add(m.LocationInventory(material_id=material.id,
                    warehouse_id=ids[key], location='QA32-' + key.upper(), quantity=qty))
        m.db.session.add(m.SystemSetting(key='location_management_enabled', value='1'))
        check = m.db.session.get(m.InventoryCheck, ids['check'])
        check.check_no, check.warehouse = 'QA32-KEEP-CHECK', 'QA32-A'
        item = m.InventoryCheckItem.query.one()
        item.system_stock = item.actual_stock = 4
        inbound = m.InOrder(order_no='QA32-PI-REF', warehouse='QA32-A', location='QA32-A',
            business_type='产品入库', status='pending')
        outbound = m.OutOrder(order_no='QA32-OUT-REF', warehouse='QA32-A', location='QA32-A',
            business_type='其他出库', status='pending')
        m.db.session.add_all([inbound, outbound]); m.db.session.flush()
        ini = m.InOrderItem(in_order_id=inbound.id, material_id=source.id,
            quantity=2, price=0, amount=0)
        outi = m.OutOrderItem(out_order_id=outbound.id, material_id=source.id,
            quantity=1, price=0, amount=0)
        alias = m.AIMaterialAlias(alias='QA32-SOURCE-ALIAS', alias_key='qa32-source-alias',
            material_id=source.id, source='synthetic-round32')
        m.db.session.add_all([ini, outi, alias]); m.db.session.commit()
        ids.update(initem=ini.id, outitem=outi.id, alias=alias.id)
        m.db.session.remove()

    def deny_delete(conn, cursor, sql, parameters, context, many):
        if sql.lstrip().upper().startswith('DELETE'):
            raise ValueError('QA32_STOP_BEFORE_ANY_DELETE')
    event.listen(engine, 'before_cursor_execute', deny_delete)
    try:
        yield clients, ids, engine, dbpath
    finally:
        event.remove(engine, 'before_cursor_execute', deny_delete)
        with m.app.app_context():
            m.db.session.remove()
            m.db.engines[None] = memory
        engine.dispose()


def preview(c):
    r = c.post('/material/merge_preview', json={'source_code': 'QA32-SOURCE',
        'target_code': 'QA32-KEEP', 'manual_review': True, 'keep_alias': True})
    assert r.status_code == 200, r.json
    return r.json['data']


def execute(c, ids, token):
    return c.post(f"/material/{ids['source']}/merge", json={'target_code': 'QA32-KEEP',
        'identity_confirmed': True, 'confirm': True, 'keep_alias': True, 'preview_token': token})


def state(engine):
    # Complete business rows, including audit and settings; no assumed row counts.
    with engine.connect() as conn:
        return {t.name: [list(r) for r in conn.execute(select(t).order_by(*t.primary_key.columns))]
                for t in sorted(m.db.metadata.tables.values(), key=lambda t: t.name)}


def balances(ids):
    from services.warehouse_stock_service import verify_material_three_ledgers
    with m.app.app_context():
        result = {}
        for key in ('material', 'source'):
            result[key] = verify_material_three_ledgers(ids[key])
        return result


def test_readonly_nonzero_two_warehouse_preconditions(lab):
    clients, ids, engine, dbpath = lab
    before = state(engine)
    ledger = balances(ids)
    assert ledger['material'] == (True, {'one': 10.0, 'two': 10.0, 'three': 10.0, 'location_on': True})
    assert ledger['source'] == (True, {'one': 5.0, 'two': 5.0, 'three': 5.0, 'location_on': True})
    plan = preview(clients())
    assert plan['stock_after'] == 15
    assert plan['tables'] == {'stock_transaction': 2, 'in_order_item': 1,
        'out_order_item': 1, 'location_inventory': 2, 'ai_material_alias': 1}
    assert plan['total_rows'] == 7
    with engine.connect() as conn:
        quantities = {key: sum(conn.exec_driver_sql(
            'SELECT quantity FROM location_inventory WHERE warehouse_id=?', (ids[key],)).scalars())
            for key in ('a', 'b')}
    assert quantities == {'a': 7, 'b': 8}
    assert state(engine) == before
    evidence('readonly-preconditions', {'ledgers': ledger, 'preview': {k:v for k,v in plan.items()
        if k != 'preview_token'}, 'expected_projection_only': quantities,
        'unchanged': True, 'full_merge_executed': False})


@pytest.mark.parametrize('change', ['alias', 'target_alias', 'new_source_alias', 'new_target_alias'])
def test_real_overlapping_writer_invalidates_preview(lab, monkeypatch, change):
    clients, ids, engine, _ = lab
    c, writer = clients(), clients()
    if change == 'stock':
        with m.app.app_context():
            adj = m.AdjustmentOrder(adjustment_no='QA32-CONCURRENT-STOCK',
                warehouse='QA32-A', adjustment_type='surplus', source_type='manual', status='pending')
            m.db.session.add(adj); m.db.session.flush()
            m.db.session.add(m.AdjustmentOrderItem(adjustment_order_id=adj.id,
                material_id=ids['source'], location='QA32-A', quantity=1, unit_id=ids['unit']))
            m.db.session.commit()
            ids['adjustment'] = adj.id
        path = f"/adjustment/{ids['adjustment']}/complete"
    elif change == 'reference':
        path = '/in_order/item/update'
    else:
        path = None
    plan = preview(c)
    ready, attempting = threading.Event(), threading.Event()
    errors, results, calls = [], [], []
    guarded = [False]
    def before_commit(session):
        if has_request_context() and request.path == path and not guarded[0]:
            guarded[0] = True
            session.flush()  # A real uncommitted SQLite write holds the lock.
            ready.set()
            assert attempting.wait(5), 'merge never attempted BEGIN IMMEDIATE'
    def begin_attempt(conn, cursor, sql, params, context, many):
        if sql.strip().upper() == 'BEGIN IMMEDIATE':
            attempting.set()
    def no_merge(*a, **k):
        calls.append(True)
        raise ValueError('QA32_NO_DELETE_DOMAIN_SENTINEL')
    monkeypatch.setattr(m, 'merge_material_duplicates', no_merge)
    def write():
        try:
            if path is None:
                # A real second-connection write, not HTTP: no alias-edit endpoint assumed.
                with engine.begin() as conn:
                    if change == 'alias':
                        conn.exec_driver_sql('UPDATE ai_material_alias SET alias=? WHERE id=?',
                            ('QA32-ALIAS-CHANGED', ids['alias']))
                    elif change == 'target_alias':
                        conn.exec_driver_sql('UPDATE ai_material_alias SET material_id=? WHERE id=?',
                            (ids['material'], ids['alias']))
                    else:
                        conn.exec_driver_sql('INSERT INTO ai_material_alias '
                            '(alias,alias_key,material_id,disabled) VALUES (?,?,?,?)',
                            ('QA32-NEW-ALIAS', 'qa32-new-alias',
                             ids['source'] if change == 'new_source_alias' else ids['material'], False))
                    ready.set()
                    assert attempting.wait(5)
                results.append(200)
            else:
                r = writer.post(path, json={} if change == 'stock' else None,
                    data={'id': ids['initem'], 'quantity': 3, 'price': 0} if change == 'reference' else None)
                results.append(r.status_code)
                if r.status_code != 200:
                    errors.append(r.get_data(as_text=True))
        except BaseException as exc:
            errors.append(repr(exc)); ready.set()
    event.listen(Session, 'before_commit', before_commit)
    event.listen(engine, 'before_cursor_execute', begin_attempt)
    thread = threading.Thread(target=write)
    try:
        thread.start()
        assert ready.wait(5), 'writer did not hold a transaction'
        response = execute(c, ids, plan['preview_token'])
    finally:
        attempting.set()
        thread.join(10)
        event.remove(Session, 'before_commit', before_commit)
        event.remove(engine, 'before_cursor_execute', begin_attempt)
    assert not thread.is_alive() and errors == [], errors
    assert results == [200]
    evidence('concurrent-' + change, {'writer_status': results, 'merge_status': response.status_code,
        'merge_body': response.json, 'domain_calls': len(calls), 'real_independent_sqlite_connections': True,
        'writer_transport': 'SQL' if path is None else 'HTTP', 'deletions': 0})
    assert response.status_code == 409, response.json
    assert calls == []
    with engine.connect() as conn:
        assert conn.exec_driver_sql('SELECT count(*) FROM material').scalar() == 2
        assert conn.exec_driver_sql('SELECT material_id FROM in_order_item WHERE id=?',
            (ids['initem'],)).scalar() == ids['source']
        assert conn.exec_driver_sql('SELECT quantity FROM in_order_item WHERE id=?',
            (ids['initem'],)).scalar() == (3 if change == 'reference' else 2)
        if change == 'alias':
            assert conn.exec_driver_sql('SELECT alias FROM ai_material_alias WHERE id=?',
                (ids['alias'],)).scalar() == 'QA32-ALIAS-CHANGED'
        if change == 'target_alias':
            assert conn.exec_driver_sql('SELECT material_id FROM ai_material_alias WHERE id=?',
                (ids['alias'],)).scalar() == ids['material']
        if change.startswith('new_'):
            assert conn.exec_driver_sql('SELECT material_id FROM ai_material_alias WHERE alias_key=?',
                ('qa32-new-alias',)).scalar() == ids['source' if change == 'new_source_alias' else 'material']
    ledger = balances(ids)
    assert ledger['material'][0] and ledger['source'][0]
    assert ledger['source'][1]['one'] == (6 if change == 'stock' else 5)
