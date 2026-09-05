# -*- coding: utf-8 -*-
"""自动修复数据库：添加缺失的 picker 列 + 创建缺失的新表。

启动脚本调用，确保数据库字段与代码同步。
"""
import sqlite3
import os
import logging

logger = logging.getLogger(__name__)


def _ensure_material_image_table(conn):
    """创建 material_image 表（移动端物料档案多图）。

    WMS_NO_DB_TOUCH=1 场景下启动时 db.create_all() 被跳过，导致
    MaterialImage 模型对应的表未创建，移动端 _archive_material_payload
    查询时会报 no such table: material_image。
    表结构必须与 app/app.py 中 class MaterialImage(db.Model) 完全一致。
    """
    mi_cols = [r[1] for r in conn.execute('PRAGMA table_info(material_image)').fetchall()]
    if mi_cols:
        logger.info('material_image 表已存在')
        return
    conn.execute(
        '''
        CREATE TABLE material_image (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id INTEGER NOT NULL,
            image VARCHAR(200) NOT NULL,
            sort_order INTEGER DEFAULT 0,
            created_at DATETIME,
            FOREIGN KEY (material_id) REFERENCES material(id)
        )
        '''
    )
    conn.execute(
        'CREATE INDEX idx_material_image_material ON material_image(material_id)'
    )
    conn.commit()
    logger.info('已创建 material_image 表')


def _table_exists(conn, table):
    """返回表是否存在（全新空库时表尚未由 db.create_all 创建，跳过 ALTER）。"""
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


# BUG-2026-09-05-001：盘点域迁移列（INV-BATCH-001-A / 002）此前只由
# app.py auto_migrate_database() 补列，而 start_wms_*.bat 默认 WMS_NO_DB_TOUCH=1
# 会整体跳过它——存量库重启也补不上，物料编辑报 no such column:
# inventory_check_item.counted_by。app.py 的 ensure_inventory_check_columns()
# 已独立于开关启动期自愈；本脚本是 bat 启动时强制先跑的兜底层，一并补上
# （双保险：即使换启动方式绕过 ensure 系列，这里也会补）。
# 表名/列名均为固定白名单标识符（非用户输入），无注入风险。
# 结构 (表名, PRAGMA 语句, ((列名, ALTER 语句), ...))，ALTER 片段必须与
# app.py ensure_inventory_check_columns() 逐字一致（tests 断言防漂移）。
_INVENTORY_CHECK_MIGRATIONS = (
    ('inventory_check', 'PRAGMA table_info(inventory_check)', (
        ('frozen_at',
         'ALTER TABLE inventory_check ADD COLUMN frozen_at DATETIME'),
    )),
    ('inventory_check_item', 'PRAGMA table_info(inventory_check_item)', (
        ('counted_by',
         'ALTER TABLE inventory_check_item ADD COLUMN counted_by INTEGER'),
        ('counted_at',
         'ALTER TABLE inventory_check_item ADD COLUMN counted_at DATETIME'),
        ('area',
         "ALTER TABLE inventory_check_item ADD COLUMN area VARCHAR(100) DEFAULT ''"),
    )),
    ('inventory_check_scan', 'PRAGMA table_info(inventory_check_scan)', (
        ('check_id',
         'ALTER TABLE inventory_check_scan ADD COLUMN check_id INTEGER'),
    )),
    ('inventory_check_scan_item', 'PRAGMA table_info(inventory_check_scan_item)', (
        ('area',
         "ALTER TABLE inventory_check_scan_item ADD COLUMN area VARCHAR(100) DEFAULT ''"),
    )),
)


def _ensure_inventory_check_columns(conn):
    """补齐盘点域迁移列（BUG-2026-09-05-001，与 app.py ensure_inventory_check_columns 对齐）。

    幂等：PRAGMA 判断列已存在则不 ALTER。只 ADD 可空列，不动存量数据。
    表不存在（全新空库）跳过，交给启动期 db.create_all() 建全量列。
    """
    for tbl, pragma_stmt, col_stmts in _INVENTORY_CHECK_MIGRATIONS:
        if not _table_exists(conn, tbl):
            continue
        cols = [r[1] for r in conn.execute(pragma_stmt).fetchall()]
        for col, alter_stmt in col_stmts:
            if col in cols:
                logger.info('%s.%s 已存在', tbl, col)
                continue
            conn.execute(alter_stmt)
            conn.commit()
            logger.info('已添加 %s.%s', tbl, col)


def fix_columns(db_path=None):
    """修复数据库缺失字段。

    Args:
        db_path: 数据库路径，默认使用 app/instance/inventory.db
    """
    if db_path is None:
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'inventory.db')
    if not os.path.exists(db_path):
        logger.warning('数据库不存在: %s', db_path)
        return

    conn = sqlite3.connect(db_path)

    # 修复 out_order 表
    cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
    if 'picker' not in cols:
        conn.execute('ALTER TABLE out_order ADD COLUMN picker VARCHAR(50)')
        conn.commit()
        logger.info('已添加 out_order.picker')
    else:
        logger.info('out_order.picker 已存在')

    # BUG-2026-08-17-001: WMS_NO_DB_TOUCH=1 时 app.auto_migrate_database 被跳过，
    # 而本脚本（启动时强制运行）缺少 location 补列，导致旧库 in_order/out_order
    # 永远缺 location 列，首页 index() 查询报 no such column: in_order.location。
    # 与 app/app.py auto_migrate_database() 的 ALTER 语句保持一致。
    if _table_exists(conn, 'in_order'):
        in_cols = [r[1] for r in conn.execute('PRAGMA table_info(in_order)').fetchall()]
        if 'location' not in in_cols:
            conn.execute("ALTER TABLE in_order ADD COLUMN location VARCHAR(100) NOT NULL DEFAULT ''")
            conn.commit()
            logger.info('已添加 in_order.location')
        else:
            logger.info('in_order.location 已存在')
        if 'auto_push_requisition' not in in_cols:
            conn.execute('ALTER TABLE in_order ADD COLUMN auto_push_requisition BOOLEAN NOT NULL DEFAULT 0')
            conn.commit()
            logger.info('已添加 in_order.auto_push_requisition')
        else:
            logger.info('in_order.auto_push_requisition 已存在')

    if _table_exists(conn, 'out_order'):
        out_cols = [r[1] for r in conn.execute('PRAGMA table_info(out_order)').fetchall()]
        if 'location' not in out_cols:
            conn.execute("ALTER TABLE out_order ADD COLUMN location VARCHAR(100) NOT NULL DEFAULT ''")
            conn.commit()
            logger.info('已添加 out_order.location')
        else:
            logger.info('out_order.location 已存在')

    # 修复 production_requisition 表
    pr_cols = [r[1] for r in conn.execute('PRAGMA table_info(production_requisition)').fetchall()]
    if 'picker' not in pr_cols:
        conn.execute('ALTER TABLE production_requisition ADD COLUMN picker VARCHAR(50)')
        conn.commit()
        logger.info('已添加 production_requisition.picker')
    else:
        logger.info('production_requisition.picker 已存在')

    # BUG-2026-08-08-001：领料单缺 warehouse 列，存量数据回填默认仓库名
    if 'warehouse' not in pr_cols:
        conn.execute('ALTER TABLE production_requisition ADD COLUMN warehouse VARCHAR(100)')
        try:
            row = conn.execute(
                "SELECT name FROM warehouse WHERE is_default = 1 AND status = 'active' LIMIT 1"
            ).fetchone()
            if row:
                conn.execute(
                    "UPDATE production_requisition SET warehouse = ? "
                    "WHERE warehouse IS NULL OR warehouse = ''",
                    (row[0],),
                )
        except Exception:
            conn.rollback()
        conn.commit()
        logger.info('已添加 production_requisition.warehouse')
    else:
        logger.info('production_requisition.warehouse 已存在')

    # material_image 表（WMS_NO_DB_TOUCH=1 场景下手动建表，避免 no such table）
    _ensure_material_image_table(conn)

    # BUG-2026-09-05-001：盘点域补列（bat 强制先跑的兜底层，双保险）
    _ensure_inventory_check_columns(conn)

    conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    fix_columns()
