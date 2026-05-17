import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from django.utils.dateparse import parse_date

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    get_user_preference,
    list_filter_preference_key,
    list_sort_preference_key,
    set_user_preference,
)
from access_atlas.core.list_filters import FILTER_STATE_PARAM, FILTER_STATE_UPDATE
from access_atlas.core.test_utils import parse_json_script
from access_atlas.jobs.forms import (
    ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON,
    ASSIGNED_JOB_SITE_DISABLED_REASON,
    AssignWorkProgrammeJobForm,
    JobBulkEditForm,
    JobForm,
    JobFromTemplateForm,
)
from access_atlas.jobs.imports import parse_job_import_csv
from access_atlas.jobs.models import (
    Job,
    JobStatus,
    JobTemplate,
    Priority,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)
from access_atlas.jobs.services import (
    assign_job_to_work_programme,
    assign_jobs_to_work_programme,
    bulk_edit_jobs,
    create_job_from_template,
)
from access_atlas.jobs.template_imports import parse_job_template_import_csv
from access_atlas.sites.models import Site
from access_atlas.trips.models import SiteVisit, Trip, TripApproval, TripStatus
from access_atlas.trips.services import assign_job_to_site_visit

IMPORT_FIX_ALERT = (
    "Upload a corrected CSV, or fix referenced app data and refresh the review "
    "before importing."
)


def create_site(code="AA-001"):
    return Site.objects.create(
        source_name="dummy",
        external_id=code,
        code=code,
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )


def assert_import_create_button_disabled(content, label):
    assert IMPORT_FIX_ALERT in content
    assert label in content
    assert 'type="button" disabled' in content


@pytest.mark.django_db
def test_create_job_from_template_copies_template_and_requirements():
    site = create_site()
    template = JobTemplate.objects.create(
        title="Replace sensor",
        description="Replace the field sensor.",
        estimated_duration_minutes=90,
    )
    TemplateRequirement.objects.create(
        job_template=template,
        name="Sensor cable",
        quantity="1",
    )

    job = create_job_from_template(site=site, template=template)

    assert job.site == site
    assert job.template == template
    assert job.title == "Replace sensor"
    assert job.estimated_duration_minutes == 90
    assert job.requirements.count() == 1
    assert job.requirements.get().name == "Sensor cable"
    assert job.history.first().history_change_reason == "Created job from template"
    assert (
        job.requirements.get().history.first().history_change_reason
        == "Copied requirement from job template"
    )

    template.title = "Changed template"
    template.save()
    job.refresh_from_db()
    assert job.title == "Replace sensor"


@pytest.mark.django_db
def test_create_job_from_template_rolls_back_when_requirement_copy_fails(monkeypatch):
    site = create_site()
    template = JobTemplate.objects.create(title="Replace sensor")
    TemplateRequirement.objects.create(job_template=template, name="Sensor cable")

    def fail_requirement_save(self, *args, **kwargs):
        raise RuntimeError("Requirement copy failed.")

    monkeypatch.setattr(Requirement, "save", fail_requirement_save)

    with pytest.raises(RuntimeError, match="Requirement copy failed."):
        create_job_from_template(site=site, template=template)

    assert Job.objects.count() == 0
    assert Requirement.objects.count() == 0


@pytest.mark.django_db
def test_job_created_manually_is_unassigned_by_default():
    site = create_site()

    job = Job.objects.create(site=site, title="Inspect cabinet")

    assert job.status == "unassigned"


@pytest.mark.django_db
def test_job_template_title_must_be_unique_case_insensitive():
    JobTemplate.objects.create(title="Replace Sensor")
    duplicate = JobTemplate(title="replace sensor")

    with pytest.raises(ValidationError):
        duplicate.full_clean()


@pytest.mark.django_db
def test_job_template_title_unique_constraint_is_case_insensitive():
    JobTemplate.objects.create(title="Replace Sensor")

    with pytest.raises(IntegrityError):
        JobTemplate.objects.create(title="replace sensor")


@pytest.mark.django_db
def test_work_programme_name_must_be_unique_case_insensitive():
    WorkProgramme.objects.create(
        name="2026 Field Work",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    duplicate = WorkProgramme(
        name="2026 field work",
        start_date="2026-02-01",
        end_date="2026-11-30",
    )

    with pytest.raises(ValidationError):
        duplicate.full_clean()


@pytest.mark.django_db
def test_work_programme_end_date_cannot_be_before_start_date():
    work_programme = WorkProgramme(
        name="2026 Field Work",
        start_date="2026-12-31",
        end_date="2026-01-01",
    )

    with pytest.raises(ValidationError):
        work_programme.full_clean()


@pytest.mark.django_db
def test_work_programme_dates_are_optional():
    undated_programme = WorkProgramme(name="Draft Programme")
    start_only_programme = WorkProgramme(
        name="Start Only Programme",
        start_date="2026-01-01",
    )
    due_only_programme = WorkProgramme(
        name="Due Only Programme",
        end_date="2026-12-31",
    )

    undated_programme.full_clean()
    start_only_programme.full_clean()
    due_only_programme.full_clean()

    assert undated_programme.date_range_label() == "dates not set"
    assert start_only_programme.date_range_label() == "starts 2026-01-01"
    assert due_only_programme.date_range_label() == "due 2026-12-31"


@pytest.mark.django_db
def test_work_programme_list_and_detail_render(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    work_programme = WorkProgramme.objects.create(
        name="2026 Field Work",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    list_response = client.get(reverse("work_programme_list"))
    detail_response = client.get(work_programme.get_absolute_url())

    assert list_response.status_code == 200
    assert "2026 Field Work" in list_response.content.decode()
    assert detail_response.status_code == 200
    assert "Due Date" in detail_response.content.decode()


@pytest.mark.django_db
def test_work_programme_list_and_detail_render_missing_dates(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    work_programme = WorkProgramme.objects.create(name="Draft Programme")

    list_response = client.get(reverse("work_programme_list"))
    detail_response = client.get(work_programme.get_absolute_url())

    assert list_response.status_code == 200
    assert "Draft Programme" in list_response.content.decode()
    assert detail_response.status_code == 200
    assert '<dd class="col-sm-9">-</dd>' in detail_response.content.decode()


@pytest.mark.django_db
def test_work_programme_create_uses_flatpickr_date_fields(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("work_programme_create"))

    assert response.status_code == 200
    assert b'name="start_date"' in response.content
    assert b'name="end_date"' in response.content
    assert b"date-picker form-control" in response.content
    assert b'type="date"' not in response.content


@pytest.mark.django_db
def test_work_programme_detail_includes_assign_job_form(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")

    response = client.get(work_programme.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Assign Job" in content
    assert "autocomplete/unprogrammed-jobs" in content


@pytest.mark.django_db
def test_work_programme_assign_job_view_sets_programme(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    job = Job.objects.create(site=site, title="Inspect cabinet")

    response = client.post(
        reverse("work_programme_assign_job", kwargs={"pk": work_programme.pk}),
        {"jobs": [job.pk]},
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.work_programme == work_programme


@pytest.mark.django_db
def test_work_programme_assign_job_view_assigns_multiple_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    first_job = Job.objects.create(site=site, title="Inspect cabinet")
    second_job = Job.objects.create(site=site, title="Replace cable")

    response = client.post(
        reverse("work_programme_assign_job", kwargs={"pk": work_programme.pk}),
        {"jobs": [first_job.pk, second_job.pk]},
    )

    assert response.status_code == 302
    first_job.refresh_from_db()
    second_job.refresh_from_db()
    assert first_job.work_programme == work_programme
    assert second_job.work_programme == work_programme


@pytest.mark.django_db
def test_work_programme_assign_job_view_rejects_already_programmed_job(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    first_programme = WorkProgramme.objects.create(name="First Programme")
    second_programme = WorkProgramme.objects.create(name="Second Programme")
    job = Job.objects.create(
        site=site,
        title="Inspect cabinet",
        work_programme=first_programme,
    )

    response = client.post(
        reverse("work_programme_assign_job", kwargs={"pk": second_programme.pk}),
        {"jobs": [job.pk]},
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.work_programme == first_programme


@pytest.mark.django_db
def test_work_programme_list_sorts_by_job_count(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    light_programme = WorkProgramme.objects.create(
        name="Light Programme",
        start_date="2026-01-01",
        end_date="2026-06-30",
    )
    busy_programme = WorkProgramme.objects.create(
        name="Busy Programme",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    Job.objects.create(site=site, work_programme=busy_programme, title="Job 1")
    Job.objects.create(site=site, work_programme=busy_programme, title="Job 2")
    Job.objects.create(site=site, work_programme=light_programme, title="Job 3")

    response = client.get(reverse("work_programme_list"), {"sort": "-jobs"})

    assert response.status_code == 200
    programmes = list(response.context["object_list"])
    assert programmes[0] == busy_programme
    assert programmes[1] == light_programme


@pytest.mark.django_db
def test_work_programme_list_filters_by_due_date_and_job_count(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    light_programme = WorkProgramme.objects.create(
        name="Light Programme",
        start_date="2026-01-01",
        end_date="2026-06-30",
    )
    busy_programme = WorkProgramme.objects.create(
        name="Busy Programme",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    Job.objects.create(site=site, work_programme=busy_programme, title="Job 1")
    Job.objects.create(site=site, work_programme=busy_programme, title="Job 2")
    Job.objects.create(site=site, work_programme=light_programme, title="Job 3")

    response = client.get(
        reverse("work_programme_list"),
        {"end_date__gte": "2026-07-01", "job_count__gte": "2"},
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [programme.name for programme in object_list] == ["Busy Programme"]


@pytest.mark.django_db
def test_job_template_form_shows_duplicate_title_error(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Replace Sensor")

    response = client.post(
        reverse("job_template_create"),
        {
            "title": "replace sensor",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "is_active": "on",
        },
    )

    assert response.status_code == 200
    assert "A job template with this title already exists." in response.content.decode()


@pytest.mark.django_db
def test_job_cannot_be_manually_set_to_assigned_without_assignment():
    site = create_site()
    job = Job(site=site, title="Inspect cabinet", status="assigned")

    with pytest.raises(ValidationError):
        job.full_clean()


@pytest.mark.django_db
def test_cancelled_job_requires_closeout_note_but_completed_job_does_not():
    site = create_site()
    job = Job(site=site, title="Inspect cabinet", status="cancelled")

    with pytest.raises(ValidationError):
        job.full_clean()

    job.status = JobStatus.COMPLETED
    job.completed_date = parse_date("2026-04-21")
    job.full_clean()

    job.status = JobStatus.CANCELLED
    job.completed_date = None
    job.closeout_note = "Cancelled during historical import."
    job.full_clean()


@pytest.mark.django_db
def test_completed_date_is_valid_only_for_completed_jobs():
    site = create_site()
    job = Job(
        site=site,
        title="Inspect cabinet",
        status=JobStatus.COMPLETED,
    )

    with pytest.raises(ValidationError) as missing_date:
        job.full_clean()

    assert "completed_date" in missing_date.value.message_dict

    job.completed_date = parse_date("2026-04-21")
    job.full_clean()

    job.status = JobStatus.UNASSIGNED
    with pytest.raises(ValidationError) as invalid_date:
        job.full_clean()

    assert "completed_date" in invalid_date.value.message_dict


def test_job_form_does_not_offer_assigned_status():
    form = JobForm()

    status_values = [value for value, _label in form.fields["status"].choices]

    assert "assigned" not in status_values
    assert "blocked" not in status_values


def test_job_form_exposes_completed_date_for_terminal_manual_updates():
    form = JobForm()

    assert "completed_date" in form.fields
    assert form.fields["completed_date"].label == "Completed date"


@pytest.mark.django_db
def test_assigned_job_form_disables_assignment_controlled_fields():
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=User.objects.create_user(email="leader@example.com"),
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)

    form = JobForm(instance=job)

    assert form.fields["site"].disabled is True
    assert form.fields["status"].disabled is True
    assert form.fields["completed_date"].disabled is True
    assert form.fields["closeout_note"].disabled is True
    assert form.fields["site"].help_text == ASSIGNED_JOB_SITE_DISABLED_REASON
    assert (
        form.fields["status"].help_text == ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON
    )
    assert (
        form.fields["completed_date"].help_text
        == ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON
    )
    assert (
        form.fields["closeout_note"].help_text
        == ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON
    )


@pytest.mark.django_db
def test_assigned_job_update_form_shows_frozen_assignment_controlled_fields(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)

    response = client.get(reverse("job_update", kwargs={"pk": job.pk}))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="site"' in content
    assert 'name="status"' in content
    assert 'name="completed_date"' in content
    assert 'name="closeout_note"' in content
    assert re.search(r'<select\b(?=[^>]*\bname="site")(?=[^>]*\bdisabled\b)', content)
    assert re.search(r'<select\b(?=[^>]*\bname="status")(?=[^>]*\bdisabled\b)', content)
    assert re.search(
        r'<input\b(?=[^>]*\bname="completed_date")(?=[^>]*\bdisabled\b)',
        content,
    )
    assert re.search(
        r'<textarea\b(?=[^>]*\bname="closeout_note")(?=[^>]*\bdisabled\b)',
        content,
    )
    assert content.count("disabled-form-field-control") >= 4
    assert content.count("disabled-field-reason-button") >= 4
    assert content.count('data-bs-toggle="popover"') >= 4
    assert content.count(ASSIGNED_JOB_SITE_DISABLED_REASON) == 1
    assert content.count(ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON) == 3
    assert (
        f'<div class="form-hint">{ASSIGNED_JOB_SITE_DISABLED_REASON}</div>'
        not in content
    )
    assert (
        f'<div class="form-hint">{ASSIGNED_JOB_CLOSEOUT_FIELD_DISABLED_REASON}</div>'
        not in content
    )


def test_job_form_marks_site_select_as_searchable():
    form = JobForm()

    widget = form.fields["site"].widget

    assert widget.url == "autocomplete_sites"
    assert widget.label_field == "label"


@pytest.mark.django_db
def test_job_detail_shows_work_programme_due_date(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    work_programme = WorkProgramme.objects.create(
        name="2026 Field Work",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    job = Job.objects.create(
        site=site,
        title="Inspect cabinet",
        work_programme=work_programme,
    )

    response = client.get(job.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Work Programme" in content
    assert "2026 Field Work" in content
    assert "2026-12-31" in content


@pytest.mark.django_db
def test_job_detail_links_to_requirements_section(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    Requirement.objects.create(job=job, name="Patch cable")

    response = client.get(job.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Requirements" in content
    assert job.get_requirements_url() in content
    assert "Patch cable" not in content


@pytest.mark.django_db
def test_job_detail_renders_blank_requirement_quantity_as_dash(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    Requirement.objects.create(job=job, name="Patch cable")

    response = client.get(job.get_requirements_url())

    content = response.content.decode()
    row_start = content.index("<td>Patch cable</td>")
    row_end = content.index("</tr>", row_start)
    row = content[row_start:row_end]
    assert response.status_code == 200
    assert "<td>-</td>" in row


@pytest.mark.django_db
def test_job_requirement_create_keeps_job_fixed(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")

    form_response = client.get(reverse("requirement_create", kwargs={"job_pk": job.pk}))
    post_response = client.post(
        reverse("requirement_create", kwargs={"job_pk": job.pk}),
        {
            "requirement_type": "part",
            "name": "Patch cable",
            "quantity": "",
            "notes": "",
            "is_required": "on",
        },
    )

    assert form_response.status_code == 200
    assert 'name="job"' not in form_response.content.decode()
    assert post_response.status_code == 302
    assert post_response.url == job.get_requirements_url()
    requirement = Requirement.objects.get()
    assert requirement.job == job
    assert requirement.name == "Patch cable"


@pytest.mark.django_db
def test_job_detail_renders_requirement_confirmation_checkbox(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    requirement = Requirement.objects.create(job=job, name="Patch cable")

    response = client.get(job.get_requirements_url())

    content = response.content.decode()
    row_start = content.index(f'id="requirement-row-{requirement.pk}"')
    row_end = content.index("</tr>", row_start)
    row = content[row_start:row_end]
    assert response.status_code == 200
    assert "Confirmed" in content
    assert "Requirement" in content
    assert "Patch cable" in row
    assert reverse("requirement_toggle", kwargs={"pk": requirement.pk}) in row
    assert "Mark Patch cable confirmed" in row


@pytest.mark.django_db
def test_job_detail_sorts_requirements_by_selected_column(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    Requirement.objects.create(job=job, name="Alpha cable")
    Requirement.objects.create(job=job, name="Zebra battery")

    response = client.get(job.get_requirements_url(), {"sort": "-requirement"})
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["current_sort"] == "-requirement"
    assert response.context["current_sort_field"] == "requirement"
    assert response.context["current_sort_descending"] is True
    assert content.index("Zebra battery") < content.index("Alpha cable")
    assert "sort=confirmed" in content
    assert "sort=type" in content
    assert "sort=quantity" in content


@pytest.mark.django_db
def test_requirement_toggle_updates_requirement_and_returns_job_row(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    requirement = Requirement.objects.create(job=job, name="Patch cable")
    url = reverse("requirement_toggle", kwargs={"pk": requirement.pk})

    checked_response = client.post(url, {"is_checked": "1"}, HTTP_HX_REQUEST="true")

    assert checked_response.status_code == 200
    requirement.refresh_from_db()
    assert requirement.is_checked is True
    assert f'id="requirement-row-{requirement.pk}"' in (
        checked_response.content.decode()
    )

    unchecked_response = client.post(url, {}, HTTP_HX_REQUEST="true")

    assert unchecked_response.status_code == 200
    requirement.refresh_from_db()
    assert requirement.is_checked is False


@pytest.mark.django_db
def test_terminal_trip_job_requirements_are_read_only(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    requirement = Requirement.objects.create(job=job, name="Patch cable")
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    page_response = client.get(job.get_requirements_url())
    toggle_response = client.post(
        reverse("requirement_toggle", kwargs={"pk": requirement.pk}),
        {"is_checked": "1"},
        HTTP_HX_REQUEST="true",
    )

    assert page_response.status_code == 200
    assert b"disabled" in page_response.content
    assert toggle_response.status_code == 403
    requirement.refresh_from_db()
    assert requirement.is_checked is False


@pytest.mark.django_db
def test_completed_job_requirements_are_read_only(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(
        site=site,
        title="Inspect cabinet",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
    )
    requirement = Requirement.objects.create(job=job, name="Patch cable")

    page_response = client.get(job.get_requirements_url())
    toggle_response = client.post(
        reverse("requirement_toggle", kwargs={"pk": requirement.pk}),
        {"is_checked": "1"},
        HTTP_HX_REQUEST="true",
    )

    assert page_response.status_code == 200
    assert "This job is completed" in page_response.content.decode()
    assert toggle_response.status_code == 403
    requirement.refresh_from_db()
    assert requirement.is_checked is False


@pytest.mark.django_db
def test_approved_trip_job_requirement_toggle_does_not_reset_approval(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    client.force_login(leader)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    requirement = Requirement.objects.create(job=job, name="Patch cable")

    response = client.post(
        reverse("requirement_toggle", kwargs={"pk": requirement.pk}),
        {"is_checked": "1"},
        HTTP_HX_REQUEST="true",
    )

    assert response.status_code == 200
    requirement.refresh_from_db()
    trip.refresh_from_db()
    assert requirement.is_checked is True
    assert trip.status == TripStatus.APPROVED
    assert trip.approval_round == 1
    assert TripApproval.objects.filter(trip=trip, approval_round=1).count() == 1


@pytest.mark.django_db
def test_terminal_trip_job_requirement_structure_is_read_only(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    requirement = Requirement.objects.create(job=job, name="Patch cable")
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    page_response = client.get(job.get_requirements_url())
    create_response = client.get(
        reverse("requirement_create", kwargs={"job_pk": job.pk})
    )
    update_response = client.post(
        reverse("requirement_update", kwargs={"pk": requirement.pk}),
        {
            "requirement_type": requirement.requirement_type,
            "name": "Updated cable",
            "quantity": "",
            "notes": "",
            "is_required": "on",
        },
    )
    delete_response = client.post(reverse("requirement_delete", args=[requirement.pk]))

    assert page_response.status_code == 200
    assert "Requirements frozen" in page_response.content.decode()
    assert create_response.status_code == 302
    assert create_response.url == job.get_requirements_url()
    assert update_response.status_code == 302
    assert update_response.url == job.get_requirements_url()
    assert delete_response.status_code == 302
    assert delete_response.url == job.get_requirements_url()
    requirement.refresh_from_db()
    assert requirement.name == "Patch cable"
    assert Requirement.objects.filter(pk=requirement.pk).exists()


@pytest.mark.django_db
def test_terminal_trip_job_update_is_frozen(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    get_response = client.get(reverse("job_update", kwargs={"pk": job.pk}))
    post_response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "work_programme": "",
            "title": "Updated cabinet",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
        },
    )

    assert get_response.status_code == 302
    assert get_response.url == job.get_absolute_url()
    assert post_response.status_code == 302
    assert post_response.url == job.get_absolute_url()
    job.refresh_from_db()
    assert job.title == "Inspect cabinet"


@pytest.mark.django_db
def test_approved_trip_job_requirement_create_does_not_reset_approval(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    client.force_login(leader)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)

    response = client.post(
        reverse("requirement_create", kwargs={"job_pk": job.pk}),
        {
            "requirement_type": "part",
            "name": "Patch cable",
            "quantity": "",
            "notes": "",
            "is_required": "on",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    assert Requirement.objects.filter(job=job, name="Patch cable").exists()
    assert trip.status == TripStatus.APPROVED
    assert trip.approval_round == 1
    assert TripApproval.objects.filter(trip=trip, approval_round=1).count() == 1


@pytest.mark.django_db
def test_approved_trip_job_requirement_update_and_delete_do_not_reset_approval(client):
    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    client.force_login(leader)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    requirement = Requirement.objects.create(job=job, name="Patch cable")

    update_response = client.post(
        reverse("requirement_update", kwargs={"pk": requirement.pk}),
        {
            "requirement_type": "part",
            "name": "Patch cable pack",
            "quantity": "1",
            "notes": "",
            "is_required": "on",
        },
    )
    delete_response = client.post(reverse("requirement_delete", args=[requirement.pk]))

    assert update_response.status_code == 302
    assert delete_response.status_code == 302
    assert not Requirement.objects.filter(pk=requirement.pk).exists()
    trip.refresh_from_db()
    assert trip.status == TripStatus.APPROVED
    assert trip.approval_round == 1
    assert TripApproval.objects.filter(trip=trip, approval_round=1).count() == 1


@pytest.mark.django_db
def test_job_due_date_is_empty_when_work_programme_has_no_due_date():
    site = create_site()
    work_programme = WorkProgramme.objects.create(name="Draft Programme")
    job = Job.objects.create(
        site=site,
        title="Inspect cabinet",
        work_programme=work_programme,
    )

    assert job.due_date is None


@pytest.mark.django_db
def test_assign_job_to_work_programme_sets_programme_and_history_reason():
    site = create_site()
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    job = Job.objects.create(site=site, title="Inspect cabinet")

    assign_job_to_work_programme(job, work_programme)

    job.refresh_from_db()
    assert job.work_programme == work_programme
    assert job.history.first().history_change_reason == "Assigned job to work programme"


@pytest.mark.django_db
def test_assign_job_to_work_programme_rejects_already_programmed_job():
    site = create_site()
    first_programme = WorkProgramme.objects.create(name="First Programme")
    second_programme = WorkProgramme.objects.create(name="Second Programme")
    job = Job.objects.create(
        site=site,
        title="Inspect cabinet",
        work_programme=first_programme,
    )

    with pytest.raises(ValidationError):
        assign_job_to_work_programme(job, second_programme)


@pytest.mark.django_db
def test_assign_jobs_to_work_programme_rolls_back_when_any_job_is_ineligible():
    site = create_site()
    first_programme = WorkProgramme.objects.create(name="First Programme")
    second_programme = WorkProgramme.objects.create(name="Second Programme")
    eligible_job = Job.objects.create(site=site, title="Inspect cabinet")
    ineligible_job = Job.objects.create(
        site=site,
        title="Replace cable",
        work_programme=first_programme,
    )

    with pytest.raises(ValidationError):
        assign_jobs_to_work_programme(
            [eligible_job, ineligible_job],
            second_programme,
        )

    eligible_job.refresh_from_db()
    ineligible_job.refresh_from_db()
    assert eligible_job.work_programme is None
    assert ineligible_job.work_programme == first_programme


@pytest.mark.django_db
def test_job_update_sets_and_clears_work_programme(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    work_programme = WorkProgramme.objects.create(
        name="2026 Field Work",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "work_programme": work_programme.pk,
            "title": "Inspect cabinet",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.UNASSIGNED,
            "closeout_note": "",
        },
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.work_programme == work_programme

    response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "work_programme": "",
            "title": "Inspect cabinet",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.UNASSIGNED,
            "closeout_note": "",
        },
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.work_programme is None


@pytest.mark.django_db
def test_assigned_job_update_keeps_status_and_closeout_note_under_trip_closeout(
    client,
):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    other_site = create_site("AA-002")

    response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": other_site.pk,
            "work_programme": "",
            "title": "Updated cabinet",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.CANCELLED,
            "closeout_note": "Should not land.",
        },
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.site == site
    assert job.title == "Updated cabinet"
    assert job.status == JobStatus.ASSIGNED
    assert job.closeout_note == ""


@pytest.mark.django_db
def test_editing_assigned_job_on_approved_trip_does_not_reset_approval(
    client,
):
    from access_atlas.trips.models import TripApproval, TripStatus

    leader = User.objects.create_user(email="leader@example.com")
    approver = User.objects.create_user(email="approver@example.com")
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=leader,
        status=TripStatus.APPROVED,
        approval_round=1,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Site job")
    assign_job_to_site_visit(site_visit, job)
    TripApproval.objects.create(trip=trip, approver=approver, approval_round=1)
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    client.force_login(leader)

    response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "template": "",
            "title": "Updated title",
            "description": "Allowed metadata update.",
            "work_programme": work_programme.pk,
            "estimated_duration_minutes": "45",
            "priority": "high",
            "status": JobStatus.CANCELLED,
            "closeout_note": "Should not land.",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    job.refresh_from_db()
    assert job.title == "Updated title"
    assert job.description == "Allowed metadata update."
    assert job.work_programme == work_programme
    assert job.estimated_duration_minutes == 45
    assert job.priority == Priority.HIGH
    assert job.status == JobStatus.ASSIGNED
    assert job.closeout_note == ""
    assert trip.status == TripStatus.APPROVED
    assert trip.approval_round == 1
    assert TripApproval.objects.filter(trip=trip, approval_round=1).count() == 1


@pytest.mark.django_db
def test_job_from_template_form_marks_site_select_as_searchable():
    site = create_site()

    form = JobFromTemplateForm(site_queryset=Site.objects.filter(pk=site.pk))
    site_widget = form.fields["site"].widget
    template_widget = form.fields["template"].widget
    work_programme_widget = form.fields["work_programme"].widget

    assert site_widget.url == "autocomplete_sites"
    assert site_widget.label_field == "label"
    assert template_widget.url == "autocomplete_job_templates"
    assert template_widget.label_field == "title"
    assert work_programme_widget.url == "autocomplete_work_programmes"
    assert work_programme_widget.label_field == "label"
    assert form.fields["work_programme"].required is False


@pytest.mark.django_db
def test_job_form_marks_work_programme_select_as_searchable():
    form = JobForm()
    work_programme_widget = form.fields["work_programme"].widget

    assert work_programme_widget.url == "autocomplete_work_programmes"
    assert work_programme_widget.label_field == "label"
    assert form.fields["work_programme"].required is False


def test_assign_work_programme_job_form_marks_job_select_as_searchable():
    form = AssignWorkProgrammeJobForm()
    widget = form.fields["jobs"].widget

    assert widget.url == "autocomplete_unprogrammed_jobs"
    assert widget.label_field == "label"


@pytest.mark.django_db
def test_job_from_template_page_includes_tomselect_media(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_create_from_template"))

    assert response.status_code == 200
    assert b"django_tomselect/js/django-tomselect" in response.content


@pytest.mark.django_db
def test_invalid_job_post_keeps_selected_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()

    response = client.post(
        reverse("job_create"),
        {
            "site": site.pk,
            "title": "",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.UNASSIGNED,
            "closeout_note": "",
        },
    )

    assert response.status_code == 200
    assert response.context["form"]["site"].value() == str(site.pk)


@pytest.mark.django_db
def test_invalid_job_from_template_post_keeps_selected_values(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()

    response = client.post(
        reverse("job_create_from_template"),
        {
            "site": site.pk,
            "template": "",
        },
    )

    assert response.status_code == 200
    assert response.context["form"]["site"].value() == str(site.pk)
    assert b"Unable to save changes" in response.content
    assert b"Review the highlighted fields and try again." in response.content
    assert b"Template: This field is required." in response.content


@pytest.mark.django_db
def test_job_from_template_form_uses_server_side_validation(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_create_from_template"))

    assert response.status_code == 200
    assert b'<form method="post" novalidate>' in response.content


@pytest.mark.django_db
def test_create_job_from_template_can_assign_work_programme(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    template = JobTemplate.objects.create(title="Replace sensor")
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")

    response = client.post(
        reverse("job_create_from_template"),
        {
            "site": site.pk,
            "template": template.pk,
            "work_programme": work_programme.pk,
        },
    )

    job = Job.objects.get()
    assert response.status_code == 302
    assert job.work_programme == work_programme
    assert response.url == job.get_absolute_url()


@pytest.mark.django_db
def test_job_list_links_to_map_view(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_list"))

    assert response.status_code == 200
    assert reverse("job_map") in response.content.decode()


@pytest.mark.django_db
def test_job_list_disables_edit_for_jobs_on_terminal_trips(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    response = client.get(reverse("job_list"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "normal job editing is frozen" in content
    assert 'aria-label="Edit Frozen job"' in content
    assert reverse("job_update", kwargs={"pk": frozen_job.pk}) not in content
    assert reverse("job_update", kwargs={"pk": editable_job.pk}) in content


@pytest.mark.django_db
def test_job_list_accepts_manual_per_page_value(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    for index in range(30):
        Job.objects.create(site=site, title=f"Job {index}")

    response = client.get(reverse("job_list"), {"per_page": "1000000"})

    assert response.status_code == 200
    assert len(response.context["object_list"]) == 30
    assert response.context["per_page"] == 1000000


@pytest.mark.django_db
def test_job_bulk_edit_form_requires_completed_date_for_completed_status():
    form = JobBulkEditForm(data={"status": JobStatus.COMPLETED})

    assert not form.is_valid()
    assert "completed_date" in form.errors


@pytest.mark.django_db
def test_job_bulk_edit_form_allows_clearing_completed_date_when_status_changes():
    form = JobBulkEditForm(
        data={
            "status": JobStatus.UNASSIGNED,
            "_nullify": "completed_date",
        }
    )

    assert form.is_valid()
    assert form.nullified_fields() == {"completed_date"}


@pytest.mark.django_db
def test_job_bulk_edit_form_rejects_clearing_completed_date_for_completed_status():
    form = JobBulkEditForm(
        data={
            "status": JobStatus.COMPLETED,
            "_nullify": "completed_date",
        }
    )

    assert not form.is_valid()
    assert "completed_date" in form.errors


@pytest.mark.django_db
def test_job_bulk_edit_completed_status_sets_completed_date(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Complete me")

    response = client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )

    job.refresh_from_db()
    assert response.status_code == 302
    assert job.status == JobStatus.COMPLETED
    assert job.completed_date == parse_date("2026-05-17")


@pytest.mark.django_db
def test_job_bulk_edit_success_message_reports_noop(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(
        site=site,
        title="Already urgent",
        priority=Priority.URGENT,
    )

    response = client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(job.pk)],
            "priority": Priority.URGENT,
            "apply_bulk_edit": "1",
        },
        follow=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Bulk edit checked 1 job(s). No changes were needed." in content


@pytest.mark.django_db
def test_job_bulk_edit_can_clear_completed_date_when_status_changes(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(
        site=site,
        title="Reopen me",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-05-01"),
    )

    response = client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(job.pk)],
            "status": JobStatus.UNASSIGNED,
            "_nullify": "completed_date",
            "apply_bulk_edit": "1",
        },
    )

    job.refresh_from_db()
    assert response.status_code == 302
    assert job.status == JobStatus.UNASSIGNED
    assert job.completed_date is None


@pytest.mark.django_db
def test_job_bulk_edit_renders_nullable_field_controls(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Nullable fields")

    response = client.get(reverse("job_bulk_edit"), {"pk": str(job.pk)})

    content = response.content.decode()
    assert response.status_code == 200
    assert 'name="_nullify"' in content
    assert 'value="work_programme"' in content
    assert 'value="completed_date"' in content
    assert "Set work programme to null" in content
    assert "Set completed date to null" in content


@pytest.mark.django_db
def test_job_bulk_edit_blocks_assigned_status_changes_before_saving(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    assigned_job = Job.objects.create(site=site, title="Assigned job")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, assigned_job)

    response = client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )

    assigned_job.refresh_from_db()
    editable_job.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 200
    assert "Assigned jobs cannot have status changed by bulk edit" in content
    assert "Resolve the blocking jobs" in content
    assert assigned_job.status == JobStatus.ASSIGNED
    assert editable_job.status == JobStatus.UNASSIGNED
    assert editable_job.completed_date is None


@pytest.mark.django_db
def test_job_bulk_edit_blocks_terminal_trip_jobs_before_saving(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    response = client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(frozen_job.pk), str(editable_job.pk)],
            "priority": Priority.URGENT,
            "apply_bulk_edit": "1",
        },
    )

    frozen_job.refresh_from_db()
    editable_job.refresh_from_db()
    content = response.content.decode()
    assert response.status_code == 200
    assert "normal job editing is frozen" in content
    assert "Resolve the blocking jobs" in content
    assert frozen_job.priority == Priority.NORMAL
    assert editable_job.priority == Priority.NORMAL


@pytest.mark.django_db
def test_job_bulk_edit_service_is_all_or_nothing_for_invalid_selection():
    user = User.objects.create_user(email="user@example.com")
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    with pytest.raises(ValidationError):
        bulk_edit_jobs([frozen_job, editable_job], priority=Priority.URGENT)

    frozen_job.refresh_from_db()
    editable_job.refresh_from_db()
    assert frozen_job.priority == Priority.NORMAL
    assert editable_job.priority == Priority.NORMAL


@pytest.mark.django_db
def test_job_bulk_edit_exclude_param_drops_job_from_select_all_preview(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    dropped_job = Job.objects.create(site=site, title="Dropped job")
    kept_job = Job.objects.create(site=site, title="Kept job")

    response = client.get(
        reverse("job_bulk_edit"),
        {
            "_all": "1",
            "_exclude": str(dropped_job.pk),
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["selected_count"] == 1
    assert kept_job.title in content
    assert dropped_job.title not in content


@pytest.mark.django_db
def test_job_bulk_edit_selection_post_ignores_stale_query_selection(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    stale_job = Job.objects.create(site=site, title="Stale selection")
    selected_job = Job.objects.create(site=site, title="Current selection")

    response = client.post(
        f"{reverse('job_bulk_edit')}?pk={stale_job.pk}",
        {"pk": [str(selected_job.pk)]},
    )

    query_params = parse_qs(urlparse(response["Location"]).query)
    assert response.status_code == 302
    assert query_params["pk"] == [str(selected_job.pk)]


@pytest.mark.django_db
def test_job_bulk_edit_select_all_excludes_frozen_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    response = client.get(reverse("job_bulk_edit"), {"_all": "1"})

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["selected_count"] == 1
    assert editable_job.title in content
    assert frozen_job.title not in content


@pytest.mark.django_db
def test_job_bulk_edit_select_all_respects_current_filters(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    unassigned_job = Job.objects.create(site=site, title="Unassigned job")
    Job.objects.create(
        site=site,
        title="Cancelled job",
        status=JobStatus.CANCELLED,
        closeout_note="No longer required.",
    )

    response = client.get(
        reverse("job_bulk_edit"),
        {
            "_all": "1",
            "status": JobStatus.UNASSIGNED,
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["selected_count"] == 1
    assert unassigned_job.title in content
    assert "Cancelled job" not in content


@pytest.mark.django_db
def test_job_list_select_all_count_excludes_frozen_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    response = client.get(reverse("job_list"))

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["bulk_selectable_count"] == 1
    assert response.context["bulk_excluded_count"] == 1
    assert "Select all 1 selectable jobs matching current filters" in content
    assert "1 frozen job not included" in content


@pytest.mark.django_db
def test_job_map_payload_includes_bulk_selection_contract(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    frozen_job = Job.objects.create(site=site, title="Frozen job")
    assign_job_to_site_visit(site_visit, frozen_job)
    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])

    response = client.get(reverse("job_map"))

    map_sites = parse_json_script(response.content.decode(), "job-map-data")
    site_payload = map_sites[0]["site"]
    job_payload = map_sites[0]["jobs"][0]
    assert response.status_code == 200
    assert site_payload["id"] == site.pk
    assert job_payload["bulkEditable"] is False
    assert "normal job editing is frozen" in job_payload["bulkDisabledReason"]


@pytest.mark.django_db
def test_job_bulk_edit_blockers_persist_across_preview_pages(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    first_job = Job.objects.create(site=site, title="Assigned A")
    second_job = Job.objects.create(site=site, title="Assigned B")
    assign_job_to_site_visit(site_visit, first_job)
    assign_job_to_site_visit(site_visit, second_job)

    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(first_job.pk), str(second_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    response = client.get(
        reverse("job_bulk_edit"),
        {
            "pk": [str(first_job.pk), str(second_job.pk)],
            "per_page": "1",
            "page": "2",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "2 to 2 of 2 jobs" in content
    assert "Assigned B" in content
    assert "Assigned jobs cannot have status changed by bulk edit" in content


@pytest.mark.django_db
def test_job_bulk_edit_new_selection_clears_stale_blockers(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    assigned_job = Job.objects.create(site=site, title="Assigned blocker")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, assigned_job)
    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )

    response = client.post(
        reverse("job_bulk_edit"),
        {"pk": [str(editable_job.pk)]},
        follow=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "last attempted bulk edit" not in content
    assert "Assigned jobs cannot have status changed by bulk edit" not in content


@pytest.mark.django_db
def test_job_bulk_edit_errors_only_shows_only_blocking_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    assigned_job = Job.objects.create(site=site, title="Assigned blocker")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, assigned_job)

    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    response = client.get(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "errors_only": "1",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["errors_only"] is True
    assert "Assigned blocker" in content
    assert "Editable job" not in content


@pytest.mark.django_db
def test_job_bulk_edit_dropping_blocker_keeps_remaining_blockers(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    dropped_job = Job.objects.create(site=site, title="Dropped blocker")
    remaining_job = Job.objects.create(site=site, title="Remaining blocker")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, dropped_job)
    assign_job_to_site_visit(site_visit, remaining_job)

    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(dropped_job.pk), str(remaining_job.pk), str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    response = client.get(
        reverse("job_bulk_edit"),
        {
            "pk": [str(remaining_job.pk), str(editable_job.pk)],
            "errors_only": "1",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert response.context["bulk_edit_issue_count"] == 1
    assert "Remaining blocker" in content
    assert "Dropped blocker" not in content
    assert "Editable job" not in content


@pytest.mark.django_db
def test_job_bulk_edit_ignores_blockers_when_selection_adds_new_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    assigned_job = Job.objects.create(site=site, title="Assigned blocker")
    added_job = Job.objects.create(site=site, title="New selection")
    assign_job_to_site_visit(site_visit, assigned_job)

    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    response = client.get(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(added_job.pk)],
            "errors_only": "1",
        },
    )

    assert response.status_code == 200
    assert response.context["has_bulk_edit_issues"] is False
    assert response.context["errors_only"] is False


@pytest.mark.django_db
def test_job_bulk_edit_success_clears_stored_blockers(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    assigned_job = Job.objects.create(site=site, title="Assigned blocker")
    editable_job = Job.objects.create(site=site, title="Editable job")
    assign_job_to_site_visit(site_visit, assigned_job)

    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    client.post(
        reverse("job_bulk_edit"),
        {
            "pk": [str(editable_job.pk)],
            "status": JobStatus.COMPLETED,
            "completed_date": "2026-05-17",
            "apply_bulk_edit": "1",
        },
    )
    response = client.get(
        reverse("job_bulk_edit"),
        {
            "pk": [str(assigned_job.pk), str(editable_job.pk)],
            "errors_only": "1",
        },
    )

    assert response.status_code == 200
    assert response.context["has_bulk_edit_issues"] is False
    assert response.context["errors_only"] is False


@pytest.mark.django_db
def test_job_template_list_search_filters_results(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Inspect repeater", description="Hilltop")
    JobTemplate.objects.create(title="Replace battery", description="Cabinet")

    response = client.get(reverse("job_template_list"), {"q": "repeat"})

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert len(object_list) == 1
    assert object_list[0].title == "Inspect repeater"


@pytest.mark.django_db
def test_job_template_list_filters_by_active_state_and_priority(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(
        title="Inactive low priority",
        priority=Priority.LOW,
        is_active=False,
    )
    JobTemplate.objects.create(
        title="Active urgent",
        priority=Priority.URGENT,
        is_active=True,
    )

    response = client.get(
        reverse("job_template_list"),
        {"is_active": "false", "priority": Priority.LOW},
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [template.title for template in object_list] == ["Inactive low priority"]


@pytest.mark.django_db
def test_job_template_active_filter_uses_yes_no_labels_and_matching_colors(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Inactive template", is_active=False)

    response = client.get(reverse("job_template_list"), {"is_active": "false"})

    assert response.status_code == 200
    content = response.content.decode()
    assert re.search(
        r'<option\s+value="true"[^>]*'
        r'data-filter-item-color="var\(--tblr-blue\)"[^>]*>\s*Yes\s*</option>',
        content,
    )
    assert re.search(
        r'<option\s+value="false"[^>]*'
        r'data-filter-item-color="var\(--tblr-yellow\)"[^>]*>\s*No\s*</option>',
        content,
    )
    assert '<span class="badge bg-yellow-lt">No</span>' in content


@pytest.mark.django_db
def test_job_template_list_links_to_import(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_template_list"))

    assert response.status_code == 200
    assert reverse("job_template_import") in response.content.decode()


@pytest.mark.django_db
def test_job_map_payload_uses_missing_site_code_label(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="blank",
        code="",
        name="Blank Code Site",
        latitude=-41.1,
        longitude=174.1,
    )
    Job.objects.create(site=site, title="Inspect blank code site")

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    payload = parse_json_script(response.content.decode(), "job-map-data")
    assert payload[0]["site"]["code"] == "code not set"


@pytest.mark.django_db
def test_job_list_uses_saved_sort_preference(client):
    user = User.objects.create_user(email="user@example.com")
    site_a = create_site("AA-002")
    site_b = create_site("AA-001")
    Job.objects.create(site=site_a, title="Zulu")
    Job.objects.create(site=site_b, title="Alpha")
    set_user_preference(
        user,
        list_sort_preference_key("jobs"),
        {"value": "site"},
    )
    client.force_login(user)

    response = client.get(reverse("job_list"))

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [job.site.code for job in object_list] == ["AA-001", "AA-002"]
    assert response.context["current_sort"] == "site"


@pytest.mark.django_db
def test_job_list_filters_any_supported_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    assigned_job = Job(
        site=site,
        title="Visible assigned job",
        status=JobStatus.ASSIGNED,
    )
    assigned_job.save(skip_validation=True)
    Job.objects.create(
        site=site,
        title="Visible completed job",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )

    response = client.get(reverse("job_list"), {"status": JobStatus.ASSIGNED})

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [job.title for job in object_list] == ["Visible assigned job"]


@pytest.mark.django_db
def test_job_list_saves_and_restores_filter_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    assigned_job = Job(
        site=site,
        title="Saved assigned job",
        status=JobStatus.ASSIGNED,
    )
    assigned_job.save(skip_validation=True)
    Job.objects.create(
        site=site,
        title="Saved completed job",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )

    response = client.get(reverse("job_list"), {"status": JobStatus.ASSIGNED})

    assert response.status_code == 200
    assert get_user_preference(user, list_filter_preference_key("jobs")) == {
        "params": {"status": [JobStatus.ASSIGNED]}
    }

    response = client.get(reverse("job_list"))

    assert response.status_code == 302
    assert response.url == f"{reverse('job_list')}?status=assigned"

    response = client.get(response.url)

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [job.title for job in object_list] == ["Saved assigned job"]


@pytest.mark.django_db
def test_job_list_filter_update_marker_clears_saved_filter_preference(client):
    user = User.objects.create_user(email="user@example.com")
    set_user_preference(
        user,
        list_filter_preference_key("jobs"),
        {"params": {"status": [JobStatus.ASSIGNED]}},
    )
    client.force_login(user)

    response = client.get(
        reverse("job_list"),
        {FILTER_STATE_PARAM: FILTER_STATE_UPDATE},
    )

    assert response.status_code == 302
    assert response.url == reverse("job_list")
    assert get_user_preference(user, list_filter_preference_key("jobs")) == {
        "params": {}
    }


@pytest.mark.django_db
def test_job_map_filter_submit_saves_filter_preference_for_table(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(
        reverse("job_map"),
        {
            FILTER_STATE_PARAM: FILTER_STATE_UPDATE,
            "status": JobStatus.COMPLETED,
        },
    )

    assert response.status_code == 302
    assert response.url == f"{reverse('job_map')}?status=completed"
    assert get_user_preference(user, list_filter_preference_key("jobs")) == {
        "params": {"status": [JobStatus.COMPLETED]}
    }

    response = client.get(reverse("job_list"))

    assert response.status_code == 302
    assert response.url == f"{reverse('job_list')}?status=completed"


@pytest.mark.django_db
def test_job_list_summarizes_all_selected_status_filters(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    assigned_job = Job(
        site=site,
        title="Assigned job",
        status=JobStatus.ASSIGNED,
    )
    assigned_job.save(skip_validation=True)
    Job.objects.create(
        site=site,
        title="Completed job",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )

    response = client.get(reverse("job_list"), {"status": JobStatus.values})

    assert response.status_code == 200
    assert [chip["label"] for chip in response.context["active_filter_chips"]] == [
        "Status is all statuses"
    ]
    content = response.content.decode()
    assert 'id="list-filter-offcanvas"' not in content
    assert "list-filter-inline-form" in content
    assert 'data-filter-item-color="var(--tblr-blue)"' in content
    assert 'data-filter-item-color="var(--tblr-green)"' in content
    assert content.count("data-list-filter-form") == 1


@pytest.mark.django_db
def test_job_list_filters_by_any_site_tag(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    remote_site = Site.objects.create(
        source_name="dummy",
        external_id="remote",
        code="AA-001",
        name="Remote",
        tags=[{"label": "Remote", "color": "orange"}],
        latitude=-41.1,
        longitude=174.1,
    )
    coastal_site = Site.objects.create(
        source_name="dummy",
        external_id="coastal",
        code="AA-002",
        name="Coastal",
        tags=[{"label": "Coastal", "color": "blue"}],
        latitude=-42.1,
        longitude=175.1,
    )
    untagged_site = Site.objects.create(
        source_name="dummy",
        external_id="plain",
        code="AA-003",
        name="Plain",
        latitude=-43.1,
        longitude=176.1,
    )
    Job.objects.create(site=remote_site, title="Remote job")
    Job.objects.create(site=coastal_site, title="Coastal job")
    Job.objects.create(site=untagged_site, title="Plain job")

    response = client.get(
        reverse("job_list"),
        {"site_tags": ["Remote", "Coastal"]},
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [job.title for job in object_list] == ["Coastal job", "Remote job"]
    assert any(
        chip["label"] == "Site tags has these tags Remote"
        for chip in response.context["active_filter_chips"]
    )


@pytest.mark.django_db
def test_job_map_applies_shared_status_filter(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    assigned_job = Job(
        site=site,
        title="Assigned job",
        status=JobStatus.ASSIGNED,
    )
    assigned_job.save(skip_validation=True)
    Job.objects.create(
        site=site,
        title="Completed job",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )

    response = client.get(reverse("job_map"), {"status": JobStatus.COMPLETED})

    assert response.status_code == 200
    map_sites = parse_json_script(response.content.decode(), "job-map-data")
    assert [job["title"] for job in map_sites[0]["jobs"]] == ["Completed job"]
    status_layers = parse_json_script(
        response.content.decode(),
        "job-map-status-layers",
    )
    completed_layer = next(
        layer for layer in status_layers if layer["value"] == JobStatus.COMPLETED
    )
    assigned_layer = next(
        layer for layer in status_layers if layer["value"] == JobStatus.ASSIGNED
    )
    assert completed_layer["color"] == "#2fb344"
    assert assigned_layer["color"] == "#206bc4"
    content = response.content.decode()
    assert 'id="list-filter-offcanvas"' in content
    assert 'data-filter-count="1"' in content
    assert 'id="job-map-status-controls"' not in content
    assert "list-controls-card" not in content
    assert 'id="list-results-tab"' not in content
    assert 'id="list-search-input"' not in content


@pytest.mark.django_db
def test_job_charts_apply_shared_status_filter(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    Job.objects.create(site=site, title="Unassigned job")
    Job.objects.create(
        site=site,
        title="Completed job",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )

    response = client.get(reverse("job_charts"), {"status": JobStatus.COMPLETED})

    assert response.status_code == 200
    chart_data = parse_json_script(response.content.decode(), "job-status-chart-data")
    assert chart_data["total"] == 1
    assert chart_data["counts"] == [0, 0, 1, 0]
    assert response.context["search_result_count"] == 1
    content = response.content.decode()
    assert "vendor/chart.js/chart.umd.min.js" in content
    assert 'src="/static/js/jobs_charts.js"' in content
    assert "Charts" in content


@pytest.mark.django_db
def test_job_detail_links_to_assigned_site_visit(client):
    user = User.objects.create_user(email="user@example.com")
    site = create_site()
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Inspect cabinet")
    assign_job_to_site_visit(site_visit, job)
    client.force_login(user)

    response = client.get(reverse("job_detail", kwargs={"pk": job.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Site Visit" in content
    assert site_visit.get_absolute_url() in content
    assert str(site_visit) in content


@pytest.mark.django_db
def test_job_history_defaults_to_25_entries_per_page(client):
    user = User.objects.create_user(email="user@example.com")
    site = create_site()
    job = Job.objects.create(site=site, title="Initial title")
    for index in range(30):
        job.title = f"Revision {index}"
        job.save()
    client.force_login(user)

    response = client.get(reverse("job_history", kwargs={"pk": job.pk}))

    assert response.status_code == 200
    assert len(response.context["history_records"]) == 25
    assert response.context["paginator"].num_pages == 2
    assert response.context["per_page"] == 25


@pytest.mark.django_db
def test_work_programme_history_paginates_and_renders_empty_state(client):
    user = User.objects.create_user(email="user@example.com")
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    for index in range(3):
        work_programme.description = f"Revision {index}"
        work_programme.save()
    client.force_login(user)

    response = client.get(
        reverse("work_programme_history", kwargs={"pk": work_programme.pk}),
        {"per_page": 2},
    )

    assert response.status_code == 200
    assert response.context["per_page"] == 2
    assert response.context["paginator"].num_pages == 2
    assert "<th>When</th>" in response.content.decode()

    work_programme.history.all().delete()
    response = client.get(
        reverse("work_programme_history", kwargs={"pk": work_programme.pk})
    )

    assert response.status_code == 200
    assert "No history records found." in response.content.decode()


@pytest.mark.django_db
def test_job_map_includes_jobs_and_status_layers(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    Job.objects.create(site=site, title="Inspect cabinet")
    Job.objects.create(
        site=site,
        title="Closed work",
        status=JobStatus.COMPLETED,
        completed_date=parse_date("2026-04-21"),
        closeout_note="Completed in the field.",
    )
    Job.objects.create(
        site=site,
        title="Cancelled work",
        status=JobStatus.CANCELLED,
        closeout_note="No longer required.",
    )

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "AA-001" in content
    assert "Inspect cabinet" in content
    assert "Closed work" in content
    assert "Cancelled work" in content
    status_layers = parse_json_script(content, "job-map-status-layers")
    assert {layer["value"] for layer in status_layers} == set(JobStatus.values)


@pytest.mark.django_db
def test_job_map_status_layers_prioritize_open_work_for_marker_color(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    status_layers = parse_json_script(
        response.content.decode(),
        "job-map-status-layers",
    )
    ranks = {layer["value"]: layer["rank"] for layer in status_layers}
    assert ranks[JobStatus.UNASSIGNED] > ranks[JobStatus.ASSIGNED]
    assert ranks[JobStatus.ASSIGNED] > ranks[JobStatus.COMPLETED]
    assert ranks[JobStatus.COMPLETED] > ranks[JobStatus.CANCELLED]


@pytest.mark.django_db
def test_job_map_uses_saved_viewport_preference(client):
    user = User.objects.create_user(email="user@example.com")
    set_user_preference(
        user,
        JOBS_MAP_PREFERENCE_KEY,
        {
            "viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8},
        },
    )
    client.force_login(user)

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    content = response.content.decode()
    map_preference = parse_json_script(content, "job-map-preference")
    basemap_preference = parse_json_script(content, "map-basemap-preference")
    assert map_preference["value"]["viewport"] == {
        "lat": -41.2,
        "lng": 174.7,
        "zoom": 8,
    }
    assert basemap_preference["value"] == {
        "light": "carto-voyager",
        "dark": "carto-dark",
    }


@pytest.mark.django_db
def test_job_import_upload_reviews_valid_csv_without_creating_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nAA-001,Replace sensor\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    assert response.status_code == 200
    assert "Ready" in response.content.decode()
    assert Job.objects.count() == 0


def test_job_import_parser_rejects_unsupported_headers():
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title,unexpected\nAA-001,Replace sensor,value\n",
        content_type="text/csv",
    )

    rows = parse_job_import_csv(csv_file)

    assert rows[0].error == (
        "CSV headers must include site_code,template_title and may also include "
        "status,completed_date,closeout_note,work_programme."
    )


def test_job_import_parser_rejects_missing_required_headers():
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,status\nAA-001,unassigned\n",
        content_type="text/csv",
    )

    rows = parse_job_import_csv(csv_file)

    assert rows[0].error == (
        "CSV headers must include site_code,template_title and may also include "
        "status,completed_date,closeout_note,work_programme."
    )


def test_job_import_parser_rejects_non_utf8_csv():
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"\xff\xfe\x00",
        content_type="text/csv",
    )

    rows = parse_job_import_csv(csv_file)

    assert rows[0].error == "CSV file must be UTF-8 encoded."


def test_job_import_parser_rejects_empty_csv():
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\n",
        content_type="text/csv",
    )

    rows = parse_job_import_csv(csv_file)

    assert rows[0].error == "CSV file does not contain any job rows."


@pytest.mark.django_db
def test_job_import_get_reloads_reviewed_rows_from_session(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nAA-001,Replace sensor\n",
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.get(reverse("job_import"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ready" in content
    assert "AA-001" in content


@pytest.mark.django_db
def test_job_import_confirm_without_session_redirects_without_creating_jobs(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    assert response.url == reverse("job_import")
    assert Job.objects.count() == 0


@pytest.mark.django_db
def test_job_import_confirm_refuses_review_rows_with_errors(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nBAD-001,Replace sensor\n",
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    assert response.url == reverse("job_import")
    assert Job.objects.count() == 0


@pytest.mark.django_db
def test_job_import_page_includes_specification_and_example_path(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_import"))

    content = response.content.decode()
    assert response.status_code == 200
    assert (
        "site_code,template_title,status,completed_date,closeout_note,work_programme"
        in content
    )
    assert "docs/examples/job-test-import.csv" in content
    assert "Create jobs" not in content


@pytest.mark.django_db
def test_job_import_confirm_creates_jobs_from_reviewed_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    template = JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nAA-001,Replace sensor\n",
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    job = Job.objects.get()
    assert job.site == site
    assert job.template == template
    assert job.title == "Replace sensor"
    assert job.status == JobStatus.UNASSIGNED
    assert job.history.first().history_change_reason == (
        "Imported from CSV using job template"
    )


@pytest.mark.django_db
def test_job_import_confirm_assigns_existing_work_programme(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    work_programme = WorkProgramme.objects.create(
        name="2026 Field Work",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,work_programme\n"
            b"AA-001,Replace sensor,2026 Field Work\n"
        ),
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    job = Job.objects.get()
    assert job.work_programme == work_programme
    assert job.due_date == parse_date("2026-12-31")


@pytest.mark.django_db
def test_job_import_parser_resolves_references_case_insensitively():
    site = create_site()
    template = JobTemplate.objects.create(title="Replace Sensor", is_active=True)
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,work_programme\n"
            b"aa-001,replace sensor,2026 field work\n"
        ),
        content_type="text/csv",
    )

    rows = parse_job_import_csv(csv_file)

    assert len(rows) == 1
    assert rows[0].is_valid
    assert rows[0].site == site
    assert rows[0].template == template
    assert rows[0].work_programme == work_programme


@pytest.mark.django_db
def test_job_import_rejects_unknown_work_programme(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,work_programme\n"
            b"AA-001,Replace sensor,Unknown Programme\n"
        ),
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Unknown work_programme." in content
    assert Job.objects.count() == 0


@pytest.mark.django_db
def test_job_import_confirm_creates_terminal_jobs_from_status_column(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,status,completed_date,closeout_note\n"
            b"AA-001,Replace sensor,completed,2026-04-21,"
            b"Completed before import\n"
            b"AA-001,Replace sensor,cancelled,,Cancelled before import\n"
        ),
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    jobs = list(Job.objects.order_by("pk"))
    assert [job.status for job in jobs] == [JobStatus.COMPLETED, JobStatus.CANCELLED]
    assert [job.completed_date for job in jobs] == [
        parse_date("2026-04-21"),
        None,
    ]
    assert [job.closeout_note for job in jobs] == [
        "Completed before import",
        "Cancelled before import",
    ]


@pytest.mark.django_db
def test_job_import_rejects_unknown_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nBAD-001,Replace sensor\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Unknown site_code" in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_allows_duplicate_site_template_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (b"site_code,template_title\nAA-001,Replace sensor\nAA-001,Replace sensor\n"),
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert content.count("Ready") == 2
    assert "Create jobs" in content


@pytest.mark.django_db
def test_job_import_rejects_assigned_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title,status\nAA-001,Replace sensor,assigned\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Assigned jobs must be planned through a site visit." in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_requires_closeout_note_for_cancelled_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title,status\nAA-001,Replace sensor,cancelled\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "closeout_note is required for cancelled jobs." in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_allows_completed_status_without_closeout_note(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,status,completed_date\n"
            b"AA-001,Replace sensor,completed,2026-04-21\n"
        ),
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    job = Job.objects.get()
    assert job.status == JobStatus.COMPLETED
    assert job.completed_date == parse_date("2026-04-21")
    assert job.closeout_note == ""


@pytest.mark.django_db
def test_job_import_requires_completed_date_for_completed_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title,status\nAA-001,Replace sensor,completed\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "completed_date is required for completed jobs." in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_rejects_invalid_completed_date(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,status,completed_date\n"
            b"AA-001,Replace sensor,completed,21/04/2026\n"
        ),
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "completed_date must use YYYY-MM-DD." in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_rejects_completed_date_for_non_completed_status(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (
            b"site_code,template_title,status,completed_date\n"
            b"AA-001,Replace sensor,unassigned,2026-04-21\n"
        ),
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "completed_date is only allowed for completed jobs." in content
    assert_import_create_button_disabled(content, "Create jobs")


@pytest.mark.django_db
def test_job_import_refresh_revalidates_retained_csv_against_current_data(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        b"site_code,template_title\nAA-001,Replace sensor\n",
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})
    create_site()

    response = client.post(
        reverse("job_import"),
        {"import_action": "refresh"},
        follow=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ready" in content
    assert "Unknown site_code" not in content
    assert "Create jobs" in content

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    assert Job.objects.count() == 1


@pytest.mark.django_db
def test_job_import_review_paginates_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    rows = "\n".join("AA-001,Replace sensor" for _index in range(30))
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        f"site_code,template_title\n{rows}\n".encode(),
        content_type="text/csv",
    )

    response = client.post(reverse("job_import"), {"csv_file": csv_file})

    assert response.status_code == 200
    assert len(response.context["rows"]) == 25
    assert response.context["paginator"].num_pages == 2
    assert response.context["per_page"] == 25


@pytest.mark.django_db
def test_job_import_review_sorts_by_result(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    create_site()
    JobTemplate.objects.create(title="Replace sensor", is_active=True)
    csv_file = SimpleUploadedFile(
        "jobs.csv",
        (b"site_code,template_title\nAA-001,Replace sensor\nAA-001,Missing template\n"),
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.get(reverse("job_import"), {"sort": "result"})

    assert response.status_code == 200
    rows = list(response.context["rows"])
    assert rows[0].error == "Unknown active template_title."
    assert rows[1].is_valid
    assert response.context["current_sort_field"] == "result"


@pytest.mark.django_db
def test_job_template_import_upload_reviews_valid_csv_without_creating_templates(
    client,
):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        (
            b"title,description,estimated_duration_minutes,default_priority,is_active\n"
            b"Asset Renewal Alloy,Replace fittings,120,high,true\n"
        ),
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ready" in content
    assert "Asset Renewal Alloy" in content
    assert JobTemplate.objects.count() == 0


def test_job_template_import_parser_rejects_unsupported_headers():
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title,unexpected\nAsset Renewal Alloy,value\n",
        content_type="text/csv",
    )

    rows = parse_job_template_import_csv(csv_file)

    assert rows[0].error == (
        "CSV headers must include title and may also include "
        "description,estimated_duration_minutes,default_priority,is_active."
    )


def test_job_template_import_parser_rejects_missing_required_headers():
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"description\nReplace fittings\n",
        content_type="text/csv",
    )

    rows = parse_job_template_import_csv(csv_file)

    assert rows[0].error == (
        "CSV headers must include title and may also include "
        "description,estimated_duration_minutes,default_priority,is_active."
    )


def test_job_template_import_parser_rejects_non_utf8_csv():
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"\xff\xfe\x00",
        content_type="text/csv",
    )

    rows = parse_job_template_import_csv(csv_file)

    assert rows[0].error == "CSV file must be UTF-8 encoded."


@pytest.mark.django_db
def test_job_template_import_parser_rejects_empty_csv():
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\n",
        content_type="text/csv",
    )

    rows = parse_job_template_import_csv(csv_file)

    assert rows[0].error == "CSV file does not contain any job template rows."


@pytest.mark.django_db
def test_job_template_import_get_reloads_reviewed_rows_from_session(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\nAsset Renewal Alloy\n",
        content_type="text/csv",
    )
    client.post(reverse("job_template_import"), {"csv_file": csv_file})

    response = client.get(reverse("job_template_import"))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ready" in content
    assert "Asset Renewal Alloy" in content


@pytest.mark.django_db
def test_job_template_import_confirm_without_session_redirects_empty(
    client,
):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(reverse("job_template_import_confirm"))

    assert response.status_code == 302
    assert response.url == reverse("job_template_import")
    assert JobTemplate.objects.count() == 0


@pytest.mark.django_db
def test_job_template_import_confirm_refuses_review_rows_with_errors(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Asset Renewal Alloy")
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\nasset renewal alloy\n",
        content_type="text/csv",
    )
    client.post(reverse("job_template_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_template_import_confirm"))

    assert response.status_code == 302
    assert response.url == reverse("job_template_import")
    assert JobTemplate.objects.count() == 1


@pytest.mark.django_db
def test_job_template_import_page_includes_specification_and_example_path(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_template_import"))

    content = response.content.decode()
    assert response.status_code == 200
    assert (
        "title,description,estimated_duration_minutes,default_priority,is_active"
        in content
    )
    assert "docs/examples/job-template-test-import.csv" in content
    assert "Create job templates" not in content


@pytest.mark.django_db
def test_job_template_import_confirm_creates_templates_from_reviewed_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        (
            b"title,description,estimated_duration_minutes,default_priority,is_active\n"
            b"Asset Renewal Alloy,Replace fittings,120,high,false\n"
            b"GDSP SIM swap,Swap SIM,45,normal,true\n"
        ),
        content_type="text/csv",
    )
    client.post(reverse("job_template_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_template_import_confirm"))

    assert response.status_code == 302
    templates = list(JobTemplate.objects.order_by("title"))
    assert [template.title for template in templates] == [
        "Asset Renewal Alloy",
        "GDSP SIM swap",
    ]
    assert templates[0].priority == Priority.HIGH
    assert templates[0].estimated_duration_minutes == 120
    assert templates[0].is_active is False
    assert templates[0].history.first().history_change_reason == (
        "Imported job template from CSV"
    )


@pytest.mark.django_db
def test_job_template_import_rejects_existing_title(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    JobTemplate.objects.create(title="Asset Renewal Alloy")
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\nasset renewal alloy\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "A job template with this title already exists." in content
    assert_import_create_button_disabled(content, "Create job templates")


@pytest.mark.django_db
def test_job_template_import_rejects_duplicate_title_in_file(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\nAsset Renewal Alloy\nasset renewal alloy\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Duplicate title in this file." in content
    assert_import_create_button_disabled(content, "Create job templates")


@pytest.mark.django_db
def test_job_template_import_rejects_invalid_priority(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title,default_priority\nAsset Renewal Alloy,critical\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "Unknown default_priority." in content
    assert_import_create_button_disabled(content, "Create job templates")


@pytest.mark.django_db
def test_job_template_import_rejects_invalid_estimate(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title,estimated_duration_minutes\nAsset Renewal Alloy,0\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "estimated_duration_minutes must be a positive integer." in content
    assert_import_create_button_disabled(content, "Create job templates")


@pytest.mark.django_db
def test_job_template_import_rejects_invalid_active_flag(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title,is_active\nAsset Renewal Alloy,maybe\n",
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    content = response.content.decode()
    assert response.status_code == 200
    assert "is_active must be true or false." in content
    assert_import_create_button_disabled(content, "Create job templates")


@pytest.mark.django_db
def test_job_template_import_discard_clears_retained_review(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        b"title\nAsset Renewal Alloy\n",
        content_type="text/csv",
    )
    client.post(reverse("job_template_import"), {"csv_file": csv_file})

    response = client.post(
        reverse("job_template_import"),
        {"import_action": "discard"},
        follow=True,
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Ready" not in content
    assert "Review Import" not in content
    assert "Create job templates" not in content


@pytest.mark.django_db
def test_job_template_import_review_paginates_rows(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    rows = "\n".join(f"Template {index}" for index in range(30))
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        f"title\n{rows}\n".encode(),
        content_type="text/csv",
    )

    response = client.post(reverse("job_template_import"), {"csv_file": csv_file})

    assert response.status_code == 200
    assert len(response.context["rows"]) == 25
    assert response.context["paginator"].num_pages == 2
    assert response.context["per_page"] == 25


@pytest.mark.django_db
def test_job_template_import_review_sorts_by_result(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    csv_file = SimpleUploadedFile(
        "job_templates.csv",
        (b"title,description\nAsset Renewal Alloy,Valid template\n,Missing title\n"),
        content_type="text/csv",
    )
    client.post(reverse("job_template_import"), {"csv_file": csv_file})

    response = client.get(reverse("job_template_import"), {"sort": "result"})

    assert response.status_code == 200
    rows = list(response.context["rows"])
    assert rows[0].error == "Missing title."
    assert rows[1].is_valid
    assert response.context["current_sort_field"] == "result"


@pytest.mark.django_db
def test_requirement_delete_removes_requirement_and_returns_to_job(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    requirement = Requirement.objects.create(job=job, name="Cable")

    response = client.post(reverse("requirement_delete", args=[requirement.pk]))

    assert response.status_code == 302
    assert response.url == job.get_requirements_url()
    assert not Requirement.objects.filter(pk=requirement.pk).exists()


@pytest.mark.django_db
def test_requirement_delete_confirmation_names_requirement_and_job(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    job = Job.objects.create(site=site, title="Inspect cabinet")
    requirement = Requirement.objects.create(job=job, name="Cable")

    response = client.get(reverse("requirement_delete", args=[requirement.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Delete job requirement" in content
    assert "delete" in content
    assert "Cable" in content
    assert "Inspect cabinet" in content


@pytest.mark.django_db
def test_template_requirement_delete_removes_requirement_and_returns_to_template(
    client,
):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    template = JobTemplate.objects.create(title="Replace sensor")
    requirement = TemplateRequirement.objects.create(
        job_template=template, name="Cable"
    )

    response = client.post(
        reverse("template_requirement_delete", args=[requirement.pk])
    )

    assert response.status_code == 302
    assert response.url == template.get_absolute_url()
    assert not TemplateRequirement.objects.filter(pk=requirement.pk).exists()


@pytest.mark.django_db
def test_template_requirement_delete_confirmation_names_requirement_and_template(
    client,
):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    template = JobTemplate.objects.create(title="Replace sensor")
    requirement = TemplateRequirement.objects.create(
        job_template=template, name="Cable"
    )

    response = client.get(reverse("template_requirement_delete", args=[requirement.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Delete job template requirement" in content
    assert "delete" in content
    assert "Cable" in content
    assert "Replace sensor" in content
