from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session
from starlette import status

from ..database import SessionLocal
from ..models import Users
from ..security import validate_password_strength
from .auth import bcrypt_context, get_current_user

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


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    first_name: str
    last_name: str
    role: str
    phone_number: str | None = None
    is_active: bool | None = None


class UserVerification(BaseModel):
    password: str
    new_password: str

    _check_new_password = field_validator('new_password')(validate_password_strength)


@router.get("/", status_code=status.HTTP_200_OK, response_model=UserResponse)
async def read_user(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed.')
        
    return db.query(Users).filter(Users.id == user.get('id')).first()

@router.put("/user/password", status_code=status.HTTP_200_OK)
async def update_user_password(user: user_dependency, db: db_dependency, user_verification: UserVerification):
    if user is None:
        raise HTTPException(status_code=401, detail='Authentication Failed.')
        
    user_model = db.query(Users).filter(Users.id == user.get('id')).first()
    if user_model is None:
        raise HTTPException(status_code=404, detail='User not found.')

    if not bcrypt_context.verify(user_verification.password, user_model.hashed_password):
        raise HTTPException(status_code=401, detail='Error on password change.')

    user_model.hashed_password = bcrypt_context.hash(user_verification.new_password)
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