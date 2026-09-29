"""Collaborative operators and settings

Revision ID: b123456789ab
Revises: 601a5965ece6
Create Date: 2026-09-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b123456789ab'
down_revision: Union[str, Sequence[str], None] = '601a5965ece6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=True, server_default='operator'),
        sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # 2. Create app_settings table
    op.create_table('app_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(length=50), nullable=True, server_default='network'),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=255), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_app_settings_id'), 'app_settings', ['id'], unique=False)
    op.create_index(op.f('ix_app_settings_key'), 'app_settings', ['key'], unique=True)

    # 3. Create operator_sessions table
    op.create_table('operator_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('operator_id', sa.Integer(), nullable=False),
        sa.Column('applied_qty', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='running'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['operator_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operator_sessions_id'), 'operator_sessions', ['id'], unique=False)

    # 4. Refactor tasks table
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('operator_name')
        batch_op.drop_column('quantity_completed')
        batch_op.drop_column('remaining_stickers')
        batch_op.drop_column('started_at')
        batch_op.drop_column('finished_at')
        batch_op.drop_column('is_locked')
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('tasks') as batch_op:
        batch_op.drop_column('created_at')
        batch_op.add_column(sa.Column('is_locked', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('finished_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('remaining_stickers', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('quantity_completed', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('operator_name', sa.String(length=100), nullable=True))

    op.drop_index(op.f('ix_operator_sessions_id'), table_name='operator_sessions')
    op.drop_table('operator_sessions')
    op.drop_index(op.f('ix_app_settings_key'), table_name='app_settings')
    op.drop_index(op.f('ix_app_settings_id'), table_name='app_settings')
    op.drop_table('app_settings')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_table('users')
