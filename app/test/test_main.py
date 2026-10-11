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


def test_security_headers_on_pages_and_api():
    response = TestClient(app).get("/auth/login-page")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "same-origin"
    assert response.headers["cache-control"] == "no-store"
    csp = response.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
    assert "strict-transport-security" not in response.headers  # plain http


def test_hsts_only_over_https():
    https = TestClient(app, base_url="https://testserver").get("/healthy")
    proxied = TestClient(app).get("/healthy", headers={"x-forwarded-proto": "https"})

    assert "max-age=31536000" in https.headers["strict-transport-security"]
    assert "max-age=31536000" in proxied.headers["strict-transport-security"]


def test_static_files_are_cacheable_but_still_hardened():
    response = TestClient(app).get("/static/css/base.css")

    assert response.status_code == status.HTTP_200_OK
    assert "cache-control" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"


def test_docs_are_disabled_by_default():
    from ..main import create_app

    client = TestClient(create_app())
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == status.HTTP_404_NOT_FOUND


def test_docs_can_be_enabled_and_have_no_csp():
    from ..main import create_app

    client = TestClient(create_app(enable_docs=True))
    assert client.get("/openapi.json").status_code == status.HTTP_200_OK
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
    assert "content-security-policy" not in response.headers


def test_navbar_has_no_inline_handlers():
    from pathlib import Path

    templates = Path(__file__).resolve().parent.parent / "templates"
    for html in templates.glob("*.html"):
        text = html.read_text()
        assert " onclick=" not in text, html.name
        assert "<script>" not in text, html.name
