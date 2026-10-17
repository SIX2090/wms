# -*- coding: utf-8 -*-
"""BUG-2026-10-17-013-F04：数据修复工具必须默认只读、可报告、可显式修 FK。"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'scripts' / 'data_repairs.py'


def _make_db(path):
    conn = sqlite3.connect(str(path))
    conn.executescript("""
        CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT);
        CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, name TEXT, spec TEXT,
                               brand TEXT, stock FLOAT);
        CREATE TABLE stock_transaction (id INTEGER PRIMARY KEY, material_id INTEGER,
                                        warehouse_id INTEGER, quantity FLOAT);
        CREATE TABLE location_inventory (id INTEGER PRIMARY KEY, material_id INTEGER,
                                         warehouse_id INTEGER, location TEXT, quantity FLOAT);
        CREATE TABLE ai_cleanup_log (id INTEGER PRIMARY KEY, log_id TEXT, executed_by INTEGER,
                                     FOREIGN KEY (executed_by) REFERENCES user(id));
        INSERT INTO user VALUES (1, 'admin');
        INSERT INTO material VALUES (1, 'M1', '轴承', '6204', '', 10);
        INSERT INTO material VALUES (2, 'M2', '轴承 ', '6204', '', 0);
        INSERT INTO stock_transaction VALUES (1, 1, 1, 5);
        INSERT INTO location_inventory VALUES (1, 1, 1, 'WH1', 9);
        INSERT INTO ai_cleanup_log VALUES (1, 'auto', 0);
    """)
    conn.commit()
    conn.close()


def _run(path, *args):
    return subprocess.run([sys.executable, str(TOOL), '--db', str(path), *args],
                          capture_output=True, text=True, encoding='utf-8', timeout=120)


def test_dry_run_reports_issues_without_writing(tmp_path):
    db = tmp_path / 'db.sqlite'
    _make_db(db)
    before = sqlite3.connect(str(db)).execute('SELECT executed_by FROM ai_cleanup_log').fetchone()
    result = _run(db, '--json')
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload['counts']['duplicate_materials'] == 1
    assert payload['counts']['stock_vs_txn'] == 1
    assert payload['counts']['location_vs_txn'] == 1
    assert payload['counts']['ai_cleanup_bad_executor'] == 1
    after = sqlite3.connect(str(db)).execute('SELECT executed_by FROM ai_cleanup_log').fetchone()
    assert before == after == (0,)


def test_apply_fk_requires_yes_and_then_fixes(tmp_path):
    db = tmp_path / 'db.sqlite'
    _make_db(db)
    refused = _run(db, '--apply-fk')
    assert refused.returncode == 2
    applied = _run(db, '--apply-fk', '--yes', '--json')
    assert applied.returncode in (0, 1)
    value = sqlite3.connect(str(db)).execute('SELECT executed_by FROM ai_cleanup_log').fetchone()[0]
    assert value == 1
