import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from ..main import create_app

APP_DIR = Path(__file__).resolve().parent.parent
HTML = {"accept": "text/html,application/xhtml+xml"}


def test_unknown_url_in_a_browser_shows_the_404_page():
    response = TestClient(create_app()).get("/nao-existe", headers=HTML)

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.headers["content-type"].startswith("text/html")
    assert "Página não encontrada" in response.text
    assert "ERRO 404" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"


def test_unknown_url_for_an_api_client_stays_json():
    for accept in ({"accept": "application/json"}, {"accept": "*/*"}, {}):
        response = TestClient(create_app()).get("/nao-existe", headers=accept)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"detail": "Not Found"}


def test_wrong_method_in_a_browser_shows_a_friendly_page_and_keeps_the_allow_header():
    response = TestClient(create_app()).get("/auth/token", headers=HTML)

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert "Ação não permitida" in response.text
    assert "POST" in response.headers["allow"]


def test_invalid_path_parameter_in_a_browser_shows_a_400_page_but_json_for_clients():
    app = create_app()
    html = TestClient(app).get("/todos/edit-todo-page/abc", headers=HTML)
    api = TestClient(app).get("/todos/edit-todo-page/abc", headers={"accept": "application/json"})

    assert html.status_code == status.HTTP_400_BAD_REQUEST and "Requisição inválida" in html.text
    assert api.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert isinstance(api.json()["detail"], list)


def test_server_error_page_shows_the_request_id_but_no_internals():
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("db password is hunter2")

    response = TestClient(app).get("/boom", headers={**HTML, "x-request-id": "trace-12345678"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Algo deu errado" in response.text
    assert "trace-12345678" in response.text
    assert "hunter2" not in response.text and "RuntimeError" not in response.text


def test_unauthenticated_browser_navigation_to_the_api_still_redirects_not_404_page():
    response = TestClient(create_app()).get("/todos/", headers=HTML, follow_redirects=False)

    assert response.status_code == status.HTTP_302_FOUND
    assert response.headers["location"] == "/"


def test_favicon_is_served_and_the_legacy_path_redirects_to_it():
    client = TestClient(create_app())

    legacy = client.get("/favicon.ico", follow_redirects=False)
    icon = client.get("/static/favicon.svg")

    assert legacy.status_code == status.HTTP_301_MOVED_PERMANENTLY
    assert legacy.headers["location"] == "/static/favicon.svg"
    assert icon.status_code == status.HTTP_200_OK and icon.headers["content-type"].startswith("image/svg+xml")
    assert 'rel="icon"' in client.get("/auth/login-page").text


def test_templates_have_no_dead_links_and_every_form_has_a_feedback_area():
    templates = APP_DIR / "templates"
    for name in ("login.html", "register.html", "add-todo.html", "edit-todo.html"):
        assert 'class="form-feedback"' in (templates / name).read_text(), name
    for html in templates.glob("*.html"):
        assert 'href="#"' not in html.read_text(), html.name
    assert not (templates / "home.html").exists()


def test_javascript_does_not_use_alert():
    assert "alert(" not in (APP_DIR / "static" / "js" / "base.js").read_text()


# --- behaviour of base.js in a tiny DOM stub (needs node; always available on CI) ----------------

NODE = shutil.which("node")

HARNESS = textwrap.dedent(
    """
    const fs = require('fs');
    const src = fs.readFileSync(process.argv[2], 'utf8');
    const scenario = JSON.parse(process.argv[3]);

    const nav = { href: null };
    const feedback = { textContent: '', hidden: true };
    const submit = { disabled: false };
    const lock = { disabled: false };
    const form = {
      querySelector: () => feedback,
      querySelectorAll: () => [submit, lock],
      setAttribute() {},
      handlers: {},
      addEventListener(type, fn) { this.handlers[type] = fn; },
    };
    const deleteButton = { handlers: {}, addEventListener(type, fn) { this.handlers[type] = fn; } };
    const byId = { [scenario.form]: form, deleteButton };
    global.document = { getElementById: (id) => byId[id] || null, querySelectorAll: () => [] };
    global.window = { location: Object.defineProperties({ pathname: '/todos/edit-todo-page/7' },
      { href: { get: () => nav.href, set: (v) => { nav.href = v; } } }), confirm: () => scenario.confirm !== false };
    global.FormData = class { constructor() { this.rows = scenario.fields; } entries() { return this.rows[Symbol.iterator](); } };
    global.URLSearchParams = URLSearchParams;
    let calls = [];
    global.fetch = async (url, opts) => {
      calls.push({ url, method: (opts || {}).method });
      if (scenario.network) throw new Error('offline');
      return { ok: scenario.status < 400, status: scenario.status, json: async () => scenario.body };
    };
    eval(src + '; global.__logout = logout;');
    (async () => {
      const target = scenario.target === 'delete' ? deleteButton : form;
      await target.handlers[scenario.target === 'delete' ? 'click' : 'submit']({ preventDefault() {}, target: form });
      console.log(JSON.stringify({ nav: nav.href, text: feedback.textContent, hidden: feedback.hidden,
        submitDisabled: submit.disabled, lockDisabled: lock.disabled, calls }));
    })();
    """
)


def run_js(**scenario):
    script = APP_DIR / "test" / "_base_js_harness.js"
    script.write_text(HARNESS)
    try:
        out = subprocess.run(
            [NODE, str(script), str(APP_DIR / "static" / "js" / "base.js"), json.dumps(scenario)],
            capture_output=True, text=True, timeout=20, check=True,
        )
    finally:
        script.unlink(missing_ok=True)
    return json.loads(out.stdout.strip().splitlines()[-1])


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")
LOGIN = {"form": "loginForm", "fields": [["username", "ana"], ["password", "x"]]}


@needs_node
def test_js_login_failure_shows_a_message_in_the_form_and_unlocks_the_button():
    result = run_js(**LOGIN, status=401, body={"detail": "Could not validate credentials."})

    assert result["text"] == "Usuário ou senha inválidos."
    assert result["hidden"] is False and result["submitDisabled"] is False and result["nav"] is None


@needs_node
def test_js_login_success_navigates_and_keeps_the_button_locked_against_double_submit():
    result = run_js(**LOGIN, status=200, body={"access_token": "ignored", "token_type": "bearer"})

    assert result["nav"] == "/todos/todo-page"
    assert result["submitDisabled"] is True and result["text"] == ""


@needs_node
def test_js_rate_limit_and_server_and_network_errors_have_friendly_messages():
    limited = run_js(**LOGIN, status=429, body={"detail": "Too many failed login attempts."})
    broken = run_js(**LOGIN, status=500, body={"detail": "Internal server error.", "request_id": "abc12345"})
    offline = run_js(**LOGIN, network=True)

    assert "Muitas tentativas" in limited["text"]
    assert "Erro no servidor" in broken["text"] and "abc12345" in broken["text"]
    assert "conectar ao servidor" in offline["text"] and offline["submitDisabled"] is False


@needs_node
def test_js_register_validates_matching_passwords_without_calling_the_api():
    fields = [["email", "a@b.c"], ["username", "ana"], ["first_name", "A"], ["last_name", "B"],
              ["phone_number", "1"], ["password", "Abcdefg1"], ["password2", "different1"]]
    result = run_js(form="registerForm", fields=fields, status=201, body={})

    assert result["text"] == "As senhas não conferem." and result["calls"] == []


@needs_node
def test_js_register_conflict_and_weak_password_messages():
    fields = [["email", "a@b.c"], ["username", "ana"], ["first_name", "A"], ["last_name", "B"],
              ["phone_number", "1"], ["password", "weak"], ["password2", "weak"]]
    conflict = run_js(form="registerForm", fields=fields, status=409, body={"detail": "x"})
    weak = run_js(form="registerForm", fields=fields, status=422,
                  body={"detail": [{"loc": ["body", "password"], "msg": "too short"}]})

    assert conflict["text"] == "Usuário ou e-mail já cadastrado."
    assert "8 a 72 caracteres" in weak["text"]


@needs_node
def test_js_server_text_is_set_with_textcontent_so_markup_is_inert():
    payload = '<img src=x onerror="alert(1)">'
    result = run_js(**LOGIN, status=400, body={"detail": payload})

    assert result["text"] == payload  # stored as plain text on textContent, never parsed as HTML


@needs_node
def test_js_expired_session_on_save_redirects_to_logout_without_a_message():
    fields = [["title", "abc"], ["description", "abcdef"], ["priority", "2"]]
    result = run_js(form="todoForm", fields=fields, status=401, body={"detail": "x"})

    assert result["nav"] == "/auth/logout" and result["text"] == ""


@needs_node
def test_js_delete_asks_for_confirmation_first():
    base = dict(form="editTodoForm", fields=[], target="delete", status=204, body={})
    cancelled = run_js(**base, confirm=False)
    confirmed = run_js(**base, confirm=True)

    assert cancelled["calls"] == [] and cancelled["nav"] is None
    assert confirmed["calls"] == [{"url": "/todos/todo/7", "method": "DELETE"}]
    assert confirmed["nav"] == "/todos/todo-page"
