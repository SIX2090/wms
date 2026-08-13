"""location inventory warehouse compatibility

Revision ID: 8b17c4d90a2e
Revises: 279ebeb0381a
Create Date: 2026-08-13

INV-AUDIT-002 修复：
- 增加 warehouse_id 列、外键、索引（已有逻辑，保留）。
- 关键新增：重建唯一约束，从 (material_id, location) -> uix_material_location
  改为 (material_id, warehouse_id, location) -> uix_material_warehouse_location。
  否则旧库即使增加了 warehouse_id 列，仍会因为旧唯一约束阻止
  “同物料在不同仓库的同名库位”分别建账，跨仓合并 BUG 无法修复。
- 数据回填保持原有逻辑：仅当 location 字符串能唯一匹配到 warehouse
  name/code 时才回填 warehouse_id，无法确定的行保留 NULL
  （AGENTS.md：不自动归入任意默认仓库）。

注意：alembic batch_alter_table 在 SQLite 下会重建表，可安全 drop/create
唯一约束；MySQL/PG 下走原生 ALTER TABLE 语句。
"""
from alembic import op
import sqlalchemy as sa


revision = '8b17c4d90a2e'
down_revision = '279ebeb0381a'
branch_labels = None
depends_on = None


def upgrade():
    # 1) 重建表结构：增加 warehouse_id 列、外键、索引，并替换唯一约束。
    #    旧约束 uix_material_location (material_id, location) 必须先 drop，
    #    否则不同仓库同名库位的写入仍会被旧约束拦截。
    #    注意：batch_alter_table 在 SQLite 下会重建表，可安全 drop/create
    #    唯一约束；MySQL/PG 下走原生 ALTER TABLE 语句。
    #    先检查旧约束是否存在，避免 drop_constraint 在 batch 模式下抛
    #    ValueError（batch 模式下 drop_constraint 是延迟执行的，try/except
    #    无法捕获）。
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_unique_constraints = []
    try:
        existing_unique_constraints = inspector.get_unique_constraints('location_inventory')
    except Exception:
        pass
    existing_unique_names = {c.get('name') for c in existing_unique_constraints if c.get('name')}
    # 同时检查是否已有新约束（部分迁移过的情况）
    has_new_constraint = 'uix_material_warehouse_location' in existing_unique_names

    with op.batch_alter_table('location_inventory') as batch_op:
        batch_op.add_column(sa.Column('warehouse_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_location_inventory_warehouse_id',
            'warehouse',
            ['warehouse_id'],
            ['id'],
        )
        batch_op.create_index(
            'idx_location_inventory_warehouse',
            ['warehouse_id'],
            unique=False,
        )
        # 仅当旧约束确实存在时才 drop（按名匹配）。
        if 'uix_material_location' in existing_unique_names:
            batch_op.drop_constraint('uix_material_location', type_='unique')
        if not has_new_constraint:
            batch_op.create_unique_constraint(
                'uix_material_warehouse_location',
                ['material_id', 'warehouse_id', 'location'],
            )

    # 2) 回填 warehouse_id（必须在 add_column 之后）。
    #    仅当 location 字符串能唯一匹配到 warehouse name/code 时才回填，
    #    无法确定的行保留 NULL（AGENTS.md：不自动归入任意默认仓库）。
    op.execute(
        sa.text(
            """
            UPDATE location_inventory
            SET warehouse_id = (
                SELECT warehouse.id
                FROM warehouse
                WHERE warehouse.name = TRIM(location_inventory.location)
                   OR warehouse.code = TRIM(location_inventory.location)
            )
            WHERE warehouse_id IS NULL
              AND TRIM(COALESCE(location_inventory.location, '')) <> ''
              AND 1 = (
                  SELECT COUNT(*)
                  FROM warehouse
                  WHERE warehouse.name = TRIM(location_inventory.location)
                     OR warehouse.code = TRIM(location_inventory.location)
              )
            """
        )
    )


def downgrade():
    with op.batch_alter_table('location_inventory') as batch_op:
        try:
            batch_op.drop_constraint('uix_material_warehouse_location', type_='unique')
        except Exception:
            pass
        batch_op.create_unique_constraint(
            'uix_material_location',
            ['material_id', 'location'],
        )
        batch_op.drop_index('idx_location_inventory_warehouse')
        batch_op.drop_constraint('fk_location_inventory_warehouse_id', type_='foreignkey')
        batch_op.drop_column('warehouse_id')
