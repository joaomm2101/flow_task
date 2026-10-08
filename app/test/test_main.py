from app.src import app
from fastapi.testclient import TestClient
from fastapi import status

from ..main import app

client = TestClient(app)

def test_healthy():
    response = client.get("/healthy")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "Healthy"}


def test_root_redirects_to_login_without_token():
    response = TestClient(app).get("/", follow_redirects=False)
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/auth/login-page"


def test_root_redirects_to_todo_page_with_token():
    anon = TestClient(app)
    anon.cookies.set("access_token", "any-token")
    response = anon.get("/", follow_redirects=False)
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/todos/todo-page"
