import pytest
from django.test import override_settings
from django.urls import reverse

from access_atlas.accounts.models import User, UserPreference
from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    LIST_SORT_PREFERENCE_KEY_PREFIX,
    SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX,
    SITES_MAP_PREFERENCE_KEY,
    UI_THEME_PREFERENCE_KEY,
)
from access_atlas.accounts.templatetags.avatar import avatar_color, avatar_initials


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
    assert user.avatar_seed


@pytest.mark.django_db
@override_settings(
    LOCAL_LOGIN_ENABLED=False,
    OIDC_LOGIN_ENABLED=True,
    OIDC_PROVIDER_ID="work",
    OIDC_PROVIDER_NAME="Work SSO",
)
def test_login_page_shows_oidc_when_enabled(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200
    assert b"Continue with Work SSO" in response.content
    assert b"/accounts/sso/oidc/work/login/" in response.content
    assert b"Continue with email" not in response.content


@pytest.mark.django_db
@override_settings(
    LOCAL_LOGIN_ENABLED=False,
    OIDC_LOGIN_ENABLED=True,
    OIDC_PROVIDER_ID="work",
    OIDC_PROVIDER_NAME="Work SSO",
)
def test_passwordless_login_is_blocked_when_local_login_is_disabled(client):
    response = client.post(reverse("login"), {"email": "user@example.com"})

    assert response.status_code == 200
    assert b"Local email login is disabled." in response.content
    assert not User.objects.filter(email="user@example.com").exists()


@pytest.mark.django_db
@override_settings(
    LOCAL_LOGIN_ENABLED=True,
    OIDC_LOGIN_ENABLED=True,
    OIDC_PROVIDER_ID="work",
    OIDC_PROVIDER_NAME="Work SSO",
)
def test_login_page_can_show_local_and_oidc_together(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200
    assert b"Continue with Work SSO" in response.content
    assert b"Continue with email" in response.content


@pytest.mark.django_db
def test_user_avatar_helpers_are_stable():
    user = User.objects.create_user(
        email="dave@example.com",
        display_name="Dave Harris",
    )

    assert avatar_initials(user) == "DH"
    assert avatar_color(user) == avatar_color(user)


@pytest.mark.django_db
def test_user_avatar_initials_fall_back_to_email():
    user = User.objects.create_user(email="dave.smith@example.com")

    assert avatar_initials(user) == "DA"
    assert str(user) == "dave.smith@example.com"


@pytest.mark.django_db
def test_header_does_not_duplicate_email_when_display_name_is_blank(client):
    user = User.objects.create_user(email="dave@example.com")
    client.force_login(user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert response.content.count(b"dave@example.com") == 1


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


@pytest.mark.django_db
def test_preference_view_saves_sites_map_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {
            "key": SITES_MAP_PREFERENCE_KEY,
            "value": {"viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8}},
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=SITES_MAP_PREFERENCE_KEY)
    assert preference.value == {"viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8}}


@pytest.mark.django_db
def test_preference_view_rejects_invalid_sites_map_viewport(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {
            "key": SITES_MAP_PREFERENCE_KEY,
            "value": {"viewport": {"lat": -91, "lng": 174.7, "zoom": 8}},
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.filter(
        user=user, key=SITES_MAP_PREFERENCE_KEY
    ).exists()


@pytest.mark.django_db
def test_preference_view_saves_theme_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {"key": UI_THEME_PREFERENCE_KEY, "value": {"mode": "dark"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=UI_THEME_PREFERENCE_KEY)
    assert preference.value == {"mode": "dark"}


@pytest.mark.django_db
def test_preference_view_rejects_invalid_theme_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("account_preference"),
        {"key": UI_THEME_PREFERENCE_KEY, "value": {"mode": "sepia"}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_preference_view_saves_site_access_map_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}12"

    response = client.post(
        reverse("account_preference"),
        {
            "key": key,
            "value": {"visible_record_ids": [3, 9, 3], "animate_tracks": False},
        },
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=key)
    assert preference.value == {"visible_record_ids": [3, 9], "animate_tracks": False}


@pytest.mark.django_db
def test_preference_view_saves_list_sort_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{LIST_SORT_PREFERENCE_KEY_PREFIX}jobs"

    response = client.post(
        reverse("account_preference"),
        {"key": key, "value": {"value": "-status"}},
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=key)
    assert preference.value == {"value": "-status"}


@pytest.mark.django_db
def test_preference_view_rejects_invalid_list_sort_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{LIST_SORT_PREFERENCE_KEY_PREFIX}jobs"

    response = client.post(
        reverse("account_preference"),
        {"key": key, "value": {"value": ""}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.filter(user=user, key=key).exists()


@pytest.mark.django_db
def test_preference_view_rejects_invalid_site_access_map_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}12"

    response = client.post(
        reverse("account_preference"),
        {"key": key, "value": {"visible_record_ids": ["bad"]}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_preference_view_rejects_invalid_site_access_animation_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}12"

    response = client.post(
        reverse("account_preference"),
        {"key": key, "value": {"visible_record_ids": [1], "animate_tracks": "yes"}},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserPreference.objects.exists()


@pytest.mark.django_db
def test_preference_view_allows_site_access_map_preference_without_animation(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    key = f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}12"

    response = client.post(
        reverse("account_preference"),
        {"key": key, "value": {"visible_record_ids": []}},
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserPreference.objects.get(user=user, key=key)
    assert preference.value == {"visible_record_ids": []}
