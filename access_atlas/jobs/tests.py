import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    set_user_preference,
)
from access_atlas.jobs.forms import JobForm, JobFromTemplateForm
from access_atlas.jobs.models import Job, JobStatus, JobTemplate, TemplateRequirement
from access_atlas.jobs.services import create_job_from_template
from access_atlas.sites.models import Site


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
def test_job_cannot_be_manually_set_to_planned_without_assignment():
    site = create_site()
    job = Job(site=site, title="Inspect cabinet", status="planned")

    with pytest.raises(ValidationError):
        job.full_clean()


@pytest.mark.django_db
def test_cancelled_job_requires_reason():
    site = create_site()
    job = Job(site=site, title="Inspect cabinet", status="cancelled")

    with pytest.raises(ValidationError):
        job.full_clean()

    job.cancelled_reason = "No longer required."
    job.full_clean()


def test_job_form_does_not_offer_planned_status():
    form = JobForm()

    status_values = [value for value, _label in form.fields["status"].choices]

    assert "planned" not in status_values
    assert "blocked" not in status_values


def test_job_form_marks_site_select_as_searchable():
    form = JobForm()

    attrs = form.fields["site"].widget.attrs

    assert attrs["data-searchable-select"] == "true"
    assert attrs["data-search-placeholder"] == "Search sites"


@pytest.mark.django_db
def test_job_from_template_form_marks_site_select_as_searchable():
    site = create_site()

    form = JobFromTemplateForm(site_queryset=Site.objects.filter(pk=site.pk))
    site_attrs = form.fields["site"].widget.attrs
    template_attrs = form.fields["template"].widget.attrs

    assert site_attrs["data-searchable-select"] == "true"
    assert site_attrs["data-search-placeholder"] == "Search sites"
    assert template_attrs["data-searchable-select"] == "true"
    assert template_attrs["data-search-placeholder"] == "Search templates"


@pytest.mark.django_db
def test_job_list_links_to_map_view(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("job_list"))

    assert response.status_code == 200
    assert reverse("job_map") in response.content.decode()


@pytest.mark.django_db
def test_job_map_includes_jobs_and_status_layers(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = create_site()
    Job.objects.create(site=site, title="Inspect cabinet")
    Job.objects.create(site=site, title="Closed work", status=JobStatus.COMPLETED)
    Job.objects.create(
        site=site,
        title="Cancelled work",
        status=JobStatus.CANCELLED,
        cancelled_reason="No longer required.",
    )

    response = client.get(reverse("job_map"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "AA-001" in content
    assert "Inspect cabinet" in content
    assert "Closed work" in content
    assert "Cancelled work" in content
    assert "job-map-status-layers" in content
    assert '"visible": true' in content
    assert '"visible": false' in content


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
    assert (
        '"value": "completed", "label": "Completed", "color": "#2fb344", '
        '"rank": 10, "visible": true'
    ) in content
    assert (
        '"value": "planned", "label": "Planned", "color": "#206bc4", '
        '"rank": 30, "visible": false'
    ) in content
    assert '"viewport": {"lat": -41.2, "lng": 174.7, "zoom": 8}' in content


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
def test_job_import_rejects_duplicate_rows(client):
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
    assert "Duplicate site_code/template_title row" in content
    assert "Create jobs" not in content
