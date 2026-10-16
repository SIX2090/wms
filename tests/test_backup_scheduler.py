# -*- coding: utf-8 -*-
"""F1.2 备份机制测试：backup_scheduler 调度模块 + online_backup/restore_backup 脚本。

验收口径（任务卡 F1.2）：
- 手动触发备份 -> integrity_check=ok 且包含最新事务；
- 到期清理只动 auto_daily_*.db；
- 恢复脚本在库被占用时拒绝执行、备份损坏时拒绝执行。
"""
import importlib.util
import os
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import backup_scheduler  # noqa: E402


def _load_script(name: str):
    """按路径加载 scripts/ 下的独立脚本（非包，不能常规 import）。"""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_db(path: Path, rows: int = 3) -> Path:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
        # 恢复入口现在拒绝非WMS库；保留原t表内容/留底断言，并补齐真实入口必需的结构。
        conn.executescript('''
            CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, stock REAL);
            CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE stock_transaction (id INTEGER PRIMARY KEY, material_id INTEGER,
                quantity REAL, warehouse_id INTEGER, created_at TEXT);
            CREATE TABLE in_order (id INTEGER PRIMARY KEY, order_no TEXT, status TEXT);
            CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT, status TEXT);
            CREATE TABLE user (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT, role TEXT);
            CREATE TABLE system_setting (id INTEGER PRIMARY KEY, key TEXT, value TEXT);
        ''')
        conn.executemany("INSERT INTO t (v) VALUES (?)", [(f"r{i}",) for i in range(rows)])
        conn.commit()
    finally:
        conn.close()
    return path


# ---------------- online_backup.py ----------------

def test_online_backup_integrity_and_content(tmp_path):
    online_backup = _load_script("online_backup")
    src = _make_db(tmp_path / "src.db", rows=5)
    dest = tmp_path / "sub" / "dest.db"  # 目录不存在，验证自动建目录
    assert online_backup.main([str(src), str(dest)]) == 0
    conn = sqlite3.connect(str(dest))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 5
    finally:
        conn.close()


def test_online_backup_missing_source_fails(tmp_path):
    online_backup = _load_script("online_backup")
    assert online_backup.main([str(tmp_path / "nope.db"), str(tmp_path / "d.db")]) == 2
    assert not (tmp_path / "d.db").exists()


# ---------------- restore_backup.py ----------------

def test_restore_refuses_locked_target(tmp_path):
    restore_backup = _load_script("restore_backup")
    src = _make_db(tmp_path / "backup.db")
    target = _make_db(tmp_path / "live.db")
    # 模拟运行中的 WMS：持有一个 IMMEDIATE 写事务不放手
    held = sqlite3.connect(str(target), timeout=1)
    held.execute("BEGIN IMMEDIATE")
    try:
        rc = restore_backup.main([str(src), "--db", str(target), "--yes"])
        assert rc == 3, "库被占用时必须拒绝恢复（防在线覆盖撕裂）"
    finally:
        held.execute("ROLLBACK")
        held.close()


def test_restore_refuses_corrupt_backup(tmp_path):
    restore_backup = _load_script("restore_backup")
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a sqlite database at all")
    target = _make_db(tmp_path / "target.db")
    rc = restore_backup.main([str(bad), "--db", str(target), "--yes"])
    assert rc == 2, "损坏备份必须被拒绝"
    # 目标库未被破坏
    conn = sqlite3.connect(str(target))
    try:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 3
    finally:
        conn.close()


def test_restore_success_leaves_safety_copy(tmp_path):
    restore_backup = _load_script("restore_backup")
    src = _make_db(tmp_path / "backup.db", rows=7)
    target = _make_db(tmp_path / "target.db", rows=2)
    rc = restore_backup.main([str(src), "--db", str(target), "--yes"])
    assert rc == 0
    conn = sqlite3.connect(str(target))
    try:
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 7
    finally:
        conn.close()
    safeties = list(tmp_path.glob("target.db.before_restore_*"))
    assert len(safeties) == 1, "覆盖前必须留底当前库"


# ---------------- backup_scheduler ----------------

def test_parse_hhmm_valid_and_fallback():
    assert backup_scheduler._parse_hhmm("02:00") == (2, 0)
    assert backup_scheduler._parse_hhmm("23:59") == (23, 59)
    assert backup_scheduler._parse_hhmm("垃圾") == (2, 0)
    assert backup_scheduler._parse_hhmm("25:00") == (2, 0)


def test_get_backup_dir(monkeypatch, tmp_path):
    """精确名测试（A9）：默认目录与 env 覆盖。"""
    monkeypatch.delenv("WMS_BACKUP_DIR", raising=False)
    assert backup_scheduler.get_backup_dir() == Path(backup_scheduler.DEFAULT_BACKUP_DIR)


def test_get_backup_dir_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("WMS_BACKUP_DIR", str(tmp_path / "nas"))
    assert backup_scheduler.get_backup_dir() == tmp_path / "nas"
    monkeypatch.delenv("WMS_BACKUP_DIR")
    assert backup_scheduler.get_backup_dir() == Path(backup_scheduler.DEFAULT_BACKUP_DIR)


def test_run_daily_backup(monkeypatch, tmp_path):
    """精确名测试（A9）：手动触发备份 -> integrity ok 且含源库数据。"""
    import app as app_module

    src = _make_db(tmp_path / "inventory.db", rows=4)
    monkeypatch.setattr(app_module, "get_database_file_path", lambda: str(src))
    monkeypatch.setenv("WMS_BACKUP_DIR", str(tmp_path / "bk"))
    from app import app as flask_app
    with flask_app.app_context():
        dest = backup_scheduler.run_daily_backup(flask_app)
    assert dest.exists()


def test_run_daily_backup_verified_and_contains_data(monkeypatch, tmp_path):
    """手动触发一次备份：integrity_check=ok 且包含源库数据（验收口径）。"""
    import app as app_module

    src = _make_db(tmp_path / "inventory.db", rows=9)
    monkeypatch.setattr(app_module, "get_database_file_path", lambda: str(src))
    monkeypatch.setenv("WMS_BACKUP_DIR", str(tmp_path / "backups"))

    from app import app as flask_app
    with flask_app.app_context():
        dest = backup_scheduler.run_daily_backup(flask_app)

    assert dest.name.startswith(backup_scheduler.AUTO_BACKUP_PREFIX)
    conn = sqlite3.connect(str(dest))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 9
    finally:
        conn.close()


def test_cleanup_expired_only_touches_auto_daily(monkeypatch, tmp_path):
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "30")
    old_auto = _make_db(tmp_path / "auto_daily_20200101_020000_inventory.db")
    new_auto = _make_db(tmp_path / "auto_daily_29990101_020000_inventory.db")
    other = _make_db(tmp_path / "before_github_update_20200101_inventory.db")
    old_ts = time.time() - 40 * 86400
    os.utime(old_auto, (old_ts, old_ts))
    os.utime(other, (old_ts, old_ts))  # 更新前备份再老也不许动

    removed = backup_scheduler._cleanup_expired(tmp_path)
    assert removed == 1
    assert not old_auto.exists()
    assert new_auto.exists()
    assert other.exists(), "更新前备份不属于自动清理范围"


class _FakeScheduler:
    def __init__(self):
        self.jobs = []

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append((func, trigger, kwargs))


def test_register_backup_jobs(monkeypatch):
    """精确名测试（A9）：开关语义——关时返回 False 且不注册。"""
    monkeypatch.setenv("AUTO_BACKUP_ENABLED", "0")
    assert backup_scheduler.register_backup_jobs(_FakeScheduler(), object()) is False


def test_register_backup_jobs_disabled_by_env(monkeypatch):
    monkeypatch.setenv("AUTO_BACKUP_ENABLED", "0")
    sched = _FakeScheduler()
    assert backup_scheduler.register_backup_jobs(sched, object()) is False
    assert not sched.jobs


def test_register_backup_jobs_cron_wired(monkeypatch):
    monkeypatch.setenv("AUTO_BACKUP_ENABLED", "1")
    monkeypatch.setenv("AUTO_BACKUP_TIME", "03:30")
    sched = _FakeScheduler()
    assert backup_scheduler.register_backup_jobs(sched, object()) is True
    assert len(sched.jobs) == 1
    _, trigger, kwargs = sched.jobs[0]
    assert trigger == "cron"
    assert kwargs["hour"] == 3 and kwargs["minute"] == 30
    assert kwargs["id"] == "daily_auto_backup"
    assert kwargs["replace_existing"] is True and kwargs["max_instances"] == 1
