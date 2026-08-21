# -*- coding: utf-8 -*-
"""内置打印模板无条件同步回归测试（BUG-2026-08-21-002）。

背景：ensure_default_print_templates() 只挂在 initialize_database() 里，
而 start_wms_offline.bat / start_wms_auto.bat 默认 WMS_NO_DB_TOUCH=1 会跳过
initialize_database()，导致「系统默认入库单模板」「系统默认领料单模板」的
template_type 一直停在 'html'、html_template_content 仍是旧样式（RECEIPT 副标题、
序号/备注列、合计行、四格签名行），修改后的 Excel 默认模板线上永不生效。

修复：app.py 新增 _ensure_default_print_templates_unconditional()，用独立 sqlite
连接、独立于迁移开关、幂等地把两个内置模板 template_type 对齐为 'excel'、
html_template_content 对齐为常量。
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))

import app as app_module  # noqa: E402


def _make_db(db_path: Path, table: str, name: str) -> Path:
    """构造一个含旧样式内置模板的 sqlite 库（旧 html + 含合计行内容）。"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"""CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                name TEXT,
                template_type TEXT,
                excel_template_path TEXT,
                html_template_content TEXT,
                is_default INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            )"""
        )
        conn.execute(
            f"INSERT INTO {table} "
            "(id, name, template_type, html_template_content, is_default, created_at, updated_at) "
            "VALUES (1, ?, 'html', ?, 1, datetime('now'), datetime('now'))",
            (name, "<div>旧样式含 RECEIPT 与合计行</div>"),
        )
        conn.commit()
    return db_path


def _call_sync(db_path: Path):
    app_module._ensure_default_print_templates_unconditional(str(db_path))


def test_in_order_template_synced_to_excel(tmp_path):
    """入库单默认模板应从 html 旧样式同步为 excel + 新内容。"""
    db_path = _make_db(tmp_path / "inv.db", "in_order_print_template", "系统默认入库单模板")
    _call_sync(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT template_type, html_template_content FROM in_order_print_template WHERE id=1"
        ).fetchone()
    assert row[0] == "excel"
    assert row[1] == app_module.DEFAULT_IN_ORDER_HTML_TEMPLATE


def test_out_order_template_synced_to_excel(tmp_path):
    """领料单默认模板应从 html 旧样式同步为 excel + 新内容。"""
    db_path = _make_db(tmp_path / "inv.db", "out_order_print_template", "系统默认领料单模板")
    _call_sync(db_path)
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT template_type, html_template_content FROM out_order_print_template WHERE id=1"
        ).fetchone()
    assert row[0] == "excel"
    assert row[1] == app_module.DEFAULT_OUT_ORDER_HTML_TEMPLATE


def test_idempotent_repeat_sync(tmp_path):
    """重复同步无变化、不报错。"""
    db_path = _make_db(tmp_path / "inv.db", "in_order_print_template", "系统默认入库单模板")
    _call_sync(db_path)
    before = None
    with sqlite3.connect(db_path) as conn:
        before = conn.execute("SELECT template_type, html_template_content, is_default "
                              "FROM in_order_print_template WHERE id=1").fetchone()
    _call_sync(db_path)
    with sqlite3.connect(db_path) as conn:
        after = conn.execute("SELECT template_type, html_template_content, is_default "
                             "FROM in_order_print_template WHERE id=1").fetchone()
    assert before == after


def test_missing_table_skips_without_error(tmp_path):
    """库中无打印模板表时静默跳过，不抛异常。"""
    db_path = tmp_path / "inv.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE warehouse (id INTEGER PRIMARY KEY, name TEXT)")
    app_module._ensure_default_print_templates_unconditional(str(db_path))  # 不应抛异常