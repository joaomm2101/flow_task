from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import engine
from .models import Base
from .routers import admin, auth, todos, user
from starlette import status

app = FastAPI()

Base.metadata.create_all(bind=engine)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent / "static"),
    name="static",
)

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
