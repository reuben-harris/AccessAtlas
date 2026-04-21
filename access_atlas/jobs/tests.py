import pytest
from django.core.exceptions import ValidationError
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


@pytest.mark.django_db
def test_create_job_from_template_copies_template_and_requirements():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
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
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )

    job = Job.objects.create(site=site, title="Inspect cabinet")

    assert job.status == "unassigned"


@pytest.mark.django_db
def test_job_cannot_be_manually_set_to_planned_without_assignment():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    job = Job(site=site, title="Inspect cabinet", status="planned")

    with pytest.raises(ValidationError):
        job.full_clean()


@pytest.mark.django_db
def test_cancelled_job_requires_reason():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
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
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )

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
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
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
