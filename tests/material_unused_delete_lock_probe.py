"""Disposable file-DB concurrency proof, launched only by its isolated pytest wrapper."""
# 当前文件路径归属及应用出站隔离尚未证明；不得先导入应用或创建文件库。
raise RuntimeError('物料并发验证已阻止：隔离文件库及应用出站尚未证明')

from pathlib import Path
import json
import os
import sqlite3
import sys
import threading

database = Path(sys.argv[1]).resolve()
assert database.name == 'lock-test.db' and not database.exists()
repo = Path(__file__).resolve().parents[1]
os.environ.update(DATABASE_URL='sqlite:///'+database.as_posix(), WMS_DATABASE_URI='sqlite:///'+database.as_posix(),
                  WMS_NO_DB_TOUCH='1', WMS_ALLOW_INSECURE_COOKIE='1', WMS_SKIP_AUTO_UPDATE='1',
                  WMS_LOCAL_PRINT_AGENT='0', LOG_FILE=str(database.with_suffix('.log')))
sys.path.insert(0, str(repo/'app'))
import app as w
from sqlalchemy import event
from services.material_delete import delete_unused_materials

with w.app.app_context():
    assert Path(w.db.engine.url.database).resolve() == database
    w.db.create_all()
    material = w.Material(code='LOCK-CLEAN', name='并发清理合成物料', stock=0)
    w.db.session.add(material)
    w.db.session.commit()
    material_id = material.id
    proof = {}
    statements = []
    def competing_reference():
        with sqlite3.connect(database, timeout=0.05) as connection:
            connection.execute('PRAGMA foreign_keys=ON')
            try:
                connection.execute('INSERT INTO material_image(material_id, image) VALUES (?, ?)',
                                   (material_id, 'synthetic-concurrent.jpg'))
                connection.commit()
                proof['writer_during_check'] = 'unexpected_success'
            except sqlite3.OperationalError as exc:
                assert 'locked' in str(exc).lower()
                proof['writer_during_check'] = 'locked'
    def trace(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)
        if 'SELECT' in statement and 'FROM material ' in statement and not proof:
            worker = threading.Thread(target=competing_reference)
            worker.start()
            worker.join(3)
            assert not worker.is_alive()
    event.listen(w.db.engine, 'before_cursor_execute', trace)
    result, snapshots = delete_unused_materials([material_id])
    event.remove(w.db.engine, 'before_cursor_execute', trace)
    assert proof['writer_during_check'] == 'locked'
    assert statements[0] == 'BEGIN IMMEDIATE'
    assert result['deleted_count'] == 1 and len(snapshots) == 1
    with sqlite3.connect(database) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            connection.execute('INSERT INTO material_image(material_id,image) VALUES (?,?)',
                               (material_id, 'synthetic-late.jpg'))
        except sqlite3.IntegrityError:
            proof['writer_after_delete'] = 'foreign_key_rejected'
        else:
            raise AssertionError('Late writer created an orphan reference')
    assert w.db.session.get(w.Material, material_id) is None
    assert w.MaterialImage.query.count() == 0
    print(json.dumps(proof))
