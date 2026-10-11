from .utils import *
from ..routers.user import get_db, get_current_user
from fastapi import status

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

def test_return_user(test_user):
    response = client.get("/user")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()['username'] == 'codingwithrobytest'
    assert response.json()['email'] == 'codingwithrobytest@email.com'
    assert response.json()['first_name'] == 'Eric'
    assert response.json()['last_name'] == 'Roby'
    assert response.json()['role'] == 'admin'
    assert response.json()['phone_number'] == '(111)-111-1111'
    assert 'hashed_password' not in response.json()


def test_change_password_success(test_user):
    response = client.put(
        "/user/user/password",
        json={"password": "testpassword", "new_password": "newpassword1"},
    )
    assert response.status_code == status.HTTP_200_OK

    db = TestSessionLocal()
    user = db.query(Users).filter(Users.username == test_user.username).first()
    assert bcrypt_context.verify("newpassword1", user.hashed_password)
    db.close()


def test_change_password_invalid_current_password(test_user):
    response = client.put(
        "/user/user/password",
        json={"password": "wrongpassword", "new_password": "newpassword1"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {"detail": "Error on password change."}


def test_change_password_requires_current_password(test_user):
    response = client.put("/user/user/password", json={"new_password": "newpassword1"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_change_phone_number_success(test_user):
    response = client.put("/user/phone_number/2222222222")
    assert response.status_code == status.HTTP_200_OK







def test_change_password_rejects_weak_new_password(test_user):
    response = client.put(
        "/user/user/password",
        json={"password": "testpassword", "new_password": "short1"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
