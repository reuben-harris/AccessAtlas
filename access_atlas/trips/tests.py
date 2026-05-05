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
    TripApproval,
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
def test_assigning_job_sets_status_to_assigned():
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
    assert job.status == "assigned"


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
def test_job_assignment_requires_non_terminal_trip():
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
        status=TripStatus.COMPLETED,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")

    with pytest.raises(ValidationError, match="completed or cancelled trips"):
        assign_job_to_site_visit(site_visit, job)

    assert not SiteVisitJob.objects.filter(site_visit=site_visit, job=job).exists()
    job.refresh_from_db()
    assert job.status == JobStatus.UNASSIGNED


@pytest.mark.django_db
def test_terminal_trip_site_visit_detail_hides_assignment_controls(client):
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
        status=TripStatus.COMPLETED,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    client.force_login(user)

    response = client.get(reverse("site_visit_detail", kwargs={"pk": site_visit.pk}))

    assert response.status_code == 200
    assert b"Assign Job" not in response.content
    assign_url = reverse("assign_job", kwargs={"pk": site_visit.pk}).encode()
    assert assign_url not in response.content
    assert (
        b"Jobs cannot be assigned to site visits on completed or cancelled trips."
        in response.content
    )


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

    def fail_assigned_save(self, *args, **kwargs):
        if self.pk == job.pk and self.status == JobStatus.ASSIGNED:
            raise RuntimeError("status update failed")
        return original_save(self, *args, **kwargs)

    monkeypatch.setattr(Job, "save", fail_assigned_save)

    with pytest.raises(RuntimeError):
        assign_job_to_site_visit(site_visit, job)

    assert not SiteVisitJob.objects.filter(job=job).exists()
    job.refresh_from_db()
    assert job.status == JobStatus.UNASSIGNED


@pytest.mark.django_db
def test_unassigning_assigned_job_sets_status_to_unassigned(client):
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
    assert job.status == JobStatus.ASSIGNED
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
def test_trip_gantt_view_separates_scheduled_and_unscheduled_site_visits(client):
    user = User.objects.create_user(email="user@example.com")
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Scheduled Site",
        latitude=-41.1,
        longitude=174.1,
    )
    unscheduled_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Unscheduled Site",
        latitude=-42.1,
        longitude=175.1,
    )
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    empty_trip = Trip.objects.create(
        name="Trip without visits",
        start_date=date(2026, 4, 23),
        end_date=date(2026, 4, 24),
        trip_leader=user,
    )
    SiteVisit.objects.create(
        trip=trip,
        site=site,
        planned_start=timezone.make_aware(datetime(2026, 4, 21, 9, 0)),
        planned_end=timezone.make_aware(datetime(2026, 4, 21, 10, 0)),
    )
    SiteVisit.objects.create(trip=trip, site=unscheduled_site)
    client.force_login(user)

    response = client.get(reverse("trip_gantt"))

    assert response.status_code == 200
    gantt_rows = response.context["trip_gantt_rows"]
    unscheduled_visits = response.context["unscheduled_site_visits"]
    assert len(gantt_rows) == 2
    assert gantt_rows[0]["tripName"] == "Trip"
    assert len(gantt_rows[0]["siteVisits"]) == 1
    assert gantt_rows[0]["siteVisits"][0]["siteCode"] == "AA-001"
    assert gantt_rows[1]["tripId"] == empty_trip.pk
    assert gantt_rows[1]["siteVisits"] == []
    assert len(unscheduled_visits) == 1
    assert unscheduled_visits[0]["siteCode"] == "AA-002"


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
            "notes": "Updated notes.",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.name == "Updated trip"
    assert trip.history.first().history_change_reason == "Updated trip"


@pytest.mark.django_db
def test_submit_trip_for_approval_sets_submitted_state(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.DRAFT,
    )
    client.force_login(user)

    response = client.post(reverse("trip_submit", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.status == TripStatus.SUBMITTED
    assert trip.submitted_by == user
    assert trip.submitted_at is not None
    assert trip.approval_round == 1


@pytest.mark.django_db
def test_submitted_trip_cannot_be_resubmitted_for_approval(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.SUBMITTED,
        approval_round=1,
    )
    client.force_login(user)

    response = client.post(reverse("trip_submit", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 1


@pytest.mark.django_db
def test_trip_leader_cannot_approve_trip(client):
    user = User.objects.create_user(email="leader@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.SUBMITTED,
        approval_round=1,
    )
    client.force_login(user)

    response = client.post(reverse("trip_approve", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.status == TripStatus.SUBMITTED
    assert not TripApproval.objects.filter(trip=trip).exists()


@pytest.mark.django_db
def test_trip_approval_moves_trip_to_approved_and_records_approver(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=leader,
        status=TripStatus.SUBMITTED,
        approval_round=1,
    )
    client.force_login(approver)

    response = client.post(reverse("trip_approve", kwargs={"pk": trip.pk}))

    assert response.status_code == 302
    trip.refresh_from_db()
    approval = TripApproval.objects.get(trip=trip, approver=approver)
    assert trip.status == TripStatus.APPROVED
    assert trip.approved_at is not None
    assert approval.approval_round == 1


@pytest.mark.django_db
def test_approved_trip_edit_requires_confirmation_and_resubmits(client):
    user = User.objects.create_user(email="user@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    client.force_login(user)

    initial_response = client.post(
        reverse("trip_update", kwargs={"pk": trip.pk}),
        {
            "name": "Updated trip",
            "start_date": "2026-04-21",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "notes": "Updated notes.",
        },
    )

    assert initial_response.status_code == 200
    assert b"Approval reset" in initial_response.content
    assert Trip.objects.get(pk=trip.pk).status == TripStatus.APPROVED

    response = client.post(
        reverse("trip_update", kwargs={"pk": trip.pk}),
        {
            "name": "Updated trip",
            "start_date": "2026-04-21",
            "end_date": "2026-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "notes": "Updated notes.",
            "confirm_trip_approval_reset": "on",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    assert trip.name == "Updated trip"
    assert trip.status == TripStatus.SUBMITTED
    assert trip.submitted_by == user
    assert trip.approval_round == 2


@pytest.mark.django_db
def test_assigning_job_to_approved_trip_requires_confirmation_and_resubmits(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
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
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    client.force_login(leader)

    initial_response = client.post(
        reverse("assign_job", kwargs={"pk": site_visit.pk}),
        {"job": job.pk},
    )

    assert initial_response.status_code == 200
    assert b"Approval reset" in initial_response.content
    assert not SiteVisitJob.objects.filter(job=job).exists()

    response = client.post(
        reverse("assign_job", kwargs={"pk": site_visit.pk}),
        {"job": job.pk, "confirm_trip_approval_reset": "1"},
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    job.refresh_from_db()
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 2
    assert job.status == JobStatus.ASSIGNED


@pytest.mark.django_db
def test_updating_site_visit_on_approved_trip_requires_confirmation_and_resubmits(
    client,
):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
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
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(
        trip=trip,
        site=site,
        planned_day=date(2026, 4, 21),
    )
    client.force_login(leader)

    initial_response = client.post(
        reverse("site_visit_update", kwargs={"pk": site_visit.pk}),
        {
            "site": site.pk,
            "planned_day": "2026-04-22",
            "planned_start_time": "",
            "planned_end_time": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "Updated note",
        },
    )

    assert initial_response.status_code == 200
    assert b"Approval reset" in initial_response.content

    response = client.post(
        reverse("site_visit_update", kwargs={"pk": site_visit.pk}),
        {
            "site": site.pk,
            "planned_day": "2026-04-22",
            "planned_start_time": "",
            "planned_end_time": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "Updated note",
            "confirm_trip_approval_reset": "on",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    site_visit.refresh_from_db()
    assert site_visit.planned_day == date(2026, 4, 22)
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 2


@pytest.mark.django_db
def test_unassigning_job_from_approved_trip_requires_confirmation_and_resubmits(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
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
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    assignment = assign_job_to_site_visit(site_visit, job)
    client.force_login(leader)

    initial_response = client.post(
        reverse("unassign_job", kwargs={"pk": assignment.pk}),
    )

    assert initial_response.status_code == 200
    assert b"Approval reset" in initial_response.content

    response = client.post(
        reverse("unassign_job", kwargs={"pk": assignment.pk}),
        {"confirm_trip_approval_reset": "1"},
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    job.refresh_from_db()
    assert not SiteVisitJob.objects.filter(pk=assignment.pk).exists()
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 2
    assert job.status == JobStatus.UNASSIGNED


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
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Unable to save changes" in response.content
    assert b"Start date: This field is required." in response.content
    assert not Trip.objects.filter(name="Trip").exists()


def test_trip_form_does_not_offer_status_field():
    form = TripForm()
    assert "status" not in form.fields


@pytest.mark.django_db
def test_trip_form_rejects_trips_longer_than_one_year():
    user = User.objects.create_user(email="user@example.com")

    form = TripForm(
        data={
            "name": "Long Trip",
            "start_date": "2026-04-21",
            "end_date": "2027-04-22",
            "trip_leader": user.pk,
            "team_members": [],
            "notes": "",
        }
    )

    assert form.is_valid() is False
    assert form.errors["end_date"] == ["Trips cannot be longer than one year."]


@pytest.mark.django_db
def test_trip_form_allows_one_year_trip():
    user = User.objects.create_user(email="user@example.com")

    form = TripForm(
        data={
            "name": "One Year Trip",
            "start_date": "2026-04-21",
            "end_date": "2027-04-21",
            "trip_leader": user.pk,
            "team_members": [],
            "notes": "",
        }
    )

    assert form.is_valid() is True


def test_site_visit_form_marks_site_select_as_searchable():
    form = SiteVisitForm()

    widget = form.fields["site"].widget

    assert widget.url == "autocomplete_sites"
    assert widget.label_field == "label"


@pytest.mark.django_db
def test_site_visit_form_uses_trip_day_choices():
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 23),
        trip_leader=user,
    )

    form = SiteVisitForm(trip=trip)

    assert form.fields["planned_day"].choices == [
        ("2026-04-21", "Tue 21 Apr 2026"),
        ("2026-04-22", "Wed 22 Apr 2026"),
        ("2026-04-23", "Thu 23 Apr 2026"),
    ]


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
    widget = form.fields["job"].widget

    assert widget.url == "autocomplete_unassigned_jobs"
    assert widget.label_field == "label"


@pytest.mark.django_db
def test_trip_create_includes_tomselect_media(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("trip_create"))

    assert response.status_code == 200
    assert b"django_tomselect/js/django-tomselect.js" in response.content


@pytest.mark.django_db
def test_site_visit_create_does_not_warn_about_virtual_site_label(client, caplog):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)
    caplog.set_level("WARNING")

    response = client.get(reverse("site_visit_create", kwargs={"trip_pk": trip.pk}))

    assert response.status_code == 200
    assert "value_fields ['label'] are not concrete database columns" not in caplog.text


@pytest.mark.django_db
def test_site_visit_detail_includes_tomselect_media(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
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

    response = client.get(reverse("site_visit_detail", kwargs={"pk": site_visit.pk}))

    assert response.status_code == 200
    assert b"django_tomselect/js/django-tomselect.js" in response.content


@pytest.mark.django_db
def test_trip_form_invalid_post_keeps_selected_team_members(client):
    leader = User.objects.create_user(email="leader@example.com")
    teammate = User.objects.create_user(email="teammate@example.com")
    client.force_login(leader)

    response = client.post(
        reverse("trip_create"),
        {
            "name": "Trip",
            "start_date": "",
            "end_date": "2026-04-22",
            "trip_leader": leader.pk,
            "team_members": [teammate.pk],
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert response.context["form"]["team_members"].value() == [str(teammate.pk)]


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
    assert "21 Apr 2026" in content
    assert "09:00" in content
    assert "11:00" in content


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
def test_site_visit_validation_requires_planned_day():
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
    site_visit = SiteVisit(trip=trip, site=site)

    with pytest.raises(ValidationError) as exc:
        site_visit.full_clean()

    assert "Choose a trip day." in str(exc.value)


@pytest.mark.django_db
def test_invalid_site_visit_date_shows_inline_error_and_keeps_values(client):
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
            "planned_day": "2026-04-23",
            "planned_start_time": "09:00",
            "planned_end_time": "10:00",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"Must be between 2026-04-21 and 2026-04-22." in response.content
    assert b'name="planned_day"' in response.content
    assert b'value="09:00"' in response.content
    assert b'value="10:00"' in response.content
    assert not SiteVisit.objects.filter(trip=trip).exists()


@pytest.mark.django_db
def test_invalid_site_visit_time_order_shows_inline_error_and_keeps_values(client):
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
            "planned_day": "2026-04-22",
            "planned_start_time": "11:00",
            "planned_end_time": "09:00",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert b"End time must be after start time." in response.content
    assert b'value="2026-04-22"' in response.content
    assert b'value="11:00"' in response.content
    assert b'value="09:00"' in response.content
    assert not SiteVisit.objects.filter(trip=trip).exists()


@pytest.mark.django_db
def test_missing_site_visit_day_shows_single_inline_required_error(client):
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
            "planned_day": "",
            "planned_start_time": "",
            "planned_end_time": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert response.content.count(b"This field is required.") == 2
    assert b"Choose a trip day." not in response.content
    assert b"Visit day: This field is required." in response.content
    assert b"Unable to save changes" in response.content


@pytest.mark.django_db
def test_invalid_site_visit_post_keeps_selected_site(client):
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
            "planned_day": "",
            "planned_start_time": "",
            "planned_end_time": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 200
    assert response.context["form"]["site"].value() == str(site.pk)


@pytest.mark.django_db
def test_site_visit_create_allows_blank_times(client):
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
            "planned_day": "2026-04-21",
            "planned_start_time": "",
            "planned_end_time": "",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 302
    site_visit = SiteVisit.objects.get(trip=trip)
    assert site_visit.planned_day == date(2026, 4, 21)
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
            "planned_day": "2026-04-21",
            "planned_start_time": "09:00",
            "planned_end_time": "10:30",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 302
    site_visit = SiteVisit.objects.get(trip=trip)
    assert site_visit.planned_day == date(2026, 4, 21)
    assert site_visit.planned_start is not None
    assert site_visit.planned_end is not None


@pytest.mark.django_db
def test_site_visit_update_moves_visit_day_and_keeps_assignment(client):
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
    site_visit = SiteVisit.objects.create(
        trip=trip,
        site=site,
        planned_day=date(2026, 4, 21),
        planned_start=timezone.make_aware(datetime(2026, 4, 21, 9, 0)),
        planned_end=timezone.make_aware(datetime(2026, 4, 21, 10, 0)),
    )
    job = Job.objects.create(site=site, title="Assigned job")
    SiteVisitJob.objects.create(site_visit=site_visit, job=job)
    client.force_login(user)

    response = client.post(
        reverse("site_visit_update", kwargs={"pk": site_visit.pk}),
        {
            "site": site.pk,
            "planned_day": "2026-04-22",
            "planned_start_time": "11:00",
            "planned_end_time": "12:00",
            "status": SiteVisitStatus.PLANNED,
            "notes": "",
        },
    )

    assert response.status_code == 302
    site_visit.refresh_from_db()
    assert site_visit.planned_day == date(2026, 4, 22)
    assert SiteVisitJob.objects.filter(site_visit=site_visit, job=job).exists()


@pytest.mark.django_db
def test_unassigned_job_autocomplete_filters_by_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
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
    visible_job = Job.objects.create(
        site=site_a,
        title="Visible job",
        status=JobStatus.UNASSIGNED,
    )
    hidden_job = Job.objects.create(
        site=site_b,
        title="Hidden job",
        status=JobStatus.UNASSIGNED,
    )
    assigned_job = Job.objects.create(
        site=site_a,
        title="Assigned job",
        status=JobStatus.UNASSIGNED,
    )
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site_a)
    assign_job_to_site_visit(site_visit, assigned_job)

    response = client.get(
        reverse("autocomplete_unassigned_jobs"),
        {"q": "job", "f": f"__const__site_id={site_a.pk}"},
    )

    assert response.status_code == 200
    payload = response.json()
    labels = [item["label"] for item in payload["results"]]
    assert visible_job.title in labels
    assert hidden_job.title not in labels
    assert assigned_job.title not in labels


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
def test_approved_trip_site_visit_form_shows_approval_reset_checkbox(client):
    user = User.objects.create_user(email="user@example.com")
    Site.objects.create(
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
        status=TripStatus.APPROVED,
    )
    client.force_login(user)

    response = client.get(reverse("site_visit_create", kwargs={"trip_pk": trip.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert (
        "Making changes to this approved trip will send it back to waiting "
        "for approval." in content
    )
    assert 'name="confirm_trip_approval_reset"' in content
    assert "I understand this change will send the trip back for approval." in content


@pytest.mark.django_db
def test_trip_history_accepts_custom_per_page(client):
    user = User.objects.create_user(email="user@example.com")
    trip = Trip.objects.create(
        name="Trip",
        start_date=date(2026, 4, 21),
        end_date=date(2026, 4, 22),
        trip_leader=user,
    )
    client.force_login(user)
    for index in range(12):
        trip.name = f"Trip {index}"
        trip.save()

    response = client.get(
        reverse("trip_history", kwargs={"pk": trip.pk}),
        {"per_page": 10},
    )

    assert response.status_code == 200
    assert response.context["per_page"] == 10
    assert response.context["paginator"].num_pages == 2


@pytest.mark.django_db
def test_site_visit_history_defaults_to_25_entries_per_page(client):
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
    client.force_login(user)
    for index in range(30):
        site_visit.notes = f"History {index}"
        site_visit.save()

    response = client.get(reverse("site_visit_history", kwargs={"pk": site_visit.pk}))

    assert response.status_code == 200
    assert response.context["per_page"] == 25
    assert response.context["paginator"].num_pages == 2


@pytest.mark.django_db
def test_cancel_trip_returns_assigned_jobs_and_skips_site_visits(client):
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
        status=TripStatus.SUBMITTED,
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
        status=TripStatus.SUBMITTED,
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
    assert trip.status == TripStatus.SUBMITTED
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
        status=TripStatus.SUBMITTED,
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
        status=TripStatus.SUBMITTED,
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
    assert trip.status == TripStatus.SUBMITTED
    assert job.status == JobStatus.ASSIGNED


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
