# -*- coding: utf-8 -*-
"""测试 fix_db_columns.py 的数据库字段修复功能。"""
import os
import sqlite3
import tempfile
import pytest

from app.fix_db_columns import fix_columns


@pytest.fixture
def temp_db():
    """创建临时数据库用于测试。"""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute('''
        CREATE TABLE out_order (
            id INTEGER PRIMARY KEY,
            order_no TEXT,
            date TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE production_requisition (
            id INTEGER PRIMARY KEY,
            req_no TEXT
        )
    ''')
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def test_fix_columns_adds_picker_to_out_order(temp_db):
    """fix_columns 应为 out_order 添加 picker 列。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
    conn.close()

    assert 'picker' in cols


def test_fix_columns_adds_picker_to_production_requisition(temp_db):
    """fix_columns 应为 production_requisition 添加 picker 列。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(production_requisition)').fetchall()]
    conn.close()

    assert 'picker' in cols


def test_fix_columns_idempotent(temp_db):
    """fix_columns 多次运行不会报错（幂等性）。"""
    fix_columns(db_path=temp_db)
    fix_columns(db_path=temp_db)  # 第二次运行不应报错

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
    conn.close()

    assert 'picker' in cols


def test_fix_columns_nonexistent_db():
    """fix_columns 对不存在的数据库应静默返回。"""
    fix_columns(db_path='/tmp/nonexistent_db_12345.db')  # 不应抛出异常


def test_fix_columns(temp_db):
    """fix_columns 应为两个表添加 picker 列（A9 规则要求同名测试）。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
    pr_cols = [r[1] for r in conn.execute('PRAGMA table_info(production_requisition)').fetchall()]
    conn.close()

    assert 'picker' in cols
    assert 'picker' in pr_cols
