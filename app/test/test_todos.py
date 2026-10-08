from fastapi import status

from ..routers.todos import get_current_user, get_db
from .utils import *

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


app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


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


def test_read_all_authenticated(test_todo):
    response = client.get("/")
    assert response.status_code == status.HTTP_200_OK
    dados = response.json()
    for todo in dados:
        todo.pop("id", None)
    assert dados == [
        {   
            'title': 'Learn to code',
            'description': 'need to learn',
            'priority': 5,
            'complete': False,
            'owner_id': 1,
        }
    ]

def test_read_one_authenticated(test_todo):
    response = client.get("/todo/1")
    assert response.status_code == status.HTTP_200_OK
    dados = response.json()
    dados.pop("id", None)
    assert dados == {   
            'title': 'Learn to code',
            'description': 'need to learn',
            'priority': 5,
            'complete': False,
            'owner_id': 1,
        }
    
def test_read_one_authenticated_not_found():
    response = client.get("/todo/999")
    assert response.status_code == 404
    assert response.json() == {'detail': 'Todo not found.'}


def test_creat_todo(test_todo):
    request_data={
        'title': 'New Todo!',
        'description': 'New todo description',
        'priority': 5,
        'complete': False
    }

    response = client.post("/todo/", json=request_data)
    assert response.status_code == 201

    db = TestSessionLocal()
    model = db.query(Todos).filter(Todos.id == 2).first()
    assert model.title == request_data.get('title')
    assert model.description == request_data.get('description')
    assert model.priority == request_data.get('priority')
    assert model.complete == request_data.get('complete')


def test_update_todo(test_todo):
    request_data={
        'title': 'Change the title',
        'description': 'Need to learn every day',
        'priority': 5,
        'complete': False
    }

    response = client.put("/todo/1", json=request_data)
    assert response.status_code == 204
    db = TestSessionLocal()
    model = db.query(Todos).filter(Todos.id == 1).first()
    assert model.title == 'Change the title'
    


def test_update_todo_not_found(test_todo):
    request_data={
        'title': 'Change the title',
        'description': 'Need to learn every day',
        'priority': 5,
        'complete': False
    }

    response = client.put("/todo/999", json=request_data)
    assert response.status_code == 404
    assert response.json() == {'detail': 'Todo not found.'}


def test_delete_todo(test_todo):
    response = client.delete("/todo/1")
    assert response.status_code == 204
    db = TestSessionLocal()
    model = db.query(Todos).filter(Todos.id == 1).first()
    assert model is None

def test_delete_todo_not_found(test_todo):
    response = client.delete("/todo/404")
    assert response.status_code == 404
    assert response.json() == {'detail': 'Todo not found.'}
    