from typing import Any

from .models import Job

TRIP_MANAGED_JOB_FIELDS = ("site", "status", "completed_date", "closeout_note")
TRIP_MANAGED_JOB_SITE_HELP_TEXT = (
    "Site is managed by the trip workflow while this job is assigned to a trip."
)
TRIP_MANAGED_JOB_OUTCOME_HELP_TEXT = (
    "This field is managed by the trip workflow while the job is assigned to a trip."
)
TRIP_MANAGED_JOB_FIELD_HELP_TEXT = {
    "site": TRIP_MANAGED_JOB_SITE_HELP_TEXT,
    "status": TRIP_MANAGED_JOB_OUTCOME_HELP_TEXT,
    "completed_date": TRIP_MANAGED_JOB_OUTCOME_HELP_TEXT,
    "closeout_note": TRIP_MANAGED_JOB_OUTCOME_HELP_TEXT,
}
TRIP_MANAGED_JOB_FIELD_API_ERROR = (
    "Assigned jobs cannot change this field because the trip workflow manages it."
)
TRIP_MANAGED_JOB_BULK_EDIT_ERRORS = {
    "status": (
        "Assigned jobs cannot have status changed by bulk edit "
        "because the trip workflow manages that field."
    ),
    "completed_date": (
        "Assigned jobs cannot have completed date changed by bulk edit "
        "because the trip workflow manages that field."
    ),
}


def trip_managed_job_fields_for(job: Job) -> tuple[str, ...]:
    """Return Job fields controlled by the trip workflow for this instance."""
    if job.pk and job.is_assigned:
        return TRIP_MANAGED_JOB_FIELDS
    return ()


def trip_managed_job_field_help_text(field_name: str) -> str:
    """Return form help text for a trip workflow-managed Job field."""
    return TRIP_MANAGED_JOB_FIELD_HELP_TEXT[field_name]


def trip_managed_job_field_changed(
    job: Job,
    field_name: str,
    submitted_value: Any,
) -> bool:
    """Compare protected API input with the stored Job field value."""
    if field_name == "site":
        submitted_pk = getattr(submitted_value, "pk", submitted_value)
        return job.site_id != submitted_pk
    return getattr(job, field_name) != submitted_value


def trip_managed_job_bulk_edit_error(field_name: str) -> str:
    """Return the bulk edit blocker message for a protected Job field."""
    return TRIP_MANAGED_JOB_BULK_EDIT_ERRORS[field_name]
