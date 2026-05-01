import pytest
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job, JobTemplate
from access_atlas.sites.models import AccessRecord, Site
from access_atlas.trips.models import SiteVisit, Trip


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
    assert b'href="/static/css/app.css"' in response.content
    assert b'src="/static/js/theme.js"' in response.content


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
