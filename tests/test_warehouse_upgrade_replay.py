"""Replay a warehouse upgrade against a clean and an interrupted synthetic SQLite copy."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
import sqlalchemy as sa

APP_DIR = Path(__file__).resolve().parents[1] / 'app'

# A real process exits after updating the second batch but before its commit.
WORKER = """
import json, os, sys
from pathlib import Path
from sqlalchemy import event
target, mode, app_dir = sys.argv[1:]
target = Path(target).resolve()
def guard(event, args):
    if event == 'sqlite3.connect' and str(args[0]) != ':memory:':
        assert Path(args[0]).resolve() == target
    if event in ('socket.bind', 'socket.connect'):
        raise AssertionError('unexpected network access')
sys.addaudithook(guard)
sys.path.insert(0, app_dir)
import app as w
with w.app.app_context():
    w.auto_migrate_database()
    writes = []
    def interrupt(conn, cursor, sql, params, context, many):
        if sql.lstrip().upper().startswith('UPDATE STOCK_TRANSACTION SET WAREHOUSE_ID'):
            writes.append(1)
            if len(writes) == 2:
                os._exit(73)
    if mode == 'crash':
        event.listen(w.db.engine, 'after_cursor_execute', interrupt)
    count = w.backfill_stock_txn_warehouse_id(batch_size=1)
    stocks = []
    monthly = []
    for wid in (1, 2):
        wh = w.db.session.get(w.Warehouse, wid)
        stocks.append(w.get_warehouse_stock_quantities(wh).get(1, 0))
        rows = w._build_warehouse_monthly_report(dict(warehouse_id=wid, material_code='ITEM',
                    start_month='2026-11', end_month='2026-11'))[1]
        monthly.append(rows[0]['ending_quantity'])
    print('RESULT ' + json.dumps([count, stocks, monthly]))
"""


def run_upgrade(target, mode):
    uri = 'sqlite:///' + target.as_posix()
    env = dict(os.environ, DATABASE_URL=uri, WMS_DATABASE_URI=uri, WMS_NO_DB_TOUCH='1',
               FLASK_ENV='production', WMS_ALLOW_INSECURE_COOKIE='1', WMS_SKIP_AUTO_UPDATE='1',
               WMS_SKIP_STARTUP_BACKUP='1', WMS_LOCAL_PRINT_AGENT='0', WMS_INIT_SAMPLE_DATA='0')
    run = subprocess.run([sys.executable, '-B', '-c', WORKER, str(target), mode, str(APP_DIR)],
                         cwd=target.parent, env=env, capture_output=True, timeout=75,
                         encoding='utf8', errors='replace')
    assert run.returncode == (73 if mode == 'crash' else 0), run.stderr + run.stdout
    if mode != 'crash':
        return json.loads(next(s[7:] for s in run.stdout.splitlines() if s.startswith('RESULT ')))


def snapshot(path):
    with sqlite3.connect(path) as db:
        assert db.execute('pragma integrity_check').fetchall() == [('ok',)]
        assert db.execute('pragma foreign_key_check').fetchall() == []
        return {table: db.execute('select ' + columns + ' from ' + table + ' order by id').fetchall()
                for table, columns in {
                    'material': 'id,code,stock',
                    'in_order': 'id,order_no,warehouse,status',
                    'sales_order': 'id,order_no,warehouse,warehouse_id',
                    'in_order_item': 'id,in_order_id,material_id,quantity',
                    'location_inventory': 'id,material_id,location,quantity,warehouse_id',
                    'stock_transaction': 'id,material_id,location,quantity,reference_id,warehouse_id',
                }.items()}


@pytest.fixture(scope='module')
def replay(tmp_path_factory):
    from app import db
    directory = tmp_path_factory.mktemp('warehouse-replay')
    seed = directory / 'legacy.db'
    engine = sa.create_engine('sqlite:///' + seed.as_posix())
    db.metadata.create_all(engine)
    engine.dispose()
    with sqlite3.connect(seed) as conn:
        conn.executescript("""
            insert into warehouse(id,code,name,is_default) values
                (1,'A','Renamed',1), (2,'B','Former',0), (3,'Renamed','Third',0);
            insert into customer(id,code,name) values (1,'C','Buyer');
            insert into unit(id,code,name) values (1,'EA','Each');
            insert into material_category(id,code,name) values (1,'CAT','Category');
            insert into material(id,code,name,stock,category_id,unit_id) values (1,'ITEM','Item',27,1,1);
            insert into in_order(id,order_no,warehouse,status,date,business_type,location,auto_push_requisition)
                values (1,'SYN-IN','A','completed','2026-11-01','采购入库','',0),
                       (2,'SYN-IN-B','Former','completed','2026-11-01','采购入库','',0);
            insert into in_order_item(id,in_order_id,material_id,quantity,price,amount,is_customer_supplied)
                values (1,1,1,17,1,17,0),(2,2,1,7,1,7,0);
            drop table sales_order;
            create table sales_order(id integer primary key, order_no text unique,
                warehouse text, customer_id integer, date date, status text);
            insert into sales_order(id,order_no,warehouse,customer_id) values
                (1,'SYN-S1','Renamed',1),(2,'SYN-S2','B',1);
            insert into location_inventory(id,material_id,warehouse_id,location,quantity) values
                (1,1,1,'B',1),(2,1,null,'B',2);
            insert into stock_transaction
                (id,material_id,transaction_type,location,quantity,reference_type,reference_id,created_at)
            values (1,1,'in','A',4,'in_order',1,'2026-11-01'),
                   (2,1,'in','Former',7,'in_order',1,'2026-11-01'),
                   (3,1,'in','A',6,'in_order',1,'2026-11-01'),
                   (4,1,'in','Former',3,null,null,'2026-11-01'),
                   (5,1,'in','A',7,'in_order',2,'2026-11-01');
        """)
    normal, resumed = directory/'normal.db', directory/'resumed.db'
    for path in (normal, resumed):
        shutil.copyfile(seed, path)
    first = run_upgrade(normal, 'normal')
    run_upgrade(resumed, 'crash')
    partial = snapshot(resumed)
    assert partial['stock_transaction'][0][-1] == 1
    assert all(row[-1] is None for row in partial['stock_transaction'][1:])
    run_upgrade(resumed, 'resume')
    expected = snapshot(normal)
    assert snapshot(resumed) == expected
    again = run_upgrade(resumed, 'again')
    assert again[0] == 0 and again[1:] == first[1:]
    assert snapshot(resumed) == expected
    return expected, first


def test_replay_keeps_conflicting_transactions_for_review(replay):
    facts, totals = replay
    assert facts['material'] == [(1, 'ITEM', 27)]
    assert facts['in_order'] == [(1, 'SYN-IN', 'A', 'completed'),
                                 (2, 'SYN-IN-B', 'Former', 'completed')]
    assert facts['in_order_item'] == [(1, 1, 1, 17), (2, 2, 1, 7)]
    assert [(r[0], r[3], r[-1]) for r in facts['stock_transaction']] == [
        (1, 4, 1), (2, 7, None), (3, 6, 1), (4, 3, 2), (5, 7, None)]
    assert totals[1:] == [[10, 3], [10, 3]]


def test_replay_preserves_conflicting_bin_and_all_quantities(replay):
    facts, _ = replay
    assert facts['location_inventory'] == [(1, 1, 'B', 1, 1), (2, 1, 'B', 2, None)]


def test_replay_keeps_ambiguous_sales_order_for_review(replay):
    facts, _ = replay
    assert facts['sales_order'] == [(1, 'SYN-S1', 'Renamed', None), (2, 'SYN-S2', 'B', 2)]



def test_warehouse_id_or_legacy_text():
    from app import SalesOrder, Warehouse
    from app import _sales_report_orders
    from db import db
    from app import app, Customer

    # Exercise the actual sales-query condition using its normal Flask session.
    with app.app_context():
        db.create_all()
        tx = db.session.begin_nested()
        try:
            buyer = Customer(name='Synthetic-replay-buyer', code='SYN-REPLAY')
            db.session.add(buyer)
            one = Warehouse(name='LEGACY-SHARED', code='LEGACY-A', is_default=False)
            two = Warehouse(name='LEGACY-B', code='LEGACY-OTHER', is_default=False)
            db.session.add_all((one, two))
            db.session.flush()
            db.session.execute(sa.update(Warehouse).where(Warehouse.id == two.id)
                               .values(code=one.name))
            for number, alias, wid in [('1', one.name, None), ('2', one.code, None),
                                       ('3', one.name, two.id)]:
                db.session.execute(SalesOrder.__table__.insert().values(
                    order_no='SYN-CHECK-'+number, warehouse=alias,
                    warehouse_id=wid, customer_id=buyer.id))
            db.session.flush()
            def found(wh):
                with app.test_request_context('/sales/execution_report', query_string={'warehouse_id': wh.id}):
                    return sorted(row.order_no for row in _sales_report_orders()
                                  if row.order_no.startswith('SYN-CHECK-'))
            assert found(one) == ['SYN-CHECK-2']
            assert found(two) == ['SYN-CHECK-3']
        finally:
            tx.rollback()
