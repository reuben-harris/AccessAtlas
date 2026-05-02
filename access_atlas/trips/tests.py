from datetime import date, datetime

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job, JobStatus
from access_atlas.sites.models import Site
from access_atlas.trips.forms import AssignJobForm, SiteVisitForm, TripForm
from access_atlas.trips.models import (
    SiteVisit,
    SiteVisitJob,
    SiteVisitStatus,
    Trip,
    TripStatus,
)
from access_atlas.trips.services import assign_job_to_site_visit


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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")

    assign_job_to_site_visit(site_visit, job)

    job.refresh_from_db()
    assert job.status == "planned"


@pytest.mark.django_db
def test_direct_assignment_create_does_not_change_job_status():
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")

    SiteVisitJob.objects.create(site_visit=site_visit, job=job)

    job.refresh_from_db()
    assert job.status == JobStatus.UNASSIGNED


@pytest.mark.django_db
def test_job_assignment_rolls_back_if_status_update_fails(monkeypatch):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    original_save = Job.save

    def fail_planned_save(self, *args, **kwargs):
        if self.pk == job.pk and self.status == JobStatus.PLANNED:
            raise RuntimeError("status update failed")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(Job, "save", fail_planned_save)

    with pytest.raises(RuntimeError):
        assign_job_to_site_visit(site_visit, job)

    assert not SiteVisitJob.objects.filter(job=job).exists()
    job.refresh_from_db()
    assert job.status == JobStatus.UNASSIGNED


@pytest.mark.django_db
def test_unassigning_planned_job_sets_status_to_unassigned(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    assignment = assign_job_to_site_visit(site_visit, job)
    client.force_login(user)

    response = client.post(reverse("unassign_job", kwargs={"pk": assignment.pk}))

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.status == "unassigned"
    assert job.history.first().history_change_reason == "Unassigned from site visit"
    assert (
        SiteVisitJob.history.first().history_change_reason
        == "Unassigned job from site visit"
    )


@pytest.mark.django_db
def test_assigning_job_records_history_reason(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    client.force_login(user)

    response = client.post(
        reverse("assign_job", kwargs={"pk": site_visit.pk}), {"job": job.pk}
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.status == JobStatus.PLANNED
    assert job.history.first().history_change_reason == "Assigned to site visit"
    assert (
        SiteVisitJob.history.first().history_change_reason
        == "Assigned job to site visit"
    )


@pytest.mark.django_db
def test_trip_list_search_filters_results(client):
    user = User.objects.create_user(email="user@example.com", display_name="Alex")
    Trip.objects.create(
        name="North Island Sweep",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    Trip.objects.create(
        name="South Island Sweep",
        start_date=date(2026, 4, 23),
        end_date=date(2026, 4, 24),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.get(reverse("trip_list"), {"q": "north"})

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert len(object_list) == 1
    assert object_list[0].name == "North Island Sweep"


@pytest.mark.django_db
def test_simple_trip_edit_records_history_reason(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("trip_update", kwargs={"pk": trip.pk}),
        {
            "name": "Updated trip",
            "start_date": "2026-04-21",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "status": TripStatus.DRAFT,
            "notes": "Updated notes.",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.name == "Updated trip"
    assert trip.history.first().history_change_reason == "Updated trip"


@pytest.mark.django_db
def test_invalid_trip_date_edit_shows_error_summary_and_stable_cancel(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("trip_update", kwargs={"pk": trip.pk}),
        {
            "name": "Trip",
            "start_date": "2026-04-23",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "status": TripStatus.DRAFT,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"Review the highlighted fields and try again." in response.content
    assert b"End date must be on or after the start date." in response.content
    assert b'name="end_date"' in response.content
    assert b"is-invalid" in response.content
    assert f'href="{trip.get_absolute_url()}"'.encode() in response.content


@pytest.mark.django_db
def test_invalid_trip_date_create_shows_error_summary(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("trip_create"),
        {
            "name": "Trip",
            "start_date": "2026-04-23",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "status": TripStatus.DRAFT,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"End date must be on or after the start date." in response.content
    assert not Trip.objects.filter(name="Trip").exists()


@pytest.mark.django_db
def test_trip_create_with_missing_date_shows_field_error(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("trip_create"),
        {
            "name": "Trip",
            "start_date": "",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "status": TripStatus.DRAFT,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"Start date: This field is required." in response.content
    assert not Trip.objects.filter(name="Trip").exists()


def test_trip_form_only_offers_draft_and_planned_statuses():
    form = TripForm()

    status_values = [value for value, _label in form.fields["status"].choices]

    assert status_values == [TripStatus.DRAFT, TripStatus.PLANNED]


def test_site_visit_form_marks_site_select_as_searchable():
    form = SiteVisitForm()

    attrs = form.fields["site"].widget.attrs

    assert attrs["data-searchable-select"] == "true"
    assert attrs["data-search-placeholder"] == "Search sites"


@pytest.mark.django_db
def test_assign_job_form_marks_job_select_as_searchable():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )

    form = AssignJobForm(site=site)
    attrs = form.fields["job"].widget.attrs

    assert attrs["data-searchable-select"] == "true"
    assert attrs["data-search-placeholder"] == "Search jobs"


@pytest.mark.django_db
def test_trip_detail_shows_assigned_jobs(client):
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
    job = Job.objects.create(
        site=site,
        title="Replace access panel",
        estimated_duration_minutes=45,
    )
    SiteVisitJob.objects.create(site_visit=site_visit, job=job)
    client.force_login(user)

    response = client.get(reverse("trip_detail", kwargs={"pk": trip.pk}))

    assert response.status_code == 200
    assert b"Jobs" in response.content
    assert b"Replace access panel" in response.content
    assert b"45 min" in response.content


@pytest.mark.django_db
def test_trip_detail_orders_site_visits_by_planned_start(client):
    user = User.objects.create_user(email="user@example.com")
    morning_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Morning Site",
        latitude=-41.1,
        longitude=174.1,
    )
    afternoon_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Afternoon Site",
        latitude=-42.1,
        longitude=175.1,
    )
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    SiteVisit.objects.create(
        trip=trip,
        site=afternoon_site,
        planned_start=timezone.make_aware(datetime(2026, 4, 21, 14, 0)),
        planned_end=timezone.make_aware(datetime(2026, 4, 21, 16, 0)),
    )
    SiteVisit.objects.create(
        trip=trip,
        site=morning_site,
        planned_start=timezone.make_aware(datetime(2026, 4, 21, 9, 0)),
        planned_end=timezone.make_aware(datetime(2026, 4, 21, 11, 0)),
    )
    client.force_login(user)

    response = client.get(reverse("trip_detail", kwargs={"pk": trip.pk}))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index("Morning Site") < content.index("Afternoon Site")
    assert "21 Apr 2026 09:00" in content


@pytest.mark.django_db
def test_site_visit_validation_requires_end_after_start():
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit(
        trip=trip,
        site=site,
        planned_start=timezone.make_aware(datetime(2026, 4, 21, 11, 0)),
        planned_end=timezone.make_aware(datetime(2026, 4, 21, 9, 0)),
    )

    with pytest.raises(ValidationError) as exc:
        site_visit.full_clean()

    assert "Planned end must be after planned start." in str(exc.value)


@pytest.mark.django_db
def test_site_visit_validation_requires_planned_times_within_trip_dates():
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit(
        trip=trip,
        site=site,
        planned_start=timezone.make_aware(datetime(2026, 4, 23, 9, 0)),
    )

    with pytest.raises(ValidationError) as exc:
        site_visit.full_clean()

    assert "Must be between 2026-04-21 and 2026-04-22." in str(exc.value)


@pytest.mark.django_db
def test_invalid_site_visit_date_shows_error_summary_and_keeps_values(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("site_visit_create", kwargs={"trip_pk": trip.pk}),
        {
            "site": site.pk,
            "planned_start_0": "2026-04-23",
            "planned_start_1": "09:00",
            "planned_end_0": "2026-04-23",
            "planned_end_1": "10:00",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"Review the highlighted fields and try again." in response.content
    assert (
        b"Planned start: Must be between 2026-04-21 and 2026-04-22." in response.content
    )
    assert (
        b"Planned end: Must be between 2026-04-21 and 2026-04-22." in response.content
    )
    assert b"Must be between 2026-04-21 and 2026-04-22." in response.content
    assert b'name="planned_start_0"' in response.content
    assert b'value="2026-04-23"' in response.content
    assert b'value="09:00"' in response.content
    assert b'value="10:00"' in response.content
    assert b"is-invalid" in response.content
    assert not SiteVisit.objects.filter(trip=trip).exists()


@pytest.mark.django_db
def test_invalid_site_visit_time_order_shows_error_summary_and_keeps_values(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("site_visit_create", kwargs={"trip_pk": trip.pk}),
        {
            "site": site.pk,
            "planned_start_0": "2026-04-22",
            "planned_start_1": "11:00",
            "planned_end_0": "2026-04-22",
            "planned_end_1": "09:00",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"Planned end: Planned end must be after planned start." in response.content
    assert b'value="2026-04-22"' in response.content
    assert b'value="11:00"' in response.content
    assert b'value="09:00"' in response.content
    assert not SiteVisit.objects.filter(trip=trip).exists()


@pytest.mark.django_db
def test_site_visit_create_allows_blank_planned_start(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("site_visit_create", kwargs={"trip_pk": trip.pk}),
        {
            "site": site.pk,
            "planned_start_0": "",
            "planned_start_1": "",
            "planned_end_0": "",
            "planned_end_1": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 302
    site_visit = SiteVisit.objects.get(trip=trip)
    assert site_visit.planned_start is None
    assert site_visit.planned_end is None


@pytest.mark.django_db
def test_site_visit_create_saves_planned_times(client):
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
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.post(
        reverse("site_visit_create", kwargs={"trip_pk": trip.pk}),
        {
            "site": site.pk,
            "planned_start_0": "2026-04-21",
            "planned_start_1": "09:00",
            "planned_end_0": "2026-04-21",
            "planned_end_1": "10:30",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 302
    site_visit = SiteVisit.objects.get(trip=trip)
    assert site_visit.planned_start is not None
    assert site_visit.planned_end is not None


@pytest.mark.django_db
def test_site_visit_create_does_not_show_trip_date_hint_on_first_load(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)

    response = client.get(reverse("site_visit_create", kwargs={"trip_pk": trip.pk}))

    assert response.status_code == 200
    assert b"Select a date and time within the trip dates." not in response.content
    assert b"Unable to save changes" not in response.content


@pytest.mark.django_db
def test_terminal_trip_detail_disables_add_site_visit(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.COMPLETED,
    )
    client.force_login(user)

    response = client.get(reverse("trip_detail", kwargs={"pk": trip.pk}))

    assert response.status_code == 200
    assert b"Add site visit" in response.content
    create_url = reverse("site_visit_create", kwargs={"trip_pk": trip.pk}).encode()
    assert create_url not in response.content
    assert (
        b"Site visits cannot be added to completed or cancelled trips."
        in response.content
    )


@pytest.mark.django_db
def test_terminal_trip_blocks_site_visit_create(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.COMPLETED,
    )
    client.force_login(user)

    response = client.get(reverse("site_visit_create", kwargs={"trip_pk": trip.pk}))

    assert response.status_code == 302
    assert response.url == trip.get_absolute_url()


@pytest.mark.django_db
def test_cancel_trip_returns_planned_jobs_and_skips_site_visits(client):
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
        status=TripStatus.PLANNED,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    assign_job_to_site_visit(site_visit, job)
    client.force_login(user)

    response = client.post(reverse("trip_cancel", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    site_visit.refresh_from_db()
    job.refresh_from_db()
    assert trip.status == TripStatus.CANCELLED
    assert site_visit.status == SiteVisitStatus.SKIPPED
    assert job.status == JobStatus.UNASSIGNED
    assert not SiteVisitJob.objects.filter(job=job).exists()
    assert trip.history.first().history_change_reason == "Cancelled trip"
    assert (
        site_visit.history.first().history_change_reason
        == "Skipped during trip cancellation"
    )
    assert (
        job.history.first().history_change_reason
        == "Returned to unassigned during trip cancellation"
    )


@pytest.mark.django_db
def test_cancel_trip_blocks_when_child_work_has_moved_forward(client):
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
        status=TripStatus.PLANNED,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    SiteVisitJob.objects.create(site_visit=site_visit, job=job)
    job.status = JobStatus.COMPLETED
    job.save(update_fields=["status", "updated_at"])
    client.force_login(user)

    response = client.post(reverse("trip_cancel", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    job.refresh_from_db()
    assert trip.status == TripStatus.PLANNED
    assert job.status == JobStatus.COMPLETED
    assert SiteVisitJob.objects.filter(job=job).exists()


@pytest.mark.django_db
def test_close_trip_resolves_site_visits_and_jobs(client):
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
        status=TripStatus.PLANNED,
    )
    completed_visit = SiteVisit.objects.create(trip=trip, site=site)
    returned_visit = SiteVisit.objects.create(trip=trip, site=site)
    cancelled_visit = SiteVisit.objects.create(trip=trip, site=site)
    completed_job = Job.objects.create(site=site, title="Complete")
    returned_job = Job.objects.create(site=site, title="Return")
    cancelled_job = Job.objects.create(site=site, title="Cancel")
    completed_assignment = SiteVisitJob.objects.create(
        site_visit=completed_visit, job=completed_job
    )
    returned_assignment = SiteVisitJob.objects.create(
        site_visit=returned_visit, job=returned_job
    )
    cancelled_assignment = SiteVisitJob.objects.create(
        site_visit=cancelled_visit, job=cancelled_job
    )
    client.force_login(user)

    response = client.post(
        reverse("trip_close", kwargs={"pk": trip.pk}),
        {
            f"site_visit_{completed_visit.pk}": SiteVisitStatus.COMPLETED,
            f"site_visit_{returned_visit.pk}": SiteVisitStatus.SKIPPED,
            f"site_visit_{cancelled_visit.pk}": SiteVisitStatus.COMPLETED,
            f"job_{completed_assignment.pk}_outcome": "completed",
            f"job_{completed_assignment.pk}_cancelled_reason": "",
            f"job_{returned_assignment.pk}_outcome": "return",
            f"job_{returned_assignment.pk}_cancelled_reason": "",
            f"job_{cancelled_assignment.pk}_outcome": "cancelled",
            f"job_{cancelled_assignment.pk}_cancelled_reason": "No longer needed.",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    completed_visit.refresh_from_db()
    returned_visit.refresh_from_db()
    cancelled_job.refresh_from_db()
    returned_job.refresh_from_db()
    completed_job.refresh_from_db()
    assert trip.status == TripStatus.COMPLETED
    assert completed_visit.status == SiteVisitStatus.COMPLETED
    assert returned_visit.status == SiteVisitStatus.SKIPPED
    assert completed_job.status == JobStatus.COMPLETED
    assert returned_job.status == JobStatus.UNASSIGNED
    assert cancelled_job.status == JobStatus.CANCELLED
    assert cancelled_job.cancelled_reason == "No longer needed."
    assert not SiteVisitJob.objects.filter(job=returned_job).exists()
    assert trip.history.first().history_change_reason == "Closed trip"
    assert (
        completed_visit.history.first().history_change_reason
        == "Resolved during trip closeout"
    )
    assert (
        completed_job.history.first().history_change_reason
        == "Completed during trip closeout"
    )
    assert (
        returned_job.history.first().history_change_reason
        == "Returned to unassigned during trip closeout"
    )
    assert (
        cancelled_job.history.first().history_change_reason
        == "Cancelled during trip closeout"
    )


@pytest.mark.django_db
def test_close_trip_requires_reason_for_cancelled_jobs(client):
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
        status=TripStatus.PLANNED,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Cancel")
    assignment = assign_job_to_site_visit(site_visit, job)
    client.force_login(user)

    response = client.post(
        reverse("trip_close", kwargs={"pk": trip.pk}),
        {
            f"site_visit_{site_visit.pk}": SiteVisitStatus.COMPLETED,
            f"job_{assignment.pk}_outcome": "cancelled",
            f"job_{assignment.pk}_cancelled_reason": "",
        },
    )

    assert response.status_code == 200
    trip.refresh_from_db()
    job.refresh_from_db()
    assert trip.status == TripStatus.PLANNED
    assert job.status == JobStatus.PLANNED


@pytest.mark.django_db
def test_terminal_trip_detail_disables_close_and_cancel_actions(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
        status=TripStatus.COMPLETED,
    )
    client.force_login(user)

    response = client.get(reverse("trip_detail", kwargs={"pk": trip.pk}))

    assert response.status_code == 200
    assert (
        reverse("trip_cancel", kwargs={"pk": trip.pk}).encode() not in response.content
    )
    assert (
        reverse("trip_close", kwargs={"pk": trip.pk}).encode() not in response.content
    )
    assert b"cannot be cancelled" in response.content
    assert b"cannot be closed again" in response.content


@pytest.mark.django_db
def test_terminal_trip_close_and_cancel_urls_redirect(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
        status=TripStatus.CANCELLED,
    )
    client.force_login(user)

    close_response = client.get(reverse("trip_close", kwargs={"pk": trip.pk}))
    cancel_response = client.get(reverse("trip_cancel", kwargs={"pk": trip.pk}))

    assert close_response.status_code == 302
    assert close_response.url == trip.get_absolute_url()
    assert cancel_response.status_code == 302
    assert cancel_response.url == trip.get_absolute_url()
