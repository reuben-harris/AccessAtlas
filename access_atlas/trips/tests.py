import pytest
from django.core.exceptions import ValidationError

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job
from access_atlas.sites.models import Site
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip


@pytest.mark.django_db
def test_job_assignment_requires_matching_site():
    user = User.objects.create_user(email="user@example.com")
    site_a = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )
    site_b = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Site B",
        latitude=-42.1,
        longitude=175.1,
    )
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site_a)
    job = Job.objects.create(site=site_b, title="Wrong site job")

    assignment = SiteVisitJob(site_visit=site_visit, job=job)

    with pytest.raises(ValidationError):
        assignment.full_clean()


@pytest.mark.django_db
def test_assigning_job_sets_status_to_planned():
    user = User.objects.create_user(email="user@example.com")
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")

    SiteVisitJob.objects.create(site_visit=site_visit, job=job)

    job.refresh_from_db()
    assert job.status == "planned"
