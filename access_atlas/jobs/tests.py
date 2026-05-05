import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    list_sort_preference_key,
    set_user_preference,
)
from access_atlas.core.test_utils import parse_json_script
from access_atlas.jobs.forms import JobForm, JobFromTemplateForm
from access_atlas.jobs.models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
)
from access_atlas.jobs.services import create_job_from_template
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

    assert site_widget.url == "autocomplete_sites"
    assert site_widget.label_field == "label"
    assert template_widget.url == "autocomplete_job_templates"
    assert template_widget.label_field == "title"


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
    assert any(layer["visible"] is True for layer in status_layers)
    assert any(layer["visible"] is False for layer in status_layers)


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
def test_job_map_uses_saved_status_preference(client):
    user = User.objects.create_user(email="user@example.com")
    set_user_preference(
        user,
        JOBS_MAP_PREFERENCE_KEY,
        {
            "visible_statuses": [JobStatus.COMPLETED],
            "viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8},
        },
    )
    client.force_login(user)

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    content = response.content.decode()
    status_layers = parse_json_script(content, "job-map-status-layers")
    completed_layer = next(
        layer for layer in status_layers if layer["value"] == JobStatus.COMPLETED
    )
    assigned_layer = next(
        layer for layer in status_layers if layer["value"] == JobStatus.ASSIGNED
    )
    assert completed_layer["visible"] is True
    assert assigned_layer["visible"] is False
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
