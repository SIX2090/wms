# -*- coding: utf-8 -*-
"""INV-BATCH-001-A 回归：盘点批次化模型层（冻结快照与行级归属字段）。

背景（Phase 2 盘点批次化）：多人手机扫码盘点需要"批次"承载——冻结
快照、行级归属、扫码挂钩。此前模型层完全没有这些字段：
- PC 盘点单（InventoryCheck）无冻结时点，save_check_table 每次保存
  都把明细 system_stock 刷新为当前账面，多人轮流保存时差异基准漂移；
- 盘点明细（InventoryCheckItem）无盘点人/盘点时间，多人协作无法判责；
- 扫码盘点单（InventoryCheckScan）无批次挂钩，多人各扫各的、互不知晓。

P2-A 范围（纯模型层 + 迁移，不改行为）：
- InventoryCheck.frozen_at：批次账面冻结时点；
- InventoryCheckItem.counted_by / counted_at：行级盘点归属；
- InventoryCheckScan.check_id：扫码盘点单挂钩批次。

覆盖：
T1. 三张表新列存在（create_all 口径，PRAGMA 检查）
T2. auto_migrate_database 给缺列老库补列，二次执行幂等
T3. 兼容：不带新字段建单/明细/扫码盘点单行为不变
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

_ctx = app_module.app.app_context()
_ctx.push()


def _reset_db():
    db.drop_all()
    db.create_all()


def _table_columns(table):
    rows = db.session.execute(db.text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def test_t1_new_columns_exist():
    """T1: 批次化字段必须存在于三张表（模型 create_all 口径）。"""
    _reset_db()
    assert "frozen_at" in _table_columns("inventory_check"), (
        "inventory_check 缺 frozen_at（批次账面冻结时点）"
    )
    item_cols = _table_columns("inventory_check_item")
    assert "counted_by" in item_cols, (
        "inventory_check_item 缺 counted_by（行级盘点人）"
    )
    assert "counted_at" in item_cols, (
        "inventory_check_item 缺 counted_at（行级盘点时间）"
    )
    assert "check_id" in _table_columns("inventory_check_scan"), (
        "inventory_check_scan 缺 check_id（扫码盘点单挂钩批次）"
    )


def test_t2_auto_migrate_backfills_legacy_db(tmp_path):
    """T2: auto_migrate_database 给缺列老库补列，二次执行幂等。"""
    import sqlite3
    from sqlalchemy import create_engine
    db_file = tmp_path / "legacy.db"
    # 用模型元数据建完整 schema 的新库，再把三张盘点表重建为"老 schema"
    # （重命名→建无新列版本→拷数据→删旧表）模拟老库。不用 DROP COLUMN：
    # counted_by 带 FK 引用，SQLite 拒绝删除被外键约束引用的列。
    engine = create_engine(f"sqlite:///{db_file}")
    db.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(str(db_file))
    conn.execute("ALTER TABLE inventory_check RENAME TO inventory_check_old")
    conn.execute("""CREATE TABLE inventory_check (
        id INTEGER PRIMARY KEY, check_no VARCHAR(50) NOT NULL,
        date DATE, warehouse VARCHAR(100) NOT NULL DEFAULT '',
        remark VARCHAR(200), status VARCHAR(20), operator_id INTEGER,
        created_at DATETIME)""")
    conn.execute("""INSERT INTO inventory_check
        SELECT id, check_no, date, warehouse, remark, status, operator_id, created_at
        FROM inventory_check_old""")
    conn.execute("DROP TABLE inventory_check_old")
    conn.execute("ALTER TABLE inventory_check_item RENAME TO inventory_check_item_old")
    conn.execute("""CREATE TABLE inventory_check_item (
        id INTEGER PRIMARY KEY, inventory_check_id INTEGER NOT NULL,
        material_id INTEGER NOT NULL, system_stock FLOAT NOT NULL,
        actual_stock FLOAT NOT NULL, difference FLOAT NOT NULL,
        reason VARCHAR(200))""")
    conn.execute("""INSERT INTO inventory_check_item
        SELECT id, inventory_check_id, material_id, system_stock, actual_stock, difference, reason
        FROM inventory_check_item_old""")
    conn.execute("DROP TABLE inventory_check_item_old")
    conn.execute("ALTER TABLE inventory_check_scan RENAME TO inventory_check_scan_old")
    conn.execute("""CREATE TABLE inventory_check_scan (
        id INTEGER PRIMARY KEY, check_no VARCHAR(50) NOT NULL,
        date DATE, warehouse VARCHAR(100) NOT NULL DEFAULT '',
        remark VARCHAR(200), status VARCHAR(20), operator_id INTEGER,
        created_at DATETIME)""")
    conn.execute("""INSERT INTO inventory_check_scan
        SELECT id, check_no, date, warehouse, remark, status, operator_id, created_at
        FROM inventory_check_scan_old""")
    conn.execute("DROP TABLE inventory_check_scan_old")
    conn.commit()
    conn.close()

    orig = app_module._resolve_sqlite_db_path
    app_module._resolve_sqlite_db_path = lambda *a, **kw: str(db_file)
    try:
        app_module.auto_migrate_database()
        app_module.auto_migrate_database()  # 二次执行必须幂等不炸
    finally:
        app_module._resolve_sqlite_db_path = orig

    conn = sqlite3.connect(str(db_file))
    check_cols = {r[1] for r in conn.execute("PRAGMA table_info(inventory_check)")}
    item_cols = {r[1] for r in conn.execute("PRAGMA table_info(inventory_check_item)")}
    scan_cols = {r[1] for r in conn.execute("PRAGMA table_info(inventory_check_scan)")}
    conn.close()
    assert "frozen_at" in check_cols, "迁移未补 inventory_check.frozen_at"
    assert "counted_by" in item_cols, "迁移未补 inventory_check_item.counted_by"
    assert "counted_at" in item_cols, "迁移未补 inventory_check_item.counted_at"
    assert "check_id" in scan_cols, "迁移未补 inventory_check_scan.check_id"


def test_t3_legacy_creation_still_works():
    """T3: 兼容——不带新字段建单/明细/扫码盘点单均正常，新字段默认空。"""
    from app import (InventoryCheck, InventoryCheckItem, InventoryCheckScan,
                     Material)
    _reset_db()
    m = Material(code="M001", name="物料M001", stock=10.0)
    db.session.add(m)
    check = InventoryCheck(check_no="CK-T3", warehouse="A仓", status="pending")
    db.session.add(check)
    db.session.flush()
    db.session.add(InventoryCheckItem(
        inventory_check_id=check.id, material_id=m.id,
        system_stock=10.0, actual_stock=9.0, difference=-1.0))
    scan = InventoryCheckScan(check_no="CS-T3", warehouse="A仓", status="completed")
    db.session.add(scan)
    db.session.commit()

    saved_check = InventoryCheck.query.filter_by(check_no="CK-T3").one()
    assert saved_check.frozen_at is None, "未冻结的盘点单 frozen_at 应为空"
    saved_item = saved_check.items[0]
    assert saved_item.counted_by is None and saved_item.counted_at is None
    saved_scan = InventoryCheckScan.query.filter_by(check_no="CS-T3").one()
    assert saved_scan.check_id is None, "未挂批次的扫码盘点单 check_id 应为空"
