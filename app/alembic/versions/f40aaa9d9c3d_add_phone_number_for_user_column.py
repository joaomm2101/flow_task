"""add phone number for user column

Revision ID: f40aaa9d9c3d
Revises: c9d2e4f6a801
Create Date: 2026-09-24 19:07:28.715396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f40aaa9d9c3d'
down_revision: Union[str, Sequence[str], None] = 'c9d2e4f6a801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'phone_number' not in columns:  # databases built from the models already have it
        op.add_column('users', sa.Column('phone_number', sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users') as batch:
        batch.drop_column('phone_number')
