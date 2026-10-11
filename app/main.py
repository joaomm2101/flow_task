import logging
import os
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text

from .database import SessionLocal
from .observability import VALID_REQUEST_ID, configure_logging, request_id_var
from .routers import admin, auth, todos, user
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException

# Fonts are the only external resource the pages load.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

# What a person sees for each error when a browser navigates to a bad URL (API clients get JSON).
ERROR_PAGES = {
    400: ("Requisição inválida", "Não foi possível entender o endereço solicitado."),
    403: ("Acesso negado", "Você não tem permissão para acessar esta página."),
    404: ("Página não encontrada", "O endereço que você tentou acessar não existe ou foi movido."),
    405: ("Ação não permitida", "Este endereço não aceita esse tipo de acesso."),
    429: ("Muitas tentativas", "Aguarde alguns minutos e tente novamente."),
    500: ("Algo deu errado", "Tivemos um problema inesperado. Tente novamente em instantes."),
    503: ("Serviço indisponível", "Estamos fora do ar por um momento. Tente novamente em instantes."),
}


def wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


def error_page(request: Request, status_code: int, headers: dict | None = None):
    title, message = ERROR_PAGES.get(status_code, ERROR_PAGES[500] if status_code >= 500 else ERROR_PAGES[400])
    return TEMPLATES.TemplateResponse(
        request=request,
        name="error.html",
        context={
            "status_code": status_code,
            "title": title,
            "message": message,
            "request_id": request_id_var.get() if status_code >= 500 else None,
        },
        status_code=status_code,
        headers=headers,
    )

logger = logging.getLogger("flowtask.request")


def allowed_origin_hosts() -> set[str]:
    """Extra hosts (host[:port]) allowed to send state-changing requests, e.g. a separate frontend."""
    return {h.strip() for h in os.environ.get("ALLOWED_ORIGIN_HOSTS", "").split(",") if h.strip()}


def docs_enabled() -> bool:
    return os.environ.get("ENABLE_DOCS", "").strip().lower() in {"1", "true", "yes"}


def create_app(enable_docs: bool = False) -> FastAPI:
    """Swagger/ReDoc/OpenAPI are off unless explicitly enabled (ENABLE_DOCS=true)."""
    app = FastAPI(
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    configure_logging()
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        """Innermost middleware: correlation id, one access-log line, and a generic 500 for
        unhandled errors (details go to the log, never to the client)."""
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if VALID_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                logger.exception("unhandled error", extra={"method": request.method, "path": request.url.path})
                if wants_html(request):
                    response = error_page(request, 500)
                else:
                    response = JSONResponse(
                        {"detail": "Internal server error.", "request_id": request_id}, status_code=500
                    )
            response.headers["X-Request-ID"] = request_id
            if not request.url.path.startswith("/static"):
                logger.info(
                    "request",
                    extra={
                        "method": request.method,
                        "path": request.url.path,  # no query string: it may carry sensitive values
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                        "client": request.client.host if request.client else None,
                    },
                )
            return response
        finally:
            request_id_var.reset(token)

    @app.middleware("http")
    async def reject_cross_origin_writes(request: Request, call_next):
        """CSRF defence in depth on top of SameSite=Lax: browsers always send Origin on
        cross-origin writes, so refuse any whose host is not ours."""
        origin = request.headers.get("origin")
        if request.method in UNSAFE_METHODS and origin is not None:
            origin_host = urlparse(origin).netloc
            if origin_host != request.headers.get("host") and origin_host not in allowed_origin_hosts():
                logger.warning(
                    "cross-origin write refused",
                    extra={"method": request.method, "path": request.url.path, "origin": origin},
                )
                return JSONResponse({"detail": "Cross-origin request refused."}, status_code=403)
        return await call_next(request)

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        # Swagger UI/ReDoc need CDN scripts and inline code, so they get no CSP.
        if not path.startswith(DOCS_PATHS):
            response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
        # Pages and API answers are per-user: don't let browsers/proxies keep them.
        if not path.startswith("/static"):
            response.headers["Cache-Control"] = "no-store"
        # HSTS is only meaningful (and only honoured) over HTTPS, also behind a proxy.
        forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip()
        if request.url.scheme == "https" or forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.exception_handler(StarletteHTTPException)
    async def browser_friendly_http_exception(request: Request, exc: StarletteHTTPException):
        # A browser navigating straight to an API URL sends no Authorization header and
        # accepts HTML: send it back to the app instead of showing raw JSON.
        is_browser_navigation = wants_html(request)
        if (
            exc.status_code == status.HTTP_401_UNAUTHORIZED
            and is_browser_navigation
            and "authorization" not in request.headers
        ):
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        if is_browser_navigation and exc.status_code in ERROR_PAGES and exc.status_code != 401:
            return error_page(request, exc.status_code, headers=getattr(exc, "headers", None))
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def browser_friendly_validation_error(request: Request, exc: RequestValidationError):
        # e.g. /todos/edit-todo-page/abc typed into the address bar
        if wants_html(request):
            return error_page(request, 400)
        return await request_validation_exception_handler(request, exc)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return RedirectResponse(url="/static/favicon.svg", status_code=status.HTTP_301_MOVED_PERMANENTLY)

    @app.get("/", include_in_schema=False)
    def root(request: Request):
        if request.cookies.get("access_token"):
            return RedirectResponse(url="/todos/todo-page", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/auth/login-page", status_code=status.HTTP_302_FOUND)

    @app.get("/healthy")
    def healthy():
        """Liveness: the process is up (does not touch the database)."""
        return {"status": "Healthy"}

    @app.get("/ready")
    def ready():
        """Readiness: the database answers. 503 otherwise, without leaking why."""
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
        except Exception:
            logger.exception("readiness check failed")
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ready"}

    app.include_router(auth.router)
    app.include_router(todos.router)
    app.include_router(admin.router)
    app.include_router(user.router)
    return app


app = create_app(enable_docs=docs_enabled())
