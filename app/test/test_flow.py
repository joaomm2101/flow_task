import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ..routers import auth, todos
from .utils import TestSessionLocal, Todos, Users, app, override_get_db

USER = {
    "username": "flowuser",
    "email": "flowuser@email.com",
    "first_name": "Flow",
    "last_name": "User",
    "password": "flowpassword",
    "role": "user",
    "phone_number": "(222)-222-2222",
}


@pytest.fixture
def real_auth():
    """Use the real JWT validation (other test modules override get_current_user)."""
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.pop(auth.get_current_user, None)
    app.dependency_overrides[auth.get_db] = override_get_db
    app.dependency_overrides[todos.get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(saved)
    db = TestSessionLocal()
    user = db.query(Users).filter(Users.username == USER["username"]).first()
    if user:
        db.query(Todos).filter(Todos.owner_id == user.id).delete()
    db.query(Users).filter(Users.username == USER["username"]).delete()
    db.commit()
    db.close()


def test_register_login_dashboard_create_todo(real_auth):
    client = TestClient(app, follow_redirects=False)

    # visitor without token is sent to the login page
    response = client.get("/")
    assert response.headers["location"] == "/auth/login-page"
    response = client.get("/todos/todo-page")
    assert response.headers["location"] == "/auth/login-page"

    # register with the exact payload the register form sends
    response = client.post("/auth/", json=USER)
    assert response.status_code == status.HTTP_201_CREATED

    # login, then store the JWT in the cookie like base.js does
    response = client.post(
        "/auth/token",
        data={"username": USER["username"], "password": USER["password"]},
    )
    assert response.status_code == status.HTTP_200_OK
    token = response.json()["access_token"]
    client.cookies.set("access_token", token)

    # logged-in user is taken to the dashboard, which renders empty
    assert client.get("/").headers["location"] == "/todos/todo-page"
    response = client.get("/todos/todo-page")
    assert response.status_code == status.HTTP_200_OK
    assert "Nenhuma tarefa por aqui" in response.text
    assert client.get("/todos/add-todo-page").status_code == status.HTTP_200_OK

    # create a todo the way the add-todo form does (Bearer token from cookie)
    response = client.post(
        "/todos/todo",
        json={"title": "Fluxo completo", "description": "tarefa e2e", "priority": 3, "complete": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = client.get("/todos/todo-page")
    assert "Fluxo completo" in response.text
    assert "Nenhuma tarefa por aqui" not in response.text
