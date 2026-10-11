import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base





def normalize_database_url(url: str) -> str:
    """Pin the PostgreSQL driver we ship.

    A bare ``postgresql://`` URL means psycopg2 on older SQLAlchemy releases but psycopg 3 on newer
    ones. The image only contains psycopg2 (psycopg2-binary), so make that explicit instead of
    depending on the SQLAlchemy version.
    """
    parsed = make_url(url)
    if parsed.drivername == 'postgresql':
        parsed = parsed.set(drivername='postgresql+psycopg2')
    return parsed.render_as_string(hide_password=False)


try:
    SQLALCHEMY_DATABASE_URL = os.environ['DATABASE_URL']
except KeyError:
    raise RuntimeError('DATABASE_URL is not set. See .env.example.') from None

engine  = create_engine(normalize_database_url(SQLALCHEMY_DATABASE_URL))

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

