from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from access_atlas.accounts.models import User
from access_atlas.api.models import ApiToken
from access_atlas.api.token_services import create_api_token
from access_atlas.jobs.models import Job, JobTemplate, TemplateRequirement
from access_atlas.sites.models import Site, SitePhoto
from access_atlas.trips.models import SiteVisit, Trip, TripStatus


def create_user(email="user@example.com"):
    return User.objects.create_user(email=email)


def create_site(code="AA-001"):
    return Site.objects.create(
        source_name="dummy",
        external_id=code,
        code=code,
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )


def authenticated_api_client(user, *, can_write=False):
    token, plaintext_token = create_api_token(
        user=user,
        name="Integration",
        can_write=can_write,
    )
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {plaintext_token}")
    return client, token


def image_upload(name="site.jpg", color=(200, 40, 40)):
    image = Image.new("RGB", (24, 24), color)
    output = BytesIO()
    image.save(output, format="JPEG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/jpeg")


@pytest.mark.django_db
def test_header_links_to_swagger_docs_and_api_tokens(client):
    user = create_user()
    client.force_login(user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    content = response.content.decode()
    assert static("docs/index.html") in content
    assert 'aria-label="Documentation"' in content
    assert 'title="Documentation"' in content
    assert reverse("api_schema_swagger_ui") in content
    assert 'aria-label="Swagger docs"' in content
    assert 'title="Swagger docs"' in content
    assert "API docs" not in content
    assert reverse("api_token_list") in content


@pytest.mark.django_db
def test_user_menu_does_not_include_api_docs_link(client):
    user = create_user()
    client.force_login(user)

    response = client.get(reverse("dashboard"))

    assert response.status_code == 200
    content = response.content.decode()
    assert content.count(reverse("api_schema_swagger_ui")) == 1


@pytest.mark.django_db
def test_swagger_docs_use_local_assets(client):
    user = create_user()
    client.force_login(user)

    response = client.get(reverse("api_schema_swagger_ui"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "/static/drf_spectacular_sidecar/" in content
    assert "cdn.jsdelivr.net" not in content


@pytest.mark.django_db
def test_api_token_authenticates_and_updates_last_used():
    user = create_user()
    create_site()
    api_client, token = authenticated_api_client(user)

    response = api_client.get(reverse("site-api-list"))

    assert response.status_code == 200
    token.refresh_from_db()
    assert token.last_used_at is not None


@pytest.mark.django_db
def test_read_only_api_token_cannot_write():
    user = create_user()
    api_client, _token = authenticated_api_client(user, can_write=False)

    response = api_client.post(
        reverse("job-template-api-list"),
        {"title": "Replace sensor"},
        format="json",
    )

    assert response.status_code == 403
    assert not JobTemplate.objects.exists()


@pytest.mark.django_db
def test_sites_api_is_read_only_even_for_write_token():
    user = create_user()
    api_client, _token = authenticated_api_client(user, can_write=True)

    response = api_client.post(
        reverse("site-api-list"),
        {
            "source_name": "dummy",
            "external_id": "AA-001",
            "code": "AA-001",
            "name": "Site",
            "latitude": "-41.100000",
            "longitude": "174.100000",
        },
        format="json",
    )

    assert response.status_code == 405
    assert not Site.objects.exists()


@pytest.mark.django_db
def test_write_token_can_create_job_from_template():
    user = create_user()
    site = create_site()
    template = JobTemplate.objects.create(title="Replace sensor")
    TemplateRequirement.objects.create(job_template=template, name="Sensor cable")
    api_client, _token = authenticated_api_client(user, can_write=True)

    response = api_client.post(
        reverse("job-api-from-template"),
        {"site": site.pk, "template": template.pk},
        format="json",
    )

    assert response.status_code == 201
    job = Job.objects.get()
    assert job.title == "Replace sensor"
    assert job.requirements.get().name == "Sensor cable"
    assert response.json()["id"] == job.pk


@pytest.mark.django_db
def test_approved_trip_api_update_requires_confirmation_and_resubmits():
    user = create_user()
    leader = create_user("leader@example.com")
    trip = Trip.objects.create(
        name="Ridge trip",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 5),
        trip_leader=leader,
        submitted_by=leader,
        submitted_at=timezone.now(),
        approved_at=timezone.now(),
        approval_round=1,
        status=TripStatus.APPROVED,
    )
    api_client, _token = authenticated_api_client(user, can_write=True)

    response = api_client.patch(
        reverse("trip-api-detail", kwargs={"pk": trip.pk}),
        {"notes": "Updated by integration"},
        format="json",
    )
    assert response.status_code == 400

    response = api_client.patch(
        reverse("trip-api-detail", kwargs={"pk": trip.pk}),
        {"notes": "Updated by integration", "confirm_approval_reset": True},
        format="json",
    )

    assert response.status_code == 200
    trip.refresh_from_db()
    assert trip.notes == "Updated by integration"
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 2
    assert trip.submitted_by == user


@pytest.mark.django_db
def test_site_visit_api_rejects_terminal_trip_creation():
    user = create_user()
    site = create_site()
    trip = Trip.objects.create(
        name="Completed trip",
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 5),
        trip_leader=user,
        status=TripStatus.COMPLETED,
    )
    api_client, _token = authenticated_api_client(user, can_write=True)

    response = api_client.post(
        reverse("site-visit-api-list"),
        {
            "trip": trip.pk,
            "site": site.pk,
            "planned_day": "2026-05-02",
        },
        format="json",
    )

    assert response.status_code == 400
    assert not SiteVisit.objects.exists()


@pytest.mark.django_db
def test_site_photo_api_uploads_multiple_and_skips_duplicates():
    user = create_user()
    site = create_site()
    api_client, _token = authenticated_api_client(user, can_write=True)

    response = api_client.post(
        reverse("site-photo-api-list"),
        {
            "site": site.pk,
            "photos": [
                image_upload("one.jpg"),
                image_upload("two.jpg"),
            ],
        },
        format="multipart",
    )

    assert response.status_code == 201
    payload = response.json()
    assert len(payload["created"]) == 1
    assert payload["skipped_duplicates"] == 1
    assert SitePhoto.objects.filter(site=site, uploaded_by=user).count() == 1


@pytest.mark.django_db
def test_api_token_create_redirects_to_list_and_shows_plaintext_once(client):
    user = create_user()
    client.force_login(user)

    response = client.post(
        reverse("api_token_create"),
        {"name": "Field app", "can_write": "on"},
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain == [(reverse("api_token_list"), 302)]
    token = ApiToken.objects.get(user=user)
    content = response.content.decode()
    assert "Copy it now; it will not be shown again." in content
    assert f"aat_{token.key_prefix}_" in content
    assert token.key_hash not in content

    response = client.get(reverse("api_token_list"))
    assert f"aat_{token.key_prefix}_" not in response.content.decode()


@pytest.mark.django_db
def test_api_token_create_uses_flatpickr_datetime_field(client):
    user = create_user()
    client.force_login(user)

    response = client.get(reverse("api_token_create"))

    assert response.status_code == 200
    assert b'name="expires_at"' in response.content
    assert b"datetime-picker form-control" in response.content
    assert b'type="datetime-local"' not in response.content


@pytest.mark.django_db
def test_api_token_create_accepts_flatpickr_datetime_value(client):
    user = create_user()
    client.force_login(user)

    response = client.post(
        reverse("api_token_create"),
        {"name": "Field app", "expires_at": "2099-01-01 12:30:00"},
        follow=True,
    )

    assert response.status_code == 200
    token = ApiToken.objects.get(user=user)
    assert timezone.localtime(token.expires_at).strftime("%Y-%m-%d %H:%M:%S") == (
        "2099-01-01 12:30:00"
    )


@pytest.mark.django_db
def test_api_token_list_sorts_and_omits_page_api_docs_button(client):
    user = create_user()
    client.force_login(user)
    create_api_token(user=user, name="Zulu")
    create_api_token(user=user, name="Alpha")

    response = client.get(f"{reverse('api_token_list')}?sort=-name")

    assert response.status_code == 200
    content = response.content.decode()
    assert content.index("Zulu") < content.index("Alpha")
    assert "Swagger docs" in content
    assert "API docs" not in content
    assert "sort=name" in content
    assert "ti-chevron-down" in content
    assert "Prefix" in content


@pytest.mark.django_db
def test_api_token_list_searches_name_and_prefix(client):
    user = create_user()
    client.force_login(user)
    alpha_token, _alpha_plaintext = create_api_token(user=user, name="Alpha")
    beta_token, _beta_plaintext = create_api_token(user=user, name="Beta")

    name_response = client.get(f"{reverse('api_token_list')}?q=Alpha")

    assert name_response.status_code == 200
    name_content = name_response.content.decode()
    assert "Alpha" in name_content
    assert "Beta" not in name_content
    assert name_response.context["search_result_count"] == 1
    assert "Search name or prefix" in name_content

    prefix_response = client.get(
        f"{reverse('api_token_list')}?q={beta_token.key_prefix}",
    )

    assert prefix_response.status_code == 200
    prefix_content = prefix_response.content.decode()
    assert beta_token.key_prefix in prefix_content
    assert alpha_token.key_prefix not in prefix_content


@pytest.mark.django_db
def test_api_token_list_search_is_limited_to_current_user(client):
    user = create_user()
    other_user = create_user(email="other@example.com")
    client.force_login(user)
    create_api_token(user=user, name="Field app")
    create_api_token(user=other_user, name="Other field app")

    response = client.get(f"{reverse('api_token_list')}?q=field")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Field app" in content
    assert "Other field app" not in content
    assert response.context["search_result_count"] == 1


@pytest.mark.django_db
def test_api_token_list_search_empty_state(client):
    user = create_user()
    client.force_login(user)
    create_api_token(user=user, name="Field app")

    response = client.get(f"{reverse('api_token_list')}?q=missing")

    assert response.status_code == 200
    content = response.content.decode()
    assert "No API tokens match your search." in content
    assert "No API tokens have been created." not in content
    assert response.context["search_result_count"] == 0


@pytest.mark.django_db
def test_api_token_list_paginates(client):
    user = create_user()
    client.force_login(user)
    for index in range(30):
        create_api_token(user=user, name=f"Token {index:02d}")

    response = client.get(reverse("api_token_list"))

    assert response.status_code == 200
    assert response.context["is_paginated"] is True
    assert len(response.context["tokens"]) == 25
    assert "Page 1 of 2 (30 total)" in response.content.decode()


@pytest.mark.django_db
def test_api_token_list_respects_per_page(client):
    user = create_user()
    client.force_login(user)
    for index in range(30):
        create_api_token(user=user, name=f"Token {index:02d}")

    response = client.get(f"{reverse('api_token_list')}?per_page=50")

    assert response.status_code == 200
    assert response.context["is_paginated"] is False
    assert len(response.context["tokens"]) == 30
    assert response.context["per_page"] == 50
    assert '<option value="50" selected>' in response.content.decode()


@pytest.mark.django_db
def test_api_token_revoke_preserves_list_query(client):
    user = create_user()
    client.force_login(user)
    token, _plaintext_token = create_api_token(user=user, name="Field app")
    list_query = "q=Field&sort=-name&page=2&per_page=25"

    response = client.post(
        f"{reverse('api_token_revoke', kwargs={'pk': token.pk})}?{list_query}",
    )

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('api_token_list')}?{list_query}"
