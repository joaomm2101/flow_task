import json
import logging

from fastapi import status
from fastapi.testclient import TestClient

from .. import main
from ..main import create_app
from ..observability import JsonFormatter, request_id_var


def test_liveness_does_not_need_the_database():
    assert TestClient(create_app()).get("/healthy").json() == {"status": "Healthy"}


def test_readiness_reports_ready_when_the_database_answers():
    response = TestClient(create_app()).get("/ready")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ready"}


def test_readiness_is_503_without_leaking_the_reason_when_the_database_is_down(monkeypatch):
    class BrokenSession:
        def __enter__(self):
            raise RuntimeError("password authentication failed for user postgres")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(main, "SessionLocal", BrokenSession)

    response = TestClient(create_app()).get("/ready")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {"status": "unavailable"}
    assert "password" not in response.text


def test_every_response_carries_a_request_id_and_valid_ones_are_echoed():
    client = TestClient(create_app())

    generated = client.get("/healthy").headers["x-request-id"]
    echoed = client.get("/healthy", headers={"x-request-id": "trace-12345678"}).headers["x-request-id"]
    replaced = client.get("/healthy", headers={"x-request-id": "bad id\twith spaces"}).headers["x-request-id"]

    assert len(generated) == 32
    assert echoed == "trace-12345678"
    assert replaced != "bad id\twith spaces" and len(replaced) == 32


def test_access_log_has_request_id_and_no_query_string(caplog):
    client = TestClient(create_app())

    with caplog.at_level(logging.INFO, logger="flowtask.request"):
        response = client.get("/healthy?secret=abc123", headers={"x-request-id": "trace-12345678"})

    record = next(r for r in caplog.records if r.getMessage() == "request")
    assert (record.method, record.path, record.status) == ("GET", "/healthy", 200)
    assert "secret" not in record.path
    assert response.headers["x-request-id"] == "trace-12345678"


def test_unhandled_error_returns_generic_500_with_request_id_and_logs_the_traceback(caplog):
    app = create_app()

    @app.get("/boom")
    def boom():
        raise RuntimeError("secret internal detail: db password is hunter2")

    client = TestClient(app)
    with caplog.at_level(logging.ERROR, logger="flowtask.request"):
        response = client.get("/boom", headers={"x-request-id": "trace-12345678"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json() == {"detail": "Internal server error.", "request_id": "trace-12345678"}
    assert "hunter2" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"  # still hardened
    logged = next(r for r in caplog.records if r.getMessage() == "unhandled error")
    assert "hunter2" in logged.exc_text or "hunter2" in str(logged.exc_info[1])


def test_cross_origin_refusal_is_logged(caplog):
    client = TestClient(create_app())

    with caplog.at_level(logging.WARNING, logger="flowtask.request"):
        response = client.post("/auth/token", headers={"origin": "https://evil.example"})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert any(r.getMessage() == "cross-origin write refused" for r in caplog.records)


def test_json_formatter_emits_one_valid_json_object_with_extras_and_exception():
    token = request_id_var.set("rid-1234567")
    try:
        try:
            raise ValueError("bad")
        except ValueError:
            import sys

            record = logging.LogRecord("flowtask.x", logging.ERROR, __file__, 1, "hello %s", ("world",), sys.exc_info())
        record.status = 418
        line = JsonFormatter().format(record)
    finally:
        request_id_var.reset(token)

    data = json.loads(line)
    assert data["message"] == "hello world" and data["level"] == "ERROR"
    assert data["request_id"] == "rid-1234567" and data["status"] == 418
    assert "ValueError: bad" in data["exception"]
    assert "\n" not in line
