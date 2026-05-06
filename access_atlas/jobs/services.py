from access_atlas.sites.models import Site

from .models import Job, JobTemplate, Requirement, WorkProgramme


def create_job_from_template(
    site: Site,
    template: JobTemplate,
    change_reason: str = "Created job from template",
    work_programme: WorkProgramme | None = None,
) -> Job:
    job = Job(
        site=site,
        template=template,
        work_programme=work_programme,
        title=template.title,
        description=template.description,
        estimated_duration_minutes=template.estimated_duration_minutes,
        priority=template.priority,
        notes=template.notes,
    )
    job._change_reason = change_reason
    job.save()

    for template_requirement in template.template_requirements.all():
        requirement = Requirement(
            job=job,
            requirement_type=template_requirement.requirement_type,
            name=template_requirement.name,
            quantity=template_requirement.quantity,
            notes=template_requirement.notes,
            is_required=template_requirement.is_required,
        )
        requirement._change_reason = "Copied requirement from job template"
        requirement.save()

    return job
