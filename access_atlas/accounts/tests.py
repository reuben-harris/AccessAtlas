import pytest
from django.urls import reverse

from access_atlas.accounts.models import User


@pytest.mark.django_db
def test_passwordless_login_creates_user(client):
    response = client.post(
        reverse("login"),
        {"email": "USER@example.com", "display_name": "User Example"},
    )

    assert response.status_code == 302
    user = User.objects.get(email="user@example.com")
    assert user.display_name == "User Example"
    assert not user.has_usable_password()
