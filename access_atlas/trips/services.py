from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from simple_history.utils import update_change_reason

from access_atlas.jobs.models import JobStatus

from .models import SiteVisitJob, SiteVisitStatus, Trip, TripStatus

JOB_OUTCOME_COMPLETED = "completed"
JOB_OUTCOME_RETURN = "return"
JOB_OUTCOME_CANCELLED = "cancelled"


@dataclass(frozen=True)
class TripCancelSummary:
    site_visits_to_skip: int
    jobs_to_return: int
    can_cancel: bool


def get_trip_assignments(trip: Trip):
    return SiteVisitJob.objects.select_related(
        "job", "site_visit", "site_visit__site"
    ).filter(site_visit__trip=trip)


def get_trip_cancel_summary(trip: Trip) -> TripCancelSummary:
    site_visits = trip.site_visits.all()
    assignments = get_trip_assignments(trip)
    can_cancel = (
        not site_visits.exclude(status=SiteVisitStatus.PLANNED).exists()
        and not assignments.exclude(job__status=JobStatus.PLANNED).exists()
    )
    return TripCancelSummary(
        site_visits_to_skip=site_visits.filter(status=SiteVisitStatus.PLANNED).count(),
        jobs_to_return=assignments.filter(job__status=JobStatus.PLANNED).count(),
        can_cancel=can_cancel,
    )


@transaction.atomic
def assign_job_to_site_visit(site_visit, job) -> SiteVisitJob:
    if job.status != JobStatus.UNASSIGNED:
        raise ValidationError("Only unassigned jobs can be assigned to a site visit.")

    assignment = SiteVisitJob(site_visit=site_visit, job=job)
    assignment.full_clean()
    assignment._change_reason = "Assigned job to site visit"
    assignment.save()

    job.status = JobStatus.PLANNED
    job.save(update_fields=["status", "updated_at"])
    update_change_reason(job, "Assigned to site visit")
    return assignment


@transaction.atomic
def unassign_site_visit_job(assignment: SiteVisitJob) -> None:
    job = assignment.job
    assignment._change_reason = "Unassigned job from site visit"
    assignment.delete()
    if job.status == JobStatus.PLANNED:
        job.status = JobStatus.UNASSIGNED
        job.save(update_fields=["status", "updated_at"])
        update_change_reason(job, "Unassigned from site visit")


@transaction.atomic
def cancel_trip(trip: Trip) -> TripCancelSummary:
    summary = get_trip_cancel_summary(trip)
    if not summary.can_cancel:
        raise ValidationError(
            "This trip has site visits or jobs that have moved forward. "
            "Close the trip instead."
        )

    for assignment in get_trip_assignments(trip).filter(job__status=JobStatus.PLANNED):
        job = assignment.job
        assignment._change_reason = "Returned job during trip cancellation"
        assignment.delete()
        job.status = JobStatus.UNASSIGNED
        job.save(update_fields=["status", "updated_at"])
        update_change_reason(job, "Returned to unassigned during trip cancellation")

    for site_visit in trip.site_visits.filter(status=SiteVisitStatus.PLANNED):
        site_visit.status = SiteVisitStatus.SKIPPED
        site_visit.save(update_fields=["status", "updated_at"])
        update_change_reason(site_visit, "Skipped during trip cancellation")

    trip.status = TripStatus.CANCELLED
    trip.save(update_fields=["status", "updated_at"])
    update_change_reason(trip, "Cancelled trip")
    return summary


@transaction.atomic
def close_trip(trip: Trip, cleaned_data: dict) -> None:
    for site_visit in trip.site_visits.all():
        site_visit.status = cleaned_data[f"site_visit_{site_visit.pk}"]
        site_visit.save(update_fields=["status", "updated_at"])
        update_change_reason(site_visit, "Resolved during trip closeout")

    for assignment in get_trip_assignments(trip).filter(
        job__status__in=[JobStatus.PLANNED, JobStatus.UNASSIGNED]
    ):
        job = assignment.job
        outcome = cleaned_data[f"job_{assignment.pk}_outcome"]
        if outcome == JOB_OUTCOME_COMPLETED:
            job.status = JobStatus.COMPLETED
            job.cancelled_reason = ""
            job.save(update_fields=["status", "cancelled_reason", "updated_at"])
            update_change_reason(job, "Completed during trip closeout")
        elif outcome == JOB_OUTCOME_RETURN:
            assignment._change_reason = "Returned job during trip closeout"
            assignment.delete()
            job.status = JobStatus.UNASSIGNED
            job.cancelled_reason = ""
            job.save(update_fields=["status", "cancelled_reason", "updated_at"])
            update_change_reason(job, "Returned to unassigned during trip closeout")
        elif outcome == JOB_OUTCOME_CANCELLED:
            job.status = JobStatus.CANCELLED
            job.cancelled_reason = cleaned_data[
                f"job_{assignment.pk}_cancelled_reason"
            ].strip()
            job.save(update_fields=["status", "cancelled_reason", "updated_at"])
            update_change_reason(job, "Cancelled during trip closeout")

    trip.status = TripStatus.COMPLETED
    trip.save(update_fields=["status", "updated_at"])
    update_change_reason(trip, "Closed trip")
