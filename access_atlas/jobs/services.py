from access_atlas.sites.models import Site

from .models import Job, JobTemplate, Requirement


def create_job_from_template(site: Site, template: JobTemplate) -> Job:
    job = Job.objects.create(
        site=site,
        template=template,
        title=template.title,
        description=template.description,
        estimated_duration_minutes=template.estimated_duration_minutes,
        priority=template.priority,
        notes=template.notes,
    )
    Requirement.objects.bulk_create(
        [
            Requirement(
                job=job,
                requirement_type=requirement.requirement_type,
                name=requirement.name,
                quantity=requirement.quantity,
                notes=requirement.notes,
                is_required=requirement.is_required,
            )
            for requirement in template.template_requirements.all()
        ]
    )
    return job
