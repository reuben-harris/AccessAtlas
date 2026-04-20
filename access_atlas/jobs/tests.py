import pytest

from access_atlas.jobs.models import Job, JobTemplate, TemplateRequirement
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
