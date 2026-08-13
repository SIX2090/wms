"""location inventory warehouse compatibility

Revision ID: 8b17c4d90a2e
Revises: 279ebeb0381a
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa


revision = '8b17c4d90a2e'
down_revision = '279ebeb0381a'
branch_labels = None
depends_on = None


def upgrade():
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
        batch_op.drop_index('idx_location_inventory_warehouse')
        batch_op.drop_constraint('fk_location_inventory_warehouse_id', type_='foreignkey')
        batch_op.drop_column('warehouse_id')
