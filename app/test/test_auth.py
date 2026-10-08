from .utils import *
from ..routers.auth import get_db, authenticate_user, create_access_token, SECRET_KEY, ALGORITHM, get_current_user
from jose import jwt
from datetime import timedelta
import pytest
from fastapi import HTTPException, status
from ..models import Users

app.dependency_overrides[get_db] = override_get_db

def test_authenticate_user(test_user):
    db = TestingSessionLocal()

    authenticated_user = authenticate_user(test_user.username, 'testpassword', db)
    assert authenticated_user is not None
    assert authenticated_user.username == test_user.username

    non_existent_user = authenticate_user('WrongUserName', 'testpassword', db)
    assert non_existent_user is False

    wrong_password_user = authenticate_user(test_user.username, 'wrongpassword', db)
    assert wrong_password_user is False


def test_create_access_token():
    username = 'testuser'
    user_id = 1
    role = 'user'
    expires_delta = timedelta(days=1)

    token = create_access_token(username, user_id, role, expires_delta)

    decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM],
                               options={'verify_signature': False})

    assert decoded_token['sub'] == username
    assert decoded_token['id'] == user_id
    assert decoded_token['role'] == role


@pytest.mark.asyncio
async def test_get_current_user_valid_token():
    encode = {'sub': 'testuser', 'id': 1, 'role': 'admin'}
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

    user = await get_current_user(token=token)
    assert user == {'username': 'testuser', 'id': 1, 'role': 'admin'}


@pytest.mark.asyncio
async def test_get_current_user_missing_payload():
    encode = {'role': 'user'}
    token = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(HTTPException) as excinfo:
        await get_current_user(token=token)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == 'Could not validate credentials.'


def test_create_user():
    request_data = {
        'username': 'newuser',
        'email': 'newuser@email.com',
        'first_name': 'New',
        'last_name': 'User',
        'password': 'newpassword',
        'role': 'user',
        'phone_number': '(222)-222-2222',
    }
    db = TestingSessionLocal()
    try:
        response = client.post("/auth/", json=request_data)
        assert response.status_code == status.HTTP_201_CREATED

        model = db.query(Users).filter(Users.username == 'newuser').first()
        assert model is not None
        assert model.email == request_data['email']
        assert model.first_name == request_data['first_name']
        assert model.last_name == request_data['last_name']
        assert model.role == request_data['role']
        assert model.phone_number == request_data['phone_number']
        assert model.hashed_password != request_data['password']
        assert bcrypt_context.verify(request_data['password'], model.hashed_password)
    finally:
        db.query(Users).filter(Users.username == 'newuser').delete()
        db.commit()
        db.close()


def test_create_user_missing_field():
    response = client.post("/auth/", json={'username': 'incomplete'})
    assert response.status_code == 422


def test_login_for_access_token(test_user):
    response = client.post("/auth/token", data={'username': test_user.username,
                                                'password': 'testpassword'})
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body['token_type'] == 'bearer'

    decoded_token = jwt.decode(body['access_token'], SECRET_KEY, algorithms=[ALGORITHM])
    assert decoded_token['sub'] == test_user.username
    assert decoded_token['role'] == test_user.role


def test_login_for_access_token_wrong_password(test_user):
    response = client.post("/auth/token", data={'username': test_user.username,
                                                'password': 'wrongpassword'})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials.'}


def test_login_for_access_token_unknown_user():
    response = client.post("/auth/token", data={'username': 'ghost', 'password': 'testpassword'})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {'detail': 'Could not validate credentials.'}


### Pages ###

def test_render_login_page():
    response = client.get("/auth/login-page")
    assert response.status_code == status.HTTP_200_OK
    assert 'text/html' in response.headers['content-type']


def test_render_register_page():
    response = client.get("/auth/register-page")
    assert response.status_code == status.HTTP_200_OK
    assert 'text/html' in response.headers['content-type']
