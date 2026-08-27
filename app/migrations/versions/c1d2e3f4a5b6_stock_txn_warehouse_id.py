"""stock transaction warehouse id

Revision ID: c1d2e3f4a5b6
Revises: 9a2b3c4d5e6f
Create Date: 2026-08-27

BUG-2026-08-27-004 治本 B1：stock_transaction 增加仓库外键列 warehouse_id。

背景：StockTransaction.location 历史上同时承载仓库名/编码、库位名、空值
三类语义，全部仓库级报表（台账/月报/库存查询）只能靠字符串匹配重建仓库
归属，口径逻辑被复制成多份、修复漏改一处，反复出 BUG（220 个历史 BUG 中
102 个为库存/仓库/台账类）。

本迁移（与 8b17c4d90a2e 的 location_inventory 回填同一规则）：
- 增加 warehouse_id 列 + 外键 + 索引 idx_stock_txn_warehouse_id；
- 简单回填：location 唯一匹配 warehouse name/code 时填入，无法唯一确定
  保留 NULL（AGENTS.md：不自动归入任意默认仓库）；
- 复杂归属（库位名 → LocationInventory.warehouse_id、空 location →
  来源单据仓库推断、调拨按数量正负归 to/from）由启动幂等函数
  backfill_stock_txn_warehouse_id()（app.py）处理，跨迁移通道统一收口。

SQLite 部署不走本迁移（auto_migrate_database 已补列+索引）；本迁移面向
MySQL/PG（flask db upgrade）。
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = '9a2b3c4d5e6f'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = []
    try:
        existing_indexes = [
            idx.get('name') for idx in inspector.get_indexes('stock_transaction')
        ]
    except Exception:
        pass

    with op.batch_alter_table('stock_transaction') as batch_op:
        batch_op.add_column(sa.Column('warehouse_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_stock_txn_warehouse_id',
            'warehouse',
            ['warehouse_id'],
            ['id'],
        )
        if 'idx_stock_txn_warehouse_id' not in existing_indexes:
            batch_op.create_index(
                'idx_stock_txn_warehouse_id',
                ['warehouse_id'],
                unique=False,
            )

    # 简单回填：location 唯一匹配 warehouse name/code 才填（与
    # 8b17c4d90a2e 的 location_inventory 回填规则一致，不猜）。
    op.execute(
        sa.text(
            """
            UPDATE stock_transaction
            SET warehouse_id = (
                SELECT warehouse.id
                FROM warehouse
                WHERE warehouse.name = TRIM(stock_transaction.location)
                   OR warehouse.code = TRIM(stock_transaction.location)
            )
            WHERE warehouse_id IS NULL
              AND TRIM(COALESCE(stock_transaction.location, '')) <> ''
              AND 1 = (
                  SELECT COUNT(*)
                  FROM warehouse
                  WHERE warehouse.name = TRIM(stock_transaction.location)
                     OR warehouse.code = TRIM(stock_transaction.location)
              )
            """
        )
    )


def downgrade():
    with op.batch_alter_table('stock_transaction') as batch_op:
        batch_op.drop_index('idx_stock_txn_warehouse_id')
        batch_op.drop_constraint('fk_stock_txn_warehouse_id', type_='foreignkey')
        batch_op.drop_column('warehouse_id')
