"""create users and todos tables

Baseline so a brand-new database can be built with `alembic upgrade head`
alone (the schema used to come from Base.metadata.create_all at import time).
Databases that already have these tables, whether created by create_all or
by hand, are left untouched.

Revision ID: c9d2e4f6a801
Revises:
Create Date: 2026-10-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d2e4f6a801'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if 'users' not in existing:
        # phone_number and the UNIQUE constraints arrive in the next two revisions
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('email', sa.String()),
            sa.Column('username', sa.String()),
            sa.Column('first_name', sa.String()),
            sa.Column('last_name', sa.String()),
            sa.Column('hashed_password', sa.String()),
            sa.Column('is_active', sa.Boolean()),
            sa.Column('role', sa.String()),
        )
        op.create_index('ix_users_id', 'users', ['id'])

    if 'todos' not in existing:
        op.create_table(
            'todos',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('title', sa.String()),
            sa.Column('description', sa.String()),
            sa.Column('priority', sa.Integer()),
            sa.Column('complete', sa.Boolean()),
            sa.Column('owner_id', sa.Integer(), sa.ForeignKey('users.id')),
        )
        op.create_index('ix_todos_id', 'todos', ['id'])


def downgrade() -> None:
    op.drop_table('todos')
    op.drop_table('users')
