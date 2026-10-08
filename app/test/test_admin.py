from fastapi import status

from ..routers.admin import get_current_user, get_db
from .utils import *

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user


def test_admin_read_all_authenticated(test_todo):
    response = client.get("/admin/todos")
    assert response.status_code == status.HTTP_200_OK
    dados = response.json()

    for todo in dados:
        todo.pop("id", None)

    assert dados == [{
        'title': 'Learn to code',
        'description': 'need to learn',
        'priority': 5,
        'complete': False,
        'owner_id': 1,
    }]