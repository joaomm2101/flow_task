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

app = FastAPI()

Base.metadata.create_all(bind=engine)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

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
