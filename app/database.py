from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base



DATABASE_PATH = Path(__file__).resolve().parent / 'todosapp.db'
SQLALCHEMY_DATABASE_URL = 'postgresql://postgres:210256@localhost/TodoApplicationDatabase'

engine  = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

