from collections.abc import Iterable
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from access_atlas.core.bulk_edit import (
    BulkEditIssue,
    BulkEditResult,
    BulkEditValidation,
    bulk_edit_objects,
    validate_bulk_edit_objects,
)
from access_atlas.sites.models import Site

from .models import Job, JobStatus, JobTemplate, Requirement, WorkProgramme

BulkJobEditIssue = BulkEditIssue
BulkJobEditResult = BulkEditResult
BulkJobEditValidation = BulkEditValidation


@transaction.atomic
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


def assign_job_to_work_programme(job: Job, work_programme: WorkProgramme) -> Job:
    """Attach an existing unprogrammed job to a work programme."""
    if job.work_programme_id is not None:
        raise ValidationError("Only jobs without a work programme can be assigned.")

    job.work_programme = work_programme
    job._change_reason = "Assigned job to work programme"
    job.save()
    return job


@transaction.atomic
def assign_jobs_to_work_programme(
    jobs: Iterable[Job],
    work_programme: WorkProgramme,
) -> int:
    """Attach multiple jobs to a work programme as one workflow."""
    selected_jobs = list(jobs)
    for job in selected_jobs:
        assign_job_to_work_programme(job, work_programme)
    return len(selected_jobs)


def job_edit_frozen_reason(job: Job) -> str:
    """Return why normal job editing is blocked for terminal-trip assignments."""
    assignment = getattr(job, "site_visit_assignment", None)
    if assignment is None or not assignment.site_visit.trip.is_terminal:
        return ""
    trip = assignment.site_visit.trip
    return (
        f"This job is assigned to {trip.get_status_display().lower()} trip "
        f'"{trip.name}", so normal job editing is frozen.'
    )


def bulk_editable_jobs_queryset(queryset):
    """Return jobs selectable by the bulk-edit UI."""
    from access_atlas.trips.models import TripStatus

    return queryset.exclude(
        site_visit_assignment__site_visit__trip__status__in=[
            TripStatus.COMPLETED,
            TripStatus.CANCELLED,
        ]
    )


def _apply_bulk_job_changes(
    job: Job,
    *,
    priority: str = "",
    work_programme: WorkProgramme | None = None,
    clear_work_programme: bool = False,
    status: str = "",
    completed_date: date | None = None,
    clear_completed_date: bool = False,
    closeout_note: str = "",
) -> bool:
    changed = False
    if priority and job.priority != priority:
        job.priority = priority
        changed = True

    if clear_work_programme:
        if job.work_programme_id is not None:
            job.work_programme = None
            changed = True
    elif work_programme is not None and job.work_programme_id != work_programme.pk:
        job.work_programme = work_programme
        changed = True

    if clear_completed_date and job.completed_date is not None:
        job.completed_date = None
        changed = True

    if status:
        if job.status != status:
            job.status = status
            changed = True
        if (
            status == JobStatus.COMPLETED
            and completed_date is not None
            and job.completed_date != completed_date
        ):
            job.completed_date = completed_date
            changed = True
        if status == JobStatus.CANCELLED and job.closeout_note != closeout_note:
            job.closeout_note = closeout_note
            changed = True

    return changed


def _bulk_job_blocker_reason(job: Job, *, status: str = "") -> str:
    frozen_reason = job_edit_frozen_reason(job)
    if frozen_reason:
        return frozen_reason
    if status and job.is_assigned:
        return (
            "Assigned jobs cannot have status changed by bulk edit "
            "because trip closeout manages them."
        )
    return ""


def validate_bulk_edit_jobs(
    jobs: Iterable[Job],
    *,
    priority: str = "",
    work_programme: WorkProgramme | None = None,
    clear_work_programme: bool = False,
    status: str = "",
    completed_date: date | None = None,
    clear_completed_date: bool = False,
    closeout_note: str = "",
) -> BulkJobEditValidation:
    """Check every selected job before the bulk edit saves anything."""

    def apply_changes(draft_job: Job) -> bool:
        _apply_bulk_job_changes(
            draft_job,
            priority=priority,
            work_programme=work_programme,
            clear_work_programme=clear_work_programme,
            status=status,
            completed_date=completed_date,
            clear_completed_date=clear_completed_date,
            closeout_note=closeout_note,
        )
        return True

    return validate_bulk_edit_objects(
        jobs,
        apply_changes=apply_changes,
        blocker_reason=lambda job: _bulk_job_blocker_reason(job, status=status),
    )


@transaction.atomic
def bulk_edit_jobs(
    jobs: Iterable[Job],
    *,
    priority: str = "",
    work_programme: WorkProgramme | None = None,
    clear_work_programme: bool = False,
    status: str = "",
    completed_date: date | None = None,
    clear_completed_date: bool = False,
    closeout_note: str = "",
) -> BulkJobEditResult:
    """Apply the supported bulk job edits after all selected jobs validate."""

    def apply_changes(job: Job) -> bool:
        return _apply_bulk_job_changes(
            job,
            priority=priority,
            work_programme=work_programme,
            clear_work_programme=clear_work_programme,
            status=status,
            completed_date=completed_date,
            clear_completed_date=clear_completed_date,
            closeout_note=closeout_note,
        )

    return bulk_edit_objects(
        jobs,
        apply_changes=apply_changes,
        validate=lambda selected_jobs: validate_bulk_edit_jobs(
            selected_jobs,
            priority=priority,
            work_programme=work_programme,
            clear_work_programme=clear_work_programme,
            status=status,
            completed_date=completed_date,
            clear_completed_date=clear_completed_date,
            closeout_note=closeout_note,
        ),
        change_reason="Bulk edited job",
    )
