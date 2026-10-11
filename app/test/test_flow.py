from datetime import timedelta

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ..routers import auth, todos
from .utils import TestSessionLocal, Todos, Users, app, override_get_db

OTHER_USER = {
    "username": "otheruser",
    "email": "otheruser@email.com",
    "first_name": "Other",
    "last_name": "User",
    "password": "otherpassword1",
    "role": "user",
    "phone_number": "(333)-333-3333",
}

USER = {
    "username": "flowuser",
    "email": "flowuser@email.com",
    "first_name": "Flow",
    "last_name": "User",
    "password": "flowpassword1",
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
    for data in (USER, OTHER_USER):
        user = db.query(Users).filter(Users.username == data["username"]).first()
        if user:
            db.query(Todos).filter(Todos.owner_id == user.id).delete()
            db.delete(user)
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


def test_logout_clears_cookie_and_redirects_to_login(real_auth):
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", "whatever")

    response = client.get("/auth/logout")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/auth/login-page"
    assert "access_token=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_expired_token_redirects_to_login_and_clears_cookie(real_auth):
    expired = auth.create_access_token("flowuser", 1, "user", timedelta(minutes=-1))
    client = TestClient(app, follow_redirects=False)
    client.cookies.set("access_token", expired)

    response = client.get("/todos/todo-page")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/auth/login-page"
    assert "Max-Age=0" in response.headers["set-cookie"]


def test_api_rejects_expired_token_with_401(real_auth):
    expired = auth.create_access_token("flowuser", 1, "user", timedelta(minutes=-1))
    client = TestClient(app)

    response = client.get("/todos/", headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.parametrize("path", ["/todos/", "/todos/todo/1", "/admin/todos", "/user/"])
def test_api_routes_redirect_browser_navigation(real_auth, path):
    client = TestClient(app, follow_redirects=False)

    response = client.get(path, headers={"accept": "text/html,application/xhtml+xml"})

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/"


@pytest.mark.parametrize("headers", [{"accept": "application/json"}, {"accept": "*/*"}])
def test_api_routes_keep_json_401_for_api_clients(real_auth, headers):
    client = TestClient(app, follow_redirects=False)

    response = client.get("/todos/", headers=headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Could not validate credentials."}
    assert response.headers["www-authenticate"] == "Bearer"


def _login(client, data):
    assert client.post("/auth/", json=data).status_code == status.HTTP_201_CREATED
    response = client.post(
        "/auth/token", data={"username": data["username"], "password": data["password"]}
    )
    token = response.json()["access_token"]
    client.cookies.set("access_token", token)
    return token


def test_edit_page_only_shows_own_todos(real_auth):
    owner = TestClient(app, follow_redirects=False)
    token = _login(owner, USER)
    owner.post(
        "/todos/todo",
        json={"title": "Privado do dono", "description": "so o dono ve", "priority": 2, "complete": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    todo_id = owner.get("/todos/", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]

    assert "Privado do dono" in owner.get(f"/todos/edit-todo-page/{todo_id}").text

    intruder = TestClient(app, follow_redirects=False)
    _login(intruder, OTHER_USER)
    response = intruder.get(f"/todos/edit-todo-page/{todo_id}")
    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/todos/todo-page"
    assert "Privado do dono" not in response.text
    # the session of the intruder is untouched (not treated as expired)
    assert "set-cookie" not in response.headers


def test_edit_page_for_missing_todo_redirects_to_dashboard(real_auth):
    client = TestClient(app, follow_redirects=False)
    _login(client, USER)

    response = client.get("/todos/edit-todo-page/99999")

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/todos/todo-page"


def test_login_sets_httponly_samesite_cookie_with_the_jwt(real_auth, monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "true")
    client = TestClient(app, follow_redirects=False)
    client.post("/auth/", json=USER)

    response = client.post("/auth/token", data={"username": USER["username"], "password": USER["password"]})

    cookie = response.headers["set-cookie"]
    token = response.json()["access_token"]
    assert cookie.startswith(f"access_token={token}")
    assert "HttpOnly" in cookie and "Secure" in cookie
    assert "SameSite=lax" in cookie and "Max-Age=1200" in cookie and "Path=/" in cookie


def test_cookie_secure_flag_can_be_disabled_for_local_http(real_auth, monkeypatch):
    monkeypatch.setenv("COOKIE_SECURE", "false")
    client = TestClient(app, follow_redirects=False)
    client.post("/auth/", json=USER)

    response = client.post("/auth/token", data={"username": USER["username"], "password": USER["password"]})

    assert "Secure" not in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]


def test_api_accepts_the_session_cookie_without_authorization_header(real_auth):
    client = TestClient(app, follow_redirects=False)
    token = _login(client, USER)  # cookie only from here on

    response = client.post(
        "/todos/todo",
        json={"title": "via cookie", "description": "no bearer header", "priority": 1, "complete": False},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert client.get("/todos/").json()[0]["title"] == "via cookie"
    assert token  # the JSON body still carries the token for API clients


def test_cross_origin_write_with_session_cookie_is_refused(real_auth):
    client = TestClient(app, follow_redirects=False)
    _login(client, USER)
    body = {"title": "csrf", "description": "forged", "priority": 1, "complete": False}

    forged = client.post("/todos/todo", json=body, headers={"origin": "https://evil.example"})
    null_origin = client.post("/todos/todo", json=body, headers={"origin": "null"})
    same_origin = client.post("/todos/todo", json=body, headers={"origin": "http://testserver"})

    assert forged.status_code == status.HTTP_403_FORBIDDEN
    assert null_origin.status_code == status.HTTP_403_FORBIDDEN
    assert same_origin.status_code == status.HTTP_201_CREATED
    assert [t["title"] for t in client.get("/todos/").json()] == ["csrf"]  # only the legit one


def test_allowed_origin_hosts_can_be_configured(real_auth, monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGIN_HOSTS", "app.example.com")
    client = TestClient(app, follow_redirects=False)
    _login(client, USER)
    body = {"title": "allowed", "description": "allowed host", "priority": 1, "complete": False}

    response = client.post("/todos/todo", json=body, headers={"origin": "https://app.example.com"})

    assert response.status_code == status.HTTP_201_CREATED


def test_logout_expires_the_cookie_with_matching_attributes(real_auth):
    response = TestClient(app, follow_redirects=False).get("/auth/logout")

    cookie = response.headers["set-cookie"]
    assert "Max-Age=0" in cookie and "HttpOnly" in cookie and "Path=/" in cookie
