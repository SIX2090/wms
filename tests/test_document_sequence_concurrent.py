"""Real independent SQLite writers reserve formal numbers in their transaction."""
import threading
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import app as w
from tests.test_native_request_concurrent import file_case
from scripts.verify_db_guard import require_isolated_test_runtime


def test_reserve_document_number_serializes_two_writers_and_multiple_allocations(file_case, monkeypatch):
    from services import document_numbering

    first_reserved = threading.Event()
    second_entered = threading.Event()
    original = document_numbering.reserve_document_number
    results, errors, connections = [], [], set()

    def reserve(session, base, maximum):
        if threading.current_thread().name == 'sequence-second':
            second_entered.set()
        return original(session, base, maximum)

    monkeypatch.setattr(document_numbering, 'reserve_document_number', reserve)

    def save(index):
        try:
            with w.app.app_context():
                connections.add(id(w.db.session.connection().connection.driver_connection))
                if index:
                    assert first_reserved.wait(timeout=5)
                first = w.generate_order_no('IN')
                if not index:
                    first_reserved.set()
                    assert second_entered.wait(timeout=5)
                second = w.generate_order_no('IN')
                w.db.session.add_all([w.InOrder(order_no=first), w.InOrder(order_no=second)])
                w.db.session.commit()
                results.extend((first, second))
                w.db.session.remove()
        except Exception as error:
            errors.append(repr(error))

    threads = [threading.Thread(target=save, args=(i,), name='sequence-first' if i == 0
                                else 'sequence-second') for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads)
    assert not errors, errors
    assert len(connections) == 2
    assert len(results) == len(set(results)) == 4
    with w.app.app_context():
        assert w.InOrder.query.count() == 4
        assert w.StockTransaction.query.count() == 0
        w.db.session.remove()


def test_reserve_document_number_across_owned_child_processes(file_case):
    _engine, database, *_rest = file_case
    profile = require_isolated_test_runtime()
    source = Path(__file__).resolve().parents[1] / 'app/services/document_numbering.py'
    # The inherited LPAC/Job/network restrictions remain in force. Child code
    # loads only this service's functions and a synthetic table mapping, never
    # WMS/config, site startup hooks, or an inherited database URL.
    code = r'''
import ast, json, pathlib, platform, sys, sysconfig, time, types
platform.machine = lambda: 'synthetic'
sys.path.append(sysconfig.get_paths()['purelib'])
from sqlalchemy import Column, Integer, String, MetaData, Table, select, update, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
import re
database, source, directory, actor = sys.argv[1:]
table = Table('system_setting', MetaData(), Column('id', Integer, primary_key=True),
              Column('key', String, unique=True), Column('value', String), Column('remark', String))
scope = dict(SystemSetting=types.SimpleNamespace(__table__=table), select=select, update=update,
             IntegrityError=IntegrityError, re=re, KEY_PREFIX='document_sequence:')
nodes = [node for node in ast.parse(pathlib.Path(source).read_text(encoding='utf-8')).body
         if isinstance(node, ast.FunctionDef)]
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
             '<real-sequence-service-owned-child>', 'exec'), scope)
directory = pathlib.Path(directory)
(directory / (actor+'.ready')).write_text('ready', encoding='ascii')
deadline = time.monotonic()+15
while not (directory/'start').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('parent did not release synthetic barrier')
    time.sleep(0.01)
engine = create_engine(URL.create('sqlite', database=database), poolclass=NullPool,
                       connect_args={'timeout':20})
try:
    with Session(engine) as session:
        numbers = [scope['reserve_document_number'](session, 'IN2611', lambda: 0) for _ in range(4)]
        session.commit()
    print(json.dumps(numbers), flush=True)
finally:
    engine.dispose()
'''
    with tempfile.TemporaryDirectory(prefix='sequence-processes-', dir=profile) as directory:
        directory = Path(directory)
        script = directory / 'child.py'
        script.write_text(code, encoding='utf-8')
        empty = directory / 'stdin'
        empty.write_bytes(b'')
        environment = {key: os.environ[key] for key in ('SYSTEMROOT', 'WINDIR') if key in os.environ}
        environment.update(TEMP=str(directory), TMP=str(directory))
        children = []
        try:
            with empty.open('rb') as stdin:
                for actor in ('one', 'two'):
                    children.append(subprocess.Popen([sys.executable, '-I', '-S', '-B', '-X', 'utf8',
                        str(script), database, str(source), str(directory), actor],
                        stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                        env=environment, text=True, encoding='utf-8'))
                deadline = time.monotonic()+15
                while not all((directory/(actor+'.ready')).exists() for actor in ('one', 'two')):
                    assert time.monotonic() < deadline, 'Owned children did not reach their barrier'
                    assert all(child.poll() is None for child in children), 'Owned child failed before barrier'
                    time.sleep(0.01)
                (directory/'start').write_text('start', encoding='ascii')
                results = []
                for child in children:
                    stdout, stderr = child.communicate(timeout=30)
                    assert child.returncode == 0, stderr
                    results.extend(json.loads(stdout))
            assert len(results) == len(set(results)) == 8
            assert sorted(int(number[6:]) for number in results) == list(range(1, 9))
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                child.communicate(timeout=10)
