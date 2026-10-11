"""The Alembic chain is the only thing that builds the schema, so test it end to end."""
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from ..database import Base
from .. import models  # noqa: F401  (registers the tables on Base.metadata)

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@pytest.fixture
def db_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    monkeypatch.setenv("DATABASE_URL", url)  # alembic/env.py reads it
    return url


def alembic_config():
    return Config(str(ALEMBIC_INI))


def test_empty_database_is_built_by_migrations_alone(db_url):
    command.upgrade(alembic_config(), "head")

    inspector = sa.inspect(sa.create_engine(db_url))
    assert {"users", "todos", "alembic_version"} <= set(inspector.get_table_names())
    assert {c["name"] for c in inspector.get_columns("users")} >= {"username", "email", "phone_number"}
    unique = {tuple(c["column_names"]) for c in inspector.get_unique_constraints("users")}
    assert {("username",), ("email",)} <= unique


def test_migrated_schema_matches_the_models(db_url):
    command.upgrade(alembic_config(), "head")

    with sa.create_engine(db_url).connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert diff == [], f"models and migrations drifted apart: {diff}"


def test_legacy_database_created_by_create_all_upgrades_without_errors(db_url):
    engine = sa.create_engine(db_url)
    Base.metadata.create_all(bind=engine)  # what the app used to do on import
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO users (username, email) VALUES ('keep', 'keep@x.com')"))

    command.upgrade(alembic_config(), "head")

    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT username FROM users")).scalars().all() == ["keep"]


def test_migrations_can_be_rolled_back_to_empty(db_url):
    command.upgrade(alembic_config(), "head")
    command.downgrade(alembic_config(), "base")

    names = set(sa.inspect(sa.create_engine(db_url)).get_table_names())
    assert "users" not in names and "todos" not in names


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgresql://u:p@db:5432/flowtask", "postgresql+psycopg2://u:p@db:5432/flowtask"),
        ("postgresql+psycopg2://u:p@db/x", "postgresql+psycopg2://u:p@db/x"),
        ("postgresql+psycopg://u:p@db/x", "postgresql+psycopg://u:p@db/x"),  # explicit choice is respected
        ("sqlite:///./test.db", "sqlite:///./test.db"),
        ("postgresql://u:p%40ss%2Fword@db/x", "postgresql+psycopg2://u:p%40ss%2Fword@db/x"),  # special chars kept
    ],
)
def test_postgres_driver_is_explicit_but_never_overrides_a_choice(given, expected):
    from ..database import normalize_database_url

    assert normalize_database_url(given) == expected
