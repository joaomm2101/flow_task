from fastapi import FastAPI

from .database import engine
from .models import Base
from .routers import admin, auth, todos, user

app = FastAPI()

Base.metadata.create_all(bind=engine)

@app.get("/healthy")
def healthy():
    return {"status": "Healthy"}

app.include_router(auth.router)
app.include_router(todos.router)
app.include_router(admin.router)
app.include_router(user.router)

