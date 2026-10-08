from typing import Annotated, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Query
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from pydantic_core.core_schema import GeneralPlainNoInfoSerializerFunction
from sqlalchemy.orm import Session
from starlette import status

from ..database import SessionLocal
from ..models import Todos, Users
from .auth import get_current_user

router = APIRouter(
       prefix='/user',
        tags=['user']
)


def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]
user_dependency = Annotated[dict, Depends(get_current_user)]


@router.get("/", status_code=status.HTTP_200_OK)
async def read_user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed.')
        
    return db.query(Users).filter(Users.id == user.get('id')).first()

@router.put("/user/password", status_code=status.HTTP_200_OK)
async def update_user_password(user: user_dependency, db: db_dependency, new_password: str = Query(min_length=6)):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed.')
        
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if user_model is None:
        raise HTTPException(status_code=404, detail='User not found.')
    
    hashed_password = CryptContext(schemes=['bcrypt']).hash(new_password)
    user_model.hashed_password = hashed_password
    db.add(user_model)
    db.commit()
    
    return {'message': 'Password updated successfully.'}


@router.put("/phone_number/{phone_number}", status_code=status.HTTP_200_OK)
async def update_user_phone_number(user: user_dependency, db: db_dependency, phone_number: str = Path(min_length=10, max_length=20)):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed.')
        
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if user_model is None:
        raise HTTPException(status_code=404, detail='User not found.')
    
    user_model.phone_number = phone_number
    db.add(user_model)
    db.commit()
    
    return {'message': 'Phone number updated successfully.'}