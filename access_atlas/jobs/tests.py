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
    AssignWorkProgrammeJobForm,
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
    create_job_from_template,
)
from access_atlas.jobs.template_imports import parse_job_template_import_csv
from access_atlas.sites.models import Site
from access_atlas.trips.models import SiteVisit, Trip
from access_atlas.trips.services import assign_job_to_site_visit


def create_site(code="AA-001"):
    return Site.objects.create(
        source_name="dummy",
        external_id=code,
        code=code,
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )


@pytest.mark.django_db
def test_create_job_from_template_copies_template_and_requirements():
    site = create_site()
    template = JobTemplate.objects.create(
        title="Replace sensor",
        description="Replace the field sensor.",
        estimated_duration_minutes=90,
        notes="Bring spares.",
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
            "notes": "",
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
def test_terminal_job_requires_closeout_note():
    site = create_site()
    job = Job(site=site, title="Inspect cabinet", status="cancelled")

    with pytest.raises(ValidationError):
        job.full_clean()

    job.status = JobStatus.COMPLETED
    with pytest.raises(ValidationError):
        job.full_clean()

    job.closeout_note = "Work completed during historical import."
    job.full_clean()


def test_job_form_does_not_offer_assigned_status():
    form = JobForm()

    status_values = [value for value, _label in form.fields["status"].choices]

    assert "assigned" not in status_values
    assert "blocked" not in status_values


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
            "notes": "",
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
            "notes": "",
        },
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.work_programme is None


@pytest.mark.django_db
def test_editing_assigned_job_on_approved_trip_requires_confirmation_and_resubmits(
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
    client.force_login(leader)

    initial_response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "template": "",
            "title": "Updated title",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.ASSIGNED,
            "notes": "",
        },
    )

    assert initial_response.status_code == 200
    assert b"Approval reset" in initial_response.content

    response = client.post(
        reverse("job_update", kwargs={"pk": job.pk}),
        {
            "site": site.pk,
            "template": "",
            "title": "Updated title",
            "description": "",
            "estimated_duration_minutes": "",
            "priority": "normal",
            "status": JobStatus.ASSIGNED,
            "notes": "",
            "confirm_trip_approval_reset": "on",
        },
    )

    assert response.status_code == 302
    trip.refresh_from_db()
    job.refresh_from_db()
    assert job.title == "Updated title"
    assert trip.status == TripStatus.SUBMITTED
    assert trip.approval_round == 2


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
            "notes": "",
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
def test_job_template_list_links_to_import(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_template_list"))

    assert response.status_code == 200
    assert reverse("job_template_import") in response.content.decode()


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
    assert map_preference["value"]["viewport"] == {
        "lat": -41.2,
        "lng": 174.7,
        "zoom": 8,
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
        "status,closeout_note,work_programme."
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
        "status,closeout_note,work_programme."
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
    assert "site_code,template_title,status,closeout_note,work_programme" in content
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
            b"site_code,template_title,status,closeout_note\n"
            b"AA-001,Replace sensor,completed,Completed before import\n"
            b"AA-001,Replace sensor,cancelled,Cancelled before import\n"
        ),
        content_type="text/csv",
    )
    client.post(reverse("job_import"), {"csv_file": csv_file})

    response = client.post(reverse("job_import_confirm"))

    assert response.status_code == 302
    jobs = list(Job.objects.order_by("pk"))
    assert [job.status for job in jobs] == [JobStatus.COMPLETED, JobStatus.CANCELLED]
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
    assert "Create jobs" not in content


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
    assert "Create jobs" not in content


@pytest.mark.django_db
def test_job_import_requires_closeout_note_for_terminal_status(client):
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
    assert "closeout_note is required for completed or cancelled jobs." in content
    assert "Create jobs" not in content


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
            b"title,description,estimated_duration_minutes,default_priority,notes,is_active\n"
            b"Asset Renewal Alloy,Replace fittings,120,high,Bring spares,true\n"
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
        "description,estimated_duration_minutes,default_priority,notes,is_active."
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
        "description,estimated_duration_minutes,default_priority,notes,is_active."
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
        "title,description,estimated_duration_minutes,default_priority,notes,is_active"
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
            b"title,description,estimated_duration_minutes,default_priority,notes,is_active\n"
            b"Asset Renewal Alloy,Replace fittings,120,high,Bring spares,false\n"
            b"GDSP SIM swap,Swap SIM,45,normal,,true\n"
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
    assert "Create job templates" not in content


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
    assert "Create job templates" not in content


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
    assert "Create job templates" not in content


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
    assert "Create job templates" not in content


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
    assert response.url == job.get_absolute_url()
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
