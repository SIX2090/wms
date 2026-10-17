# -*- coding: utf-8 -*-
"""BUG-2026-10-17-014：一物多码合并工具（dry-run / 备份 / 外键重挂 / 库位合并 / 唯一索引）。"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'scripts' / 'merge_duplicate_materials.py'


def _make_db(path, backup_dir):
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, name TEXT, spec TEXT,
                               brand TEXT, stock FLOAT, price FLOAT);
        CREATE TABLE stock_transaction (id INTEGER PRIMARY KEY, material_id INTEGER,
                                        warehouse_id INTEGER, quantity FLOAT);
        CREATE TABLE in_order_item (id INTEGER PRIMARY KEY, material_id INTEGER, quantity FLOAT);
        CREATE TABLE location_inventory (id INTEGER PRIMARY KEY, material_id INTEGER,
                                         warehouse_id INTEGER, location TEXT, quantity FLOAT,
                                         UNIQUE(material_id, warehouse_id, location));
        INSERT INTO material VALUES (1, 'KEEP', '按钮', 'LA38', '', 2, 0);
        INSERT INTO material VALUES (2, 'LOSE', '按钮', 'LA38', '', 3, 0);
        INSERT INTO stock_transaction VALUES (1, 1, 1, 2);
        INSERT INTO stock_transaction VALUES (2, 2, 1, 3);
        INSERT INTO in_order_item VALUES (1, 2, 3);
        INSERT INTO location_inventory VALUES (1, 1, 1, 'A', 2);
        INSERT INTO location_inventory VALUES (2, 2, 1, 'A', 3);
    """)
    conn.commit()
    conn.close()
    (backup_dir).mkdir(parents=True, exist_ok=True)


def _run(db, backup, *args):
    return subprocess.run([sys.executable, str(TOOL), '--db', str(db),
                           '--pairs', '2:1', '--backup-dir', str(backup), *args],
                          capture_output=True, text=True, encoding='utf-8', timeout=120)


def test_dry_run_does_not_modify(tmp_path):
    db, backup = tmp_path / 'db.sqlite', tmp_path / 'backups'
    _make_db(db, backup)
    result = _run(db, backup)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['mode'] == 'dry-run'
    assert payload['pairs'][0]['actions']
    assert sqlite3.connect(str(db)).execute('SELECT COUNT(*) FROM material').fetchone()[0] == 2


def test_apply_merges_references_and_creates_index(tmp_path):
    db, backup = tmp_path / 'db.sqlite', tmp_path / 'backups'
    _make_db(db, backup)
    result = _run(db, backup, '--apply', '--yes', '--create-unique-index')
    assert result.returncode == 0, result.stderr
    conn = sqlite3.connect(str(db))
    assert conn.execute('SELECT COUNT(*) FROM material').fetchone()[0] == 1
    assert conn.execute('SELECT stock FROM material WHERE id=1').fetchone()[0] == 5
    assert conn.execute('SELECT COUNT(*) FROM in_order_item WHERE material_id=2').fetchone()[0] == 0
    assert conn.execute('SELECT COUNT(*) FROM in_order_item WHERE material_id=1').fetchone()[0] == 1
    assert conn.execute('SELECT quantity FROM location_inventory WHERE material_id=1').fetchone()[0] == 5
    assert conn.execute('SELECT COUNT(*) FROM stock_transaction WHERE material_id=2').fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='uq_material_dedupe_key'").fetchone()[0] == 1
    assert list(backup.glob('manual_merge_*.db'))
