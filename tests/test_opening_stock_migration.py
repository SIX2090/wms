# -*- coding: utf-8 -*-
"""ARCH-OS-DOC-01 回归：期初库存多单据化的幂等迁移。

背景：期初库存原为"每 (物料,仓库) 一条余额"的扁平台账，带
AI-OS-MW-001 的 UniqueConstraint(material_id, warehouse_id)。用户要求
"期初库存要做几张单 + 导入的单据改日期 + 首上下末导航"，因此升级为
"单据头 opening_stock_doc + 明细行 opening_stock.doc_id"。

迁移必须满足三条不变量：
  1) 只加归属不改账：quantity/price/amount 与 Material.stock 均不变；
  2) 幂等：重复启动不重复建表、不重复建单、不重复回填；
  3) 老库的全局唯一约束必须移除，否则同物料同仓的第二张单撞约束 500。

实现说明：app 的库路径由 DATABASE_URL 环境变量在**导入时**决定，且 app
模块导入时会跑一串 module-level 回填（缺表会报错）。因此本测试用
subprocess 起独立进程，在导入 app 之前设好 DATABASE_URL，避免污染
pytest 会话的内存库与导入顺序。
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"


# 模拟老库：opening_stock 带 AI-OS-MW-001 全局唯一约束，无 doc_id 列，无单据头表
_LEGACY_SCHEMA = """
CREATE TABLE material (
    id INTEGER PRIMARY KEY, code VARCHAR(50), name VARCHAR(200),
    stock FLOAT DEFAULT 0, spec VARCHAR(200), price FLOAT DEFAULT 0
);
CREATE TABLE warehouse (
    id INTEGER PRIMARY KEY, code VARCHAR(50), name VARCHAR(200),
    status VARCHAR(20) DEFAULT 'active', is_default BOOLEAN DEFAULT 0
);
CREATE TABLE user (
    id INTEGER PRIMARY KEY, username VARCHAR(80), password_hash VARCHAR(200)
);
CREATE TABLE opening_stock (
    id INTEGER PRIMARY KEY,
    material_id INTEGER NOT NULL,
    warehouse_id INTEGER,
    date DATE,
    location VARCHAR(100) NOT NULL DEFAULT '',
    quantity FLOAT NOT NULL DEFAULT 0,
    price FLOAT NOT NULL DEFAULT 0,
    amount FLOAT NOT NULL DEFAULT 0,
    remark VARCHAR(500),
    operator_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uix_opening_stock_material_warehouse UNIQUE (material_id, warehouse_id)
);
CREATE INDEX idx_opening_stock_material ON opening_stock(material_id);
CREATE INDEX idx_opening_stock_warehouse ON opening_stock(warehouse_id);
CREATE INDEX idx_opening_stock_created ON opening_stock(created_at);
"""


def _make_legacy_db(db_file, rows):
    """造一个老库。rows 为 (material_id, warehouse_id, date, quantity, price, amount)。"""
    if db_file.exists():
        db_file.unlink()
    conn = sqlite3.connect(str(db_file))
    conn.executescript(_LEGACY_SCHEMA)
    for mid, code, name in ((1, 'M001', '螺栓'), (2, 'M002', '螺母')):
        conn.execute("INSERT INTO material (id, code, name, stock, spec, price) "
                     "VALUES (?,?,?,'0','M8',1.0)", (mid, code, name))
    for wid, code, name in ((1, 'WH001', '主仓'), (2, 'WH002', '副仓')):
        conn.execute("INSERT INTO warehouse (id, code, name, status) VALUES (?,?,?,'active')",
                     (wid, code, name))
    for mid, wid, d, qty, price, amount in rows:
        conn.execute(
            "INSERT INTO opening_stock (material_id, warehouse_id, date, quantity, price, amount) "
            "VALUES (?,?,?,?,?,?)", (mid, wid, d, qty, price, amount))
    conn.commit()
    conn.close()


def _run_migration(db_file, times=1):
    """在独立进程中跑迁移（导入 app 前设好 DATABASE_URL，避免内存库串扰）。

    Windows 注意（BUG-2026-09-20-007）：**不能**把路径直接拼进 `-c` 源码。
    `C:\\Users\\...` 里的 `\\U` 会被 Python 当成 unicode 转义，
    子进程直接 `SyntaxError: (unicode error) 'unicodeescape'`。
    故 DATABASE_URL 改为经**环境变量**传递给子进程，源码里只读不拼。
    """
    script = textwrap.dedent("""
        import os, sys
        sys.path.insert(0, os.environ['WMS_TEST_APP_DIR'])
        os.chdir(os.environ['WMS_TEST_APP_DIR'])
        os.environ.setdefault('WMS_BOOTSTRAP_PASSWORD', 'admin')
        os.environ['WMS_DEBUG'] = '0'
        os.environ['WMS_SKIP_AUTO_UPDATE'] = '1'
        from app import auto_migrate_database
        for _ in range(int(os.environ['WMS_TEST_MIGRATE_TIMES'])):
            auto_migrate_database()
        print('MIGRATION_OK')
    """)
    env = dict(os.environ)
    env['WMS_TEST_APP_DIR'] = str(APP_DIR)
    env['WMS_TEST_MIGRATE_TIMES'] = str(times)
    # sqlite:/// 后跟绝对路径；Windows 下用正斜杠，避免任何转义歧义
    env['DATABASE_URL'] = 'sqlite:///' + str(db_file).replace('\\', '/')
    env['WMS_BOOTSTRAP_PASSWORD'] = 'admin'
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=str(APP_DIR), timeout=180, env=env,
    )
    assert "MIGRATION_OK" in result.stdout, (
        f"迁移进程未正常完成\nstdout:\n{result.stdout[-3000:]}\nstderr:\n{result.stderr[-3000:]}")
    return result.stdout


def _fetch(db_file, sql, params=()):
    conn = sqlite3.connect(str(db_file))
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


class TestOpeningStockDocMigration:
    """迁移幂等性与数据无损性。"""

    def test_t0_legacy_db_precondition(self, tmp_path):
        """前置自检：造的确实是带全局唯一约束的老库，且同物料同仓插两行会失败。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [(1, 1, '2026-01-01', 100, 1.0, 100.0)])
        conn = sqlite3.connect(str(db_file))
        try:
            raised = False
            try:
                conn.execute(
                    "INSERT INTO opening_stock (material_id, warehouse_id, date, quantity, price, amount) "
                    "VALUES (1,1,'2026-01-02',10,1.0,10.0)")
                conn.commit()
            except sqlite3.IntegrityError:
                raised = True
                conn.rollback()
            assert raised, "老库必须带 (material_id, warehouse_id) 唯一约束，否则测试无效"
        finally:
            conn.close()

    def test_t1_migration_is_idempotent(self, tmp_path):
        """连跑两次迁移不报错，且不重复建单/重复回填。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, '2026-01-01', 50, 0.5, 25.0),
        ])
        _run_migration(db_file, times=1)
        docs_first = _fetch(db_file, "SELECT COUNT(*) FROM opening_stock_doc")[0][0]
        _run_migration(db_file, times=1)
        docs_second = _fetch(db_file, "SELECT COUNT(*) FROM opening_stock_doc")[0][0]
        assert docs_first == docs_second == 1, "重复迁移不应新建单据"

    def test_t2_backfill_groups_by_date_and_warehouse(self, tmp_path):
        """按 (建账日期, 仓库) 分组：同日同仓一张单，同日异仓各一张。

        注意：老库带 (material_id, warehouse_id) 唯一约束，所以同一张单里
        必须用不同物料模拟"同仓多行"（这正是老库的真实形态）。
        2026-01-01 仓1 两行(物料1/物料2) → 1 张单；2026-01-01 仓2 一行 → 1 张单；
        2026-02-01 仓1 一行 → 1 张单。共 3 张。
        """
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, '2026-01-01', 50, 0.5, 25.0),
            (1, 2, '2026-01-01', 30, 1.0, 30.0),
            (2, 2, '2026-02-01', 70, 1.0, 70.0),
        ])
        _run_migration(db_file)

        docs = _fetch(db_file,
                      "SELECT date, warehouse_id FROM opening_stock_doc ORDER BY date, warehouse_id")
        assert len(docs) == 3, f"应归集为 3 张单，实际 {len(docs)}：{docs}"
        assert docs[0] == ('2026-01-01', 1)
        assert docs[1] == ('2026-01-01', 2)
        assert docs[2] == ('2026-02-01', 2)

        counts = _fetch(db_file, """
            SELECT d.date, COUNT(o.id) FROM opening_stock_doc d
            JOIN opening_stock o ON o.doc_id = d.id
            GROUP BY d.id ORDER BY d.date, d.warehouse_id
        """)
        assert [c[1] for c in counts] == [2, 1, 1], f"每单明细行数不对：{counts}"

    def test_t3_no_data_loss(self, tmp_path):
        """迁移前后行数与金额合计完全一致（只加归属不改账）。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, '2026-01-01', 50, 0.5, 25.0),
            (1, 2, '2026-02-01', 30, 1.0, 30.0),
        ])
        before = _fetch(db_file, "SELECT COUNT(*), SUM(quantity), SUM(amount) FROM opening_stock")[0]
        _run_migration(db_file)
        after = _fetch(db_file, "SELECT COUNT(*), SUM(quantity), SUM(amount) FROM opening_stock")[0]
        assert after == before, f"迁移不应改变账：{before} -> {after}"

    def test_t4_legacy_unique_constraint_removed(self, tmp_path):
        """迁移后同 (material_id, warehouse_id) 可插多行（跨单据唯一性已放开）。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [(1, 1, '2026-01-01', 100, 1.0, 100.0)])
        _run_migration(db_file)

        conn = sqlite3.connect(str(db_file))
        try:
            conn.execute(
                "INSERT INTO opening_stock_doc (doc_no, date, warehouse_id, status) "
                "VALUES ('QS26090002','2026-01-05',1,'active')")
            doc2 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                "INSERT INTO opening_stock (doc_id, material_id, warehouse_id, date, quantity, price, amount) "
                "VALUES (?,1,1,'2026-01-05',20,1.0,20.0)", (doc2,))
            conn.commit()
            cnt = conn.execute(
                "SELECT COUNT(*) FROM opening_stock WHERE material_id=1 AND warehouse_id=1").fetchone()[0]
            assert cnt == 2, "同物料同仓多张单应被允许"
        finally:
            conn.close()

    def test_t5_backup_table_kept_and_consistent(self, tmp_path):
        """检测到旧唯一约束时应先备份原表，且备份内容与迁移前一致。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, '2026-01-01', 50, 0.5, 25.0),
        ])
        _run_migration(db_file)

        tables = [r[0] for r in _fetch(db_file,
                                       "SELECT name FROM sqlite_master WHERE type='table'")]
        assert 'opening_stock_backup_mw001' in tables, "重建前必须有备份表"
        backup = _fetch(db_file,
                        "SELECT COUNT(*), SUM(quantity), SUM(amount) FROM opening_stock_backup_mw001")[0]
        assert backup == (2, 150.0, 125.0), f"备份表内容应与迁移前一致，实际 {backup}"

    def test_t6_doc_no_format_and_uniqueness(self, tmp_path):
        """历史单据单号形如 QS+YYMM+4位，同月多张单不撞号。"""
        db_file = tmp_path / 'legacy.db'
        # 同月三张单：按 (日期, 仓库) 各一张，物料需错开以避开老库唯一约束
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, '2026-01-02', 30, 1.0, 30.0),
            (1, 2, '2026-01-03', 20, 1.0, 20.0),
        ])
        _run_migration(db_file)

        doc_nos = [r[0] for r in _fetch(db_file,
                                        "SELECT doc_no FROM opening_stock_doc ORDER BY doc_no")]
        assert len(doc_nos) == 3, f"应生成 3 张单，实际 {doc_nos}"
        assert len(set(doc_nos)) == 3, f"单号不得重复：{doc_nos}"
        for no in doc_nos:
            assert no.startswith('QS2601'), f"单号应按分组月份编号：{no}"
            assert len(no) == 10 and no[-4:].isdigit(), f"单号格式应为 QS+YYMM+4位：{no}"

    def test_t7_doc_id_column_added_and_backfilled(self, tmp_path):
        """迁移后 opening_stock 应有 doc_id 列且历史行全部归单。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [(1, 1, '2026-01-01', 100, 1.0, 100.0)])
        _run_migration(db_file)
        cols = [r[1] for r in _fetch(db_file, "PRAGMA table_info(opening_stock)")]
        assert 'doc_id' in cols, f"缺 doc_id 列：{cols}"
        null_rows = _fetch(db_file,
                           "SELECT COUNT(*) FROM opening_stock WHERE doc_id IS NULL")[0][0]
        assert null_rows == 0, "有日期的历史行应全部归单"

    def test_t8_null_date_rows_not_grouped(self, tmp_path):
        """建账日期为空的历史行保守不归单（留 doc_id 为空），避免误合并。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 1, None, 10, 0.5, 5.0),
        ])
        _run_migration(db_file)
        null_rows = _fetch(db_file,
                           "SELECT COUNT(*) FROM opening_stock WHERE doc_id IS NULL")[0][0]
        assert null_rows == 1, "日期为空的行不应被强制归单"
        docs = _fetch(db_file, "SELECT COUNT(*) FROM opening_stock_doc")[0][0]
        assert docs == 1

    def test_t9_repeated_migration_stable(self, tmp_path):
        """连跑三次（模拟多次重启）：单据数、行数、账目均稳定。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [(1, 1, '2026-01-01', 100, 1.0, 100.0)])
        _run_migration(db_file, times=3)
        docs = _fetch(db_file, "SELECT COUNT(*) FROM opening_stock_doc")[0][0]
        assert docs == 1, f"三次迁移仍应只有 1 张单，实际 {docs}"
        totals = _fetch(db_file, "SELECT COUNT(*), SUM(quantity) FROM opening_stock")[0]
        assert totals == (1, 100.0)

    def test_t10_legacy_index_name_preserved_in_backup(self, tmp_path):
        """备份表行级内容与主表历史行逐行一致（防止重建时列错位）。"""
        db_file = tmp_path / 'legacy.db'
        _make_legacy_db(db_file, [
            (1, 1, '2026-01-01', 100, 1.0, 100.0),
            (2, 2, '2026-03-15', 7.5, 2.5, 18.75),
        ])
        _run_migration(db_file)
        backup = _fetch(db_file,
                        "SELECT material_id, warehouse_id, date, quantity, price, amount "
                        "FROM opening_stock_backup_mw001 ORDER BY id")
        assert backup == [(1, 1, '2026-01-01', 100.0, 1.0, 100.0),
                          (2, 2, '2026-03-15', 7.5, 2.5, 18.75)], f"备份逐行不一致：{backup}"
        main = _fetch(db_file,
                      "SELECT material_id, warehouse_id, date, quantity, price, amount "
                      "FROM opening_stock ORDER BY id")
        assert main == backup, "重建后主表数据必须与备份逐行一致"
