"""Run once with: python migrations/add_todos_owner_id.py. Safe to rerun."""
from datetime import datetime, timezone
from pathlib import Path
import sqlite3


def migrate(database_path):
    database_path = Path(database_path).resolve()
    with sqlite3.connect(f'{database_path.as_uri()}?mode=rw', uri=True) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(todos)')}
        if not columns:
            raise RuntimeError('The todos table does not exist in this database.')
        if 'owner_id' in columns:
            return None
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup = database_path.with_name(f'{database_path.name}.before-owner-id-{timestamp}.bak')
        with sqlite3.connect(backup) as destination:
            connection.backup(destination)
        connection.execute('ALTER TABLE todos ADD COLUMN owner_id INTEGER REFERENCES users(id)')
        return backup


if __name__ == '__main__':
    backup = migrate(Path(__file__).resolve().parents[1] / 'todosapp.db')
    print(f'Migration complete. Backup: {backup}' if backup else 'owner_id already exists; no changes.')
