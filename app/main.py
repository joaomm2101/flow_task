import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import engine
from .models import Base
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


def docs_enabled() -> bool:
    return os.environ.get("ENABLE_DOCS", "").strip().lower() in {"1", "true", "yes"}


def create_app(enable_docs: bool = False) -> FastAPI:
    """Swagger/ReDoc/OpenAPI are off unless explicitly enabled (ENABLE_DOCS=true)."""
    app = FastAPI(
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
        openapi_url="/openapi.json" if enable_docs else None,
    )

    Base.metadata.create_all(bind=engine)
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).resolve().parent / "static"),
        name="static",
    )

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
        is_browser_navigation = "text/html" in request.headers.get("accept", "")
        if (
            exc.status_code == status.HTTP_401_UNAUTHORIZED
            and is_browser_navigation
            and "authorization" not in request.headers
        ):
            return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        return await http_exception_handler(request, exc)

    @app.get("/", include_in_schema=False)
    def root(request: Request):
        if request.cookies.get("access_token"):
            return RedirectResponse(url="/todos/todo-page", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/auth/login-page", status_code=status.HTTP_302_FOUND)

    @app.get("/healthy")
    def healthy():
        return {"status": "Healthy"}

    app.include_router(auth.router)
    app.include_router(todos.router)
    app.include_router(admin.router)
    app.include_router(user.router)
    return app


app = create_app(enable_docs=docs_enabled())
