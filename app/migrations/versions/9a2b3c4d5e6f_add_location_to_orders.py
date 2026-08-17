"""add location and auto_push_requisition to orders

Revision ID: 9a2b3c4d5e6f
Revises: 8b17c4d90a2e
Create Date: 2026-08-17

添加入库单和出库单的库位字段和自动推送领料申请字段。
"""
from alembic import op
import sqlalchemy as sa


revision = '9a2b3c4d5e6f'
down_revision = '8b17c4d90a2e'
branch_labels = None
depends_on = None


def upgrade():
    # in_order 表添加 location 和 auto_push_requisition 列
    with op.batch_alter_table('in_order') as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('auto_push_requisition', sa.Boolean(), nullable=True))

    # 回填默认值
    op.execute("UPDATE in_order SET location = '' WHERE location IS NULL")
    op.execute("UPDATE in_order SET auto_push_requisition = 0 WHERE auto_push_requisition IS NULL")

    # 设置 NOT NULL 约束
    with op.batch_alter_table('in_order') as batch_op:
        batch_op.alter_column('location', nullable=False, server_default='')
        batch_op.alter_column('auto_push_requisition', nullable=False, server_default=sa.text('0'))

    # out_order 表添加 location 列
    with op.batch_alter_table('out_order') as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=100), nullable=True))

    # 回填默认值
    op.execute("UPDATE out_order SET location = '' WHERE location IS NULL")

    # 设置 NOT NULL 约束
    with op.batch_alter_table('out_order') as batch_op:
        batch_op.alter_column('location', nullable=False, server_default='')


def downgrade():
    with op.batch_alter_table('out_order') as batch_op:
        batch_op.drop_column('location')

    with op.batch_alter_table('in_order') as batch_op:
        batch_op.drop_column('auto_push_requisition')
        batch_op.drop_column('location')
