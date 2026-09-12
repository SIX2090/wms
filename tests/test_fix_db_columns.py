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
    conn.execute('''
        CREATE TABLE in_order (
            id INTEGER PRIMARY KEY,
            order_no TEXT,
            date TEXT
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


def test_fix_columns_adds_warehouse_to_production_requisition(temp_db):
    """fix_columns 应为 production_requisition 添加 warehouse 列（BUG-2026-08-08-001）。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(production_requisition)').fetchall()]
    conn.close()

    assert 'warehouse' in cols


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
    assert 'warehouse' in pr_cols


def test_fix_columns_adds_location_to_in_order(temp_db):
    """fix_columns 应为 in_order 添加 location 列（BUG-2026-08-17-001）。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(in_order)').fetchall()]
    conn.close()

    assert 'location' in cols


def test_fix_columns_adds_auto_push_requisition_to_in_order(temp_db):
    """fix_columns 应为 in_order 添加 auto_push_requisition 列（BUG-2026-08-17-001）。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(in_order)').fetchall()]
    conn.close()

    assert 'auto_push_requisition' in cols


def test_fix_columns_adds_location_to_out_order(temp_db):
    """fix_columns 应为 out_order 添加 location 列（BUG-2026-08-17-001）。"""
    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
    conn.close()

    assert 'location' in cols


def test_fix_columns_location_backfills_default(temp_db):
    """in_order.location 列应为 NOT NULL DEFAULT ''，已有行回填空串（BUG-2026-08-17-001）。"""
    conn = sqlite3.connect(temp_db)
    conn.execute("INSERT INTO in_order (order_no) VALUES ('PI-TEST-001')")
    conn.commit()
    conn.close()

    fix_columns(db_path=temp_db)

    conn = sqlite3.connect(temp_db)
    row = conn.execute("SELECT location, auto_push_requisition FROM in_order WHERE order_no='PI-TEST-001'").fetchone()
    conn.close()

    assert row is not None
    assert row[0] == ''
    assert row[1] == 0


def test_fix_columns_skips_missing_tables(temp_db):
    """in_order 表不存在时不应报错（全新空库防御，BUG-2026-08-17-001）。"""
    conn = sqlite3.connect(temp_db)
    conn.execute('DROP TABLE in_order')
    conn.commit()
    conn.close()

    fix_columns(db_path=temp_db)  # 不应抛出异常


# ---- BUG-2026-09-05-001：盘点域补列（双保险，bat 强制先跑的兜底层）----

_OLD_CHECK_SCHEMA = """
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

_CHECK_EXPECTED = (
    ('inventory_check', ('frozen_at',)),
    ('inventory_check_item', ('counted_by', 'counted_at', 'area')),
    ('inventory_check_scan', ('check_id',)),
    ('inventory_check_scan_item', ('area',)),
)


@pytest.fixture
def old_check_db(tmp_path):
    """构造缺盘点域列的旧库（含存量数据）。

    同时建出 fix_columns 前置依赖的 out_order/in_order/production_requisition
    表（脚本开头直接 PRAGMA 这三张表，不存在会报错；加表后才能走到盘点段）。
    """
    path = str(tmp_path / 'check_old.db')
    conn = sqlite3.connect(path)
    conn.executescript(_OLD_CHECK_SCHEMA)
    conn.executescript(
        """
        CREATE TABLE out_order (id INTEGER PRIMARY KEY, order_no TEXT);
        CREATE TABLE in_order (id INTEGER PRIMARY KEY, order_no TEXT);
        CREATE TABLE production_requisition (id INTEGER PRIMARY KEY, req_no TEXT);
        """
    )
    conn.execute(
        "INSERT INTO inventory_check_item"
        "(id, inventory_check_id, material_id, system_stock, actual_stock,"
        " difference, reason) VALUES (1, 1, 43, 10, 8, -2, '旧数据')"
    )
    conn.commit()
    conn.close()
    return path


def _check_cols(db_path, table):
    conn = sqlite3.connect(db_path)
    rows = conn.execute('PRAGMA table_info(%s)' % table).fetchall()
    conn.close()
    return [r[1] for r in rows]


def test_fix_columns_adds_inventory_check_columns(old_check_db):
    """fix_columns 应补齐盘点域全部缺列（BUG-2026-09-05-001 双保险）。"""
    fix_columns(db_path=old_check_db)
    for table, cols in _CHECK_EXPECTED:
        cur = _check_cols(old_check_db, table)
        for col in cols:
            assert col in cur, f'未补齐: {table}.{col}'
    # 存量数据不受影响
    conn = sqlite3.connect(old_check_db)
    row = conn.execute(
        "SELECT system_stock, reason FROM inventory_check_item WHERE id = 1"
    ).fetchone()
    conn.close()
    assert row == (10, '旧数据')


def test_fix_columns_inventory_check_idempotent(old_check_db):
    """盘点补列重复执行不报错、不重复 ALTER。"""
    fix_columns(db_path=old_check_db)
    before = {
        table: _check_cols(old_check_db, table)
        for table, _ in _CHECK_EXPECTED
    }
    fix_columns(db_path=old_check_db)
    fix_columns(db_path=old_check_db)
    after = {
        table: _check_cols(old_check_db, table)
        for table, _ in _CHECK_EXPECTED
    }
    assert before == after


# ---- BUG-2026-09-12（R6 第 5 次复发）：P1-5 销售退货入库来源销售订单列 ----

_P15_EXPECTED = (
    ('in_order', 'source_sales_order_id'),
    ('in_order', 'source_sales_order_no'),
    ('in_order_item', 'source_sales_order_item_id'),
)


def test_fix_columns_adds_sales_return_source_columns(temp_db):
    """fix_columns 应补齐 P1-5 销售退货入库的来源销售订单列。

    2026-09-12 生产事故：这三列只加在 app.py auto_migrate_database() 里，
    而 start_wms_*.bat 默认 WMS_NO_DB_TOUCH=1 整体跳过它，兜底层又没同步，
    存量库重启后首页 index() 直接 500：no such column: in_order.source_sales_order_id。
    """
    conn = sqlite3.connect(temp_db)
    conn.execute('CREATE TABLE in_order_item (id INTEGER PRIMARY KEY, in_order_id INTEGER)')
    conn.commit()
    conn.close()

    fix_columns(db_path=temp_db)

    for table, col in _P15_EXPECTED:
        assert col in _check_cols(temp_db, table), f'未补齐: {table}.{col}'


def test_fix_columns_sales_return_columns_idempotent(temp_db):
    """重复执行不报错、不重复 ALTER。"""
    conn = sqlite3.connect(temp_db)
    conn.execute('CREATE TABLE in_order_item (id INTEGER PRIMARY KEY, in_order_id INTEGER)')
    conn.commit()
    conn.close()

    fix_columns(db_path=temp_db)
    before = {t: _check_cols(temp_db, t) for t in ('in_order', 'in_order_item')}
    fix_columns(db_path=temp_db)
    after = {t: _check_cols(temp_db, t) for t in ('in_order', 'in_order_item')}
    assert before == after


def test_p15_ddl_matches_app_py_antidrift():
    """防漂移：fix_db_columns 的 P1-5 补列 DDL 必须与 app.py 的定义逐字一致。

    app.py 用「(列名, 类型) 元组 + f-string 拼 ALTER」，故按类型片段比对：
    ADD COLUMN <列名> <类型> 必须在 fix_db_columns.py 中出现，且该 (列名, 类型)
    组合必须出现在 app.py 的迁移定义里——任一侧改动而另一侧没跟，这里立刻红。
    """
    root = os.path.dirname(os.path.dirname(__file__))
    with open(os.path.join(root, 'app', 'app.py'), encoding='utf-8') as f:
        app_src = f.read()
    with open(os.path.join(root, 'app', 'fix_db_columns.py'), encoding='utf-8') as f:
        fix_src = f.read()

    expected_ddl = {
        ('in_order', 'source_sales_order_id'): 'ADD COLUMN source_sales_order_id INTEGER',
        ('in_order', 'source_sales_order_no'): 'ADD COLUMN source_sales_order_no VARCHAR(50)',
        ('in_order_item', 'source_sales_order_item_id'):
            'ADD COLUMN source_sales_order_item_id INTEGER',
    }
    for (table, col), ddl in expected_ddl.items():
        assert ddl in fix_src, f'fix_db_columns.py 缺少 {table}.{col} 的补列 DDL'
        # app.py 侧：列定义必须存在（类型取自模型/迁移定义）
        assert f"'{col}'" in app_src, f'app.py 未登记 {col}'
        assert col in app_src

    # in_order_item 的 ALTER 在 app.py 里是整句字面量，可直接逐字比对
    assert 'ALTER TABLE in_order_item ADD COLUMN source_sales_order_item_id INTEGER' in app_src

    # 生产一次性止血脚本 fix_p15_columns.py 必须与上面同一份清单，
    # 否则「脚本补了 A 列、兜底层补了 B 列」，事故换个库又复发
    from fix_p15_columns import MIGRATIONS as standalone_migs
    expected_migs = {
        ('in_order', 'source_sales_order_id', 'INTEGER'),
        ('in_order', 'source_sales_order_no', 'VARCHAR(50)'),
        ('in_order_item', 'source_sales_order_item_id', 'INTEGER'),
    }
    assert set(standalone_migs) == expected_migs, (
        'fix_p15_columns.py 的 MIGRATIONS 与 fix_db_columns / app.py 不一致 '
        f'（多余 {set(standalone_migs) - expected_migs}、'
        f'缺失 {expected_migs - set(standalone_migs)}）'
    )


def test_fix_columns_ddl_matches_app_py_and_standalone_script():
    """防漂移：fix_db_columns 盘点补列 DDL 必须与 app.py ensure_inventory_check_columns
    及 app/fix_inventory_check_columns.py 的清单完全一致（R6 机制级防复发）。"""
    from app.fix_db_columns import _INVENTORY_CHECK_MIGRATIONS as fixdb_ddl
    from app.fix_inventory_check_columns import (
        CHECK_COLUMN_MIGRATIONS as standalone_ddl,
    )

    # 结构展开成 {(表名, 列名): DDL} 便于比对
    def flat(migs):
        return {
            (tbl, col): stmt
            for tbl, _pragma, col_stmts in migs
            for col, stmt in col_stmts
        }

    assert flat(fixdb_ddl) == flat(standalone_ddl), (
        'fix_db_columns 与 fix_inventory_check_columns 清单不一致'
    )

    # 与 app.py ensure_inventory_check_columns 的 ALTER 逐字一致
    app_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'app.py')
    with open(app_src, encoding='utf-8') as f:
        src = f.read()
    for (_tbl, _col), stmt in flat(fixdb_ddl).items():
        assert stmt in src, f'fix_db_columns DDL 与 app.py 不一致: {stmt}'
