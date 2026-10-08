import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base



DATABASE_PATH = Path(__file__).resolve().parent / 'todosapp.db'
try:
    SQLALCHEMY_DATABASE_URL = os.environ['DATABASE_URL']
except KeyError:
    raise RuntimeError('DATABASE_URL is not set. See .env.example.') from None

engine  = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

