"""add phone number for user column

Revision ID: f40aaa9d9c3d
Revises: 
Create Date: 2026-09-24 19:07:28.715396

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f40aaa9d9c3d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone_number', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    pass
