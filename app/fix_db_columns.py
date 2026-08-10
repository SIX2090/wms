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

    conn.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    fix_columns()
