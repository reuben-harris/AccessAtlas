import pytest
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    get_user_preference,
    list_sort_preference_key,
)
from access_atlas.jobs.models import Job, JobTemplate
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordVersion,
    Site,
    SiteSyncStatus,
)
from access_atlas.trips.models import SiteVisit, Trip, TripStatus


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", display_name="User")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def site(db):
    return Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )


@pytest.mark.django_db
def test_dashboard_renders(logged_in_client):
    response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Work Overview" in response.content
    assert b"Upcoming Field Work" in response.content
    assert b"Data Attention" in response.content
    assert b'href="/static/css/app.css"' in response.content
    assert b'src="/static/js/theme.js"' in response.content


@pytest.mark.django_db
def test_dashboard_shows_actionable_sections(logged_in_client, user):
    warning_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Warning Site",
        latitude=-41.1,
        longitude=174.1,
    )
    stale_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Stale Site",
        latitude=-41.2,
        longitude=174.2,
        sync_status=SiteSyncStatus.STALE,
    )
    warning_record = AccessRecord.objects.create(site=warning_site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=warning_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.11, -41.11]},
                    "properties": {"access_atlas:type": "site", "name": "Warning"},
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )
    active_trip = Trip.objects.create(
        name="Upcoming Trip",
        start_date="2026-05-10",
        end_date="2026-05-12",
        trip_leader=user,
        status=TripStatus.APPROVED,
    )
    Trip.objects.create(
        name="Cancelled Trip",
        start_date="2026-05-11",
        end_date="2026-05-12",
        trip_leader=user,
        status=TripStatus.CANCELLED,
    )
    site = Site.objects.create(
        source_name="dummy",
        external_id="003",
        code="AA-003",
        name="Job Site",
        latitude=-41.3,
        longitude=174.3,
    )
    Job.objects.create(site=site, title="Unassigned Job")
    planned_job = Job(site=site, title="Planned Job", status="planned")
    planned_job.save(skip_validation=True)

    response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    content = response.content.decode()
    assert active_trip.name in content
    assert "Cancelled Trip" not in content
    assert warning_site.code in content
    assert stale_site.code in content
    assert 'href="/jobs/?status=unassigned"' in content
    assert 'href="/jobs/?status=planned"' in content
    assert f'href="{active_trip.get_absolute_url()}"' in content
    assert f'href="{warning_site.get_access_records_url()}"' in content
    assert f'href="{stale_site.get_absolute_url()}"' in content


@pytest.mark.django_db
def test_core_object_pages_render(logged_in_client, user, site):
    template = JobTemplate.objects.create(title="Inspect sensor")
    job = Job.objects.create(site=site, title="Inspect sensor", template=template)
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    visit = SiteVisit.objects.create(trip=trip, site=site)
    access_record = AccessRecord.objects.create(site=site, name="Road access")

    urls = [
        reverse("site_detail", kwargs={"pk": site.pk}),
        reverse("site_access_records", kwargs={"pk": site.pk}),
        reverse("site_history", kwargs={"pk": site.pk}),
        reverse("access_record_detail", kwargs={"pk": access_record.pk}),
        reverse("access_record_map", kwargs={"pk": access_record.pk}),
        reverse("access_record_revisions", kwargs={"pk": access_record.pk}),
        reverse("access_record_history", kwargs={"pk": access_record.pk}),
        reverse("job_template_detail", kwargs={"pk": template.pk}),
        reverse("job_template_history", kwargs={"pk": template.pk}),
        reverse("job_detail", kwargs={"pk": job.pk}),
        reverse("job_history", kwargs={"pk": job.pk}),
        reverse("trip_detail", kwargs={"pk": trip.pk}),
        reverse("trip_history", kwargs={"pk": trip.pk}),
        reverse("site_visit_detail", kwargs={"pk": visit.pk}),
        reverse("site_visit_history", kwargs={"pk": visit.pk}),
    ]

    for url in urls:
        response = logged_in_client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_global_history_renders_changes(logged_in_client, site):
    response = logged_in_client.get(reverse("global_history"))

    assert response.status_code == 200
    assert b"History" in response.content
    assert site.code.encode() in response.content


@pytest.mark.django_db
def test_global_history_supports_search_and_pagination(logged_in_client):
    for index in range(30):
        Site.objects.create(
            source_name="dummy",
            external_id=f"{index:03d}",
            code=f"AA-{index:03d}",
            name=f"History Site {index}",
            latitude=-41.1,
            longitude=174.1,
        )

    response = logged_in_client.get(reverse("global_history"), {"q": "AA-00"})

    assert response.status_code == 200
    assert response.context["per_page"] == 25
    assert response.context["paginator"].count == 10

    response = logged_in_client.get(reverse("global_history"), {"per_page": 10})

    assert response.status_code == 200
    assert len(response.context["entries"]) == 10
    assert response.context["paginator"].num_pages >= 3


@pytest.mark.django_db
def test_global_history_sorts_and_saves_user_preference(client, user):
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Zulu Site",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Alpha Site",
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("global_history"), {"sort": "object"})

    assert response.status_code == 200
    entries = list(response.context["entries"])
    assert entries[0].object_display == "AA-001 - Alpha Site"
    assert get_user_preference(
        user,
        list_sort_preference_key("history"),
    ) == {"value": "object"}


@pytest.mark.django_db
def test_history_records_get_default_reason(site):
    assert site.history.first().history_change_reason == "Created site"


@pytest.mark.django_db
def test_dummy_feed_requires_bearer_token(client, settings):
    settings.SITE_FEED_TOKEN = "secret"

    response = client.get(reverse("dummy_site_feed"))
    assert response.status_code == 403

    response = client.get(
        reverse("dummy_site_feed"),
        headers={"Authorization": "Bearer secret"},
    )
    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.0"


@pytest.mark.django_db
def test_site_autocomplete_returns_code_and_name(logged_in_client):
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Example Ridge Station",
        latitude=-41.1,
        longitude=174.1,
    )

    response = logged_in_client.get(reverse("autocomplete_sites"), {"q": "Ridge"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "AA-001 - Example Ridge Station"


@pytest.mark.django_db
def test_team_member_autocomplete_prefers_display_name(logged_in_client):
    User.objects.create_user(email="alpha@example.com", display_name="Alpha User")
    User.objects.create_user(email="bravo@example.com")

    response = logged_in_client.get(
        reverse("autocomplete_team_members"),
        {"q": "alpha"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "Alpha User"


@pytest.mark.django_db
def test_team_member_autocomplete_falls_back_to_email(logged_in_client):
    User.objects.create_user(email="fallback@example.com")

    response = logged_in_client.get(
        reverse("autocomplete_team_members"),
        {"q": "fallback"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "fallback@example.com"


@pytest.mark.django_db
def test_job_template_autocomplete_only_returns_active_templates(logged_in_client):
    JobTemplate.objects.create(title="Active Template", is_active=True)
    JobTemplate.objects.create(title="Inactive Template", is_active=False)

    response = logged_in_client.get(
        reverse("autocomplete_job_templates"),
        {"q": "Template"},
    )

    assert response.status_code == 200
    payload = response.json()
    labels = [item["title"] for item in payload["results"]]
    assert "Active Template" in labels
    assert "Inactive Template" not in labels
