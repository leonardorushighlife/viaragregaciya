"""Partial labeling and defect tracking

Revision ID: c345678901cd
Revises: b123456789ab
Create Date: 2026-09-29 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c345678901cd'
down_revision: Union[str, Sequence[str], None] = 'b123456789ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update orders table
    with op.batch_alter_table('orders') as batch_op:
        batch_op.add_column(sa.Column('defect_qty', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('actual_labeling_date', sa.Date(), nullable=True))

    # 2. Update tasks table
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.add_column(sa.Column('actual_started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('actual_completed_at', sa.DateTime(), nullable=True))

    # 3. Update operator_sessions table
    with op.batch_alter_table('operator_sessions') as batch_op:
        batch_op.add_column(sa.Column('paused_at', sa.DateTime(), nullable=True))

    # 4. Data migration for existing sessions
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE operator_sessions
        SET status = 'completed',
            paused_at = finished_at
        WHERE finished_at IS NOT NULL
    """))


def downgrade() -> None:
    with op.batch_alter_table('operator_sessions') as batch_op:
        batch_op.drop_column('paused_at')

    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('actual_completed_at')
        batch_op.drop_column('actual_started_at')

    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('actual_labeling_date')
        batch_op.drop_column('defect_qty')
