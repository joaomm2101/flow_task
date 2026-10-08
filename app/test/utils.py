import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ..database import Base
from ..main import app
from ..models import Todos

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"


engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def override_get_current_user():
    return {"username": "testuser", "id": 1, "role": "admin"}


client = TestClient(app)



@pytest.fixture
def test_todo():
    todo = Todos(
        title="Learn to code",
        description="need to learn",
        priority=5,
        complete=False,
        owner_id=1,
    )

    db = TestSessionLocal()
    db.add(todo)
    db.commit()
    yield todo
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM todos;"))
        connection.commit()