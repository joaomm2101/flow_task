import os
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, TypeAlias

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette import status

from ..database import SessionLocal
from ..models import Users
from ..security import validate_password_strength

router = APIRouter(
    prefix='/auth',
    tags=['auth']
)

templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


try:
    SECRET_KEY = os.environ['SECRET_KEY']
except KeyError:
    raise RuntimeError('SECRET_KEY is not set. See .env.example.') from None
ALGORITHM='HS256'


bycrypt_context = CryptContext(schemes=['bcrypt'], deprecated='auto')
bcrypt_context = bycrypt_context

oauth2_bearer = OAuth2PasswordBearer(tokenUrl='auth/token')


class CreateUserRequest(BaseModel):
    username : str
    email: str
    first_name: str
    last_name: str
    password: str
    phone_number: str

    _check_password = field_validator('password')(validate_password_strength)

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally:
        db.close()

db_dependency: TypeAlias = Annotated[Session, Depends(get_db)]  # noqa: PYI042, UP040


def authenticate_user(username: str, password: str, db):
    user = db.query(Users).filter(Users.username == username).first()
    if not user: 
        return False
    if not bycrypt_context.verify(password, user.hashed_password):
        return False
    return user

def create_acess_token(username: str, user_id: int, role: str, expires_delta: timedelta):

    encode = {'sub': username, 'id': user_id, 'role': role}
    expires = datetime.now(UTC) + expires_delta
    encode.update({'exp': expires})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)


create_access_token = create_acess_token




async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)]):
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Could not validate credentials.',
        )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get('sub')
        user_id: int = payload.get('id')
        user_role: str = payload.get('role')
        if username is None or user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials.')
        return {'username': username, 'id': user_id, 'role': user_role}

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials.')


@router.get("/login-page")
def render_login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/auth/login-page", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key="access_token", path="/")
    return response


@router.get("/register-page")
def render_register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")
        




@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(db: db_dependency, create_user_request: CreateUserRequest):
    taken = db.query(Users).filter(
        (Users.username == create_user_request.username) | (Users.email == create_user_request.email)
    ).first()
    if taken:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Username or email is already registered.',
        )

    create_user_model = Users(
        email=create_user_request.email,
        username=create_user_request.username,
        first_name=create_user_request.first_name,
        last_name=create_user_request.last_name,
        role='user',  # never taken from the client: public signup must not grant admin
        hashed_password=bycrypt_context.hash(create_user_request.password),
        phone_number=create_user_request.phone_number,
        is_active=True
    )


    db.add(create_user_model)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race against a concurrent signup: the UNIQUE constraint caught it
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Username or email is already registered.',
        )


@router.post("/token")
async def login_for_acess_token(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: db_dependency):

    user = authenticate_user(form_data.username, form_data.password, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Could not validate credentials.')
        
    token = create_acess_token(user.username, user.id, user.role, timedelta(minutes=20))

    return {'access_token': token, 'token_type': 'bearer'}


    
