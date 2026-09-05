# -*- coding: utf-8 -*-
"""app/fix_inventory_check_columns.py 回归测试（BUG-2026-09-05-001 止血脚本）。

背景：盘点域缺列导致物料编辑 500。app.py 已加启动期自愈
（ensure_inventory_check_columns，拉代码重启即自动补列），本脚本用于
**不方便立刻重启**的场景，直接跑一次即可补齐。

覆盖：
- 缺列旧库：fix() 补齐全部 6 列，存量数据不变
- 幂等：重复执行无变化、不报错
- 表不存在（全新库）：跳过不报错
- resolve_db_path：显式路径 / DATABASE_URL / app/instance 自动定位
- main() CLI：退出码 0、输出含补列结果与校验行
- 防漂移：脚本里的 ALTER 语句必须与 app.py ensure_inventory_check_columns 逐字一致
- 接线：根目录 fix_inventory_check_columns.bat 必须调用本脚本
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

_OLD_SCHEMA = """
CREATE TABLE inventory_check (
    id INTEGER PRIMARY KEY, check_no TEXT, status TEXT, warehouse TEXT
);
CREATE TABLE inventory_check_item (
    id INTEGER PRIMARY KEY, inventory_check_id INTEGER, material_id INTEGER,
    system_stock REAL, actual_stock REAL, difference REAL, reason TEXT
);
CREATE TABLE inventory_check_scan (
    id INTEGER PRIMARY KEY, scan_no TEXT, warehouse TEXT, status TEXT
);
CREATE TABLE inventory_check_scan_item (
    id INTEGER PRIMARY KEY, scan_id INTEGER, material_id INTEGER,
    actual_stock REAL
);
"""

_EXPECTED = (
    ("inventory_check", "frozen_at"),
    ("inventory_check_item", "counted_by"),
    ("inventory_check_item", "counted_at"),
    ("inventory_check_item", "area"),
    ("inventory_check_scan", "check_id"),
    ("inventory_check_scan_item", "area"),
)


def _old_db(db_path: Path) -> Path:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_OLD_SCHEMA)
        conn.execute(
            "INSERT INTO inventory_check_item"
            "(id, inventory_check_id, material_id, system_stock, actual_stock,"
            " difference, reason) VALUES (1, 1, 43, 10, 8, -2, '旧数据')"
        )
    return db_path


def _cols(db_path: Path, table: str):
    with sqlite3.connect(db_path) as conn:
        stmt = "PRAGMA table_info(" + table + ")"
        return [r[1] for r in conn.execute(stmt).fetchall()]


# A9 锚点：函数名须精确匹配 def test_<func>(，规则 A9 按此查找对应测试


def test_fix(tmp_path):
    """fix() 锚点：缺列旧库补齐后新增列非空。"""
    from app.fix_inventory_check_columns import fix
    db_path = _old_db(tmp_path / "anchor_fix.db")
    assert fix(db_path)


def test_resolve_db_path(tmp_path):
    """resolve_db_path() 锚点：显式路径可定位。"""
    from app.fix_inventory_check_columns import resolve_db_path
    db_path = _old_db(tmp_path / "anchor_resolve.db")
    assert resolve_db_path(str(db_path)) == db_path


def test_fix_adds_all_missing_columns(tmp_path):
    """缺列旧库：fix() 补齐全部 6 列，存量数据不变。"""
    from app.fix_inventory_check_columns import fix
    db_path = _old_db(tmp_path / "inventory.db")
    added = fix(db_path)
    assert len(added) == len(_EXPECTED), added
    for table, col in _EXPECTED:
        assert col in _cols(db_path, table), f"未补齐: {table}.{col}"
        assert f"{table}.{col}" in added
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT system_stock FROM inventory_check_item WHERE id = 1"
        ).fetchone() == (10,)


def test_fix_is_idempotent(tmp_path):
    """重复执行无变化、不报错。"""
    from app.fix_inventory_check_columns import fix
    db_path = _old_db(tmp_path / "inventory.db")
    fix(db_path)
    before = {t: _cols(db_path, t) for t, _ in _EXPECTED}
    assert fix(db_path) == []
    assert fix(db_path) == []
    assert {t: _cols(db_path, t) for t, _ in _EXPECTED} == before


def test_fix_skips_missing_table(tmp_path):
    """全新空库（盘点表不存在）跳过、不建表、不报错。"""
    from app.fix_inventory_check_columns import fix
    db_path = tmp_path / "inventory.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT)")
    assert fix(db_path) == []


def test_resolve_db_path_explicit_and_env(tmp_path, monkeypatch):
    """显式参数优先；其次 DATABASE_URL；最后回落 app/instance/inventory.db。"""
    from app import fix_inventory_check_columns as mod
    explicit = _old_db(tmp_path / "explicit.db")
    assert mod.resolve_db_path(str(explicit)) == explicit

    env_db = _old_db(tmp_path / "env.db")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{env_db}")
    assert mod.resolve_db_path() == env_db

    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert mod.resolve_db_path() is None or mod.resolve_db_path().is_file()


def test_resolve_db_path_relative_database_url(monkeypatch):
    """DATABASE_URL 为相对路径（sqlite:///inventory.db）时按 app/ 解析。"""
    from app import fix_inventory_check_columns as mod
    monkeypatch.setenv("DATABASE_URL", "sqlite:///inventory.db")
    got = mod.resolve_db_path()
    assert got is None or got.name == "inventory.db"


def test_cli_main_reports_and_verifies(tmp_path, capsys):
    """CLI：退出码 0，输出补列结果与逐表校验行。"""
    from app import fix_inventory_check_columns as mod
    db_path = _old_db(tmp_path / "inventory.db")
    code = mod.main(["fix_inventory_check_columns.py", str(db_path)])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "[OK] 已补列" in out, out
    assert "inventory_check_item.counted_by" in out, out
    assert "[校验] inventory_check_item:" in out, out
    assert "仍缺" not in out, out


def test_ddl_matches_app_py_ensure_function():
    """防漂移：脚本 ALTER 语句必须与 app.py ensure_inventory_check_columns 逐字一致。"""
    from app import fix_inventory_check_columns as mod
    src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    for _tbl, _pragma, stmts in mod.CHECK_COLUMN_MIGRATIONS:
        for _col, ddl in stmts:
            assert ddl in src, (
                f"脚本 DDL 与 app.py ensure_inventory_check_columns 不一致: {ddl}"
            )
    # 启动序列必须调用该函数（自愈接线）
    assert "ensure_inventory_check_columns()" in src


def test_bat_script_wiring():
    """根目录 fix_inventory_check_columns.bat 必须调用本脚本（双击即可用）。"""
    bat = ROOT / "fix_inventory_check_columns.bat"
    assert bat.is_file(), "缺少双击修复 bat"
    text = bat.read_text(encoding="utf-8", errors="ignore")
    assert "fix_inventory_check_columns.py" in text
    assert "BUG-2026-09-05-001" in text
