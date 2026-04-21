import pytest
from django.urls import reverse

from access_atlas.accounts.models import User, UserPreference
from access_atlas.accounts.preferences import JOBS_MAP_PREFERENCE_KEY


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


@pytest.mark.django_db
def test_preference_view_saves_allowed_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {
            "key": JOBS_MAP_PREFERENCE_KEY,
            "value": {
                "visible_statuses": ["planned", "completed", "planned"],
                "viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8},
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=JOBS_MAP_PREFERENCE_KEY)
    assert preference.value == {
        "visible_statuses": ["planned", "completed"],
        "viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8},
    }


@pytest.mark.django_db
def test_preference_view_rejects_unknown_key(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {"key": "unknown", "value": {}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_preference_view_rejects_unknown_job_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {
            "key": JOBS_MAP_PREFERENCE_KEY,
            "value": {"visible_statuses": ["planned", "unknown"]},
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_preference_view_rejects_invalid_map_viewport(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {
            "key": JOBS_MAP_PREFERENCE_KEY,
            "value": {
                "visible_statuses": ["planned"],
                "viewport": {"lat": -100, "lng": 174.7, "zoom": 8},
            },
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()
