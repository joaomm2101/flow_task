"""unique username and email

Databases created before the models declared unique=True (or by an older
create_all) have no UNIQUE constraint on users.username / users.email, so the
same name could register twice. This adds them, but refuses to run (without
touching any data) while duplicates exist.

Revision ID: a3c1d7e9b2f4
Revises: f40aaa9d9c3d
Create Date: 2026-10-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c1d7e9b2f4'
down_revision: Union[str, Sequence[str], None] = 'f40aaa9d9c3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = ('username', 'email')


def _already_unique(inspector, column: str) -> bool:
    constraints = inspector.get_unique_constraints('users')
    if any(c['column_names'] == [column] for c in constraints):
        return True
    return any(i['unique'] and i['column_names'] == [column] for i in inspector.get_indexes('users'))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for column in COLUMNS:
        if _already_unique(inspector, column):
            continue
        # `column` comes from the constant COLUMNS tuple above, never from user input
        duplicates = bind.execute(sa.text(
            f'SELECT {column}, COUNT(*) FROM users WHERE {column} IS NOT NULL '  # noqa: S608
            f'GROUP BY {column} HAVING COUNT(*) > 1'
        )).fetchall()
        if duplicates:
            values = ', '.join(f'{row[0]!r} (x{row[1]})' for row in duplicates)
            raise RuntimeError(
                f'Cannot add UNIQUE({column}): duplicate values exist in users: {values}. '
                'Merge or rename these accounts, then run the migration again.'
            )
        with op.batch_alter_table('users') as batch:  # batch mode: SQLite can't ALTER ... ADD CONSTRAINT
            batch.create_unique_constraint(f'uq_users_{column}', [column])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing = {c['name'] for c in inspector.get_unique_constraints('users')}
    for column in COLUMNS:
        if f'uq_users_{column}' in existing:
            with op.batch_alter_table('users') as batch:
                batch.drop_constraint(f'uq_users_{column}', type_='unique')
