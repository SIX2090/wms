"""add in_order_item batch_no and expiry_date

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-09-19

P0 批次/有效期捕获：入库明细行级批次号与有效期列。
只加可空列、不动存量数据、不参与库存维度计算（库存批次维度化另行任务）。
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('in_order_item') as batch_op:
        batch_op.add_column(sa.Column('batch_no', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('expiry_date', sa.Date(), nullable=True))


def downgrade():
    with op.batch_alter_table('in_order_item') as batch_op:
        batch_op.drop_column('expiry_date')
        batch_op.drop_column('batch_no')
