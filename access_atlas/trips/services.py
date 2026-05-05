from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from simple_history.utils import update_change_reason

from access_atlas.jobs.models import JobStatus

from .models import SiteVisitJob, SiteVisitStatus, Trip, TripApproval, TripStatus

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
        and not assignments.exclude(job__status=JobStatus.ASSIGNED).exists()
    )
    return TripCancelSummary(
        site_visits_to_skip=site_visits.filter(status=SiteVisitStatus.PLANNED).count(),
        jobs_to_return=assignments.filter(job__status=JobStatus.ASSIGNED).count(),
        can_cancel=can_cancel,
    )


def user_can_approve_trip(trip: Trip, user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if trip.is_terminal or trip.status not in {
        TripStatus.SUBMITTED,
        TripStatus.APPROVED,
    }:
        return False
    if trip.trip_leader_id == user.pk:
        return False
    return not trip.current_approvals().filter(approver=user).exists()


@transaction.atomic
def submit_trip_for_approval(trip: Trip, user) -> None:
    if not trip.can_submit_for_approval:
        raise ValidationError("This trip cannot be submitted for approval.")

    trip.approval_round += 1
    trip.status = TripStatus.SUBMITTED
    trip.submitted_by = user
    trip.submitted_at = timezone.now()
    trip.approved_at = None
    trip.save(
        update_fields=[
            "approval_round",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_at",
            "updated_at",
        ]
    )
    update_change_reason(trip, "Submitted trip for approval")


@transaction.atomic
def approve_trip(trip: Trip, user) -> TripApproval:
    if not user_can_approve_trip(trip, user):
        raise ValidationError("You cannot approve this trip.")

    approval = TripApproval.objects.create(
        trip=trip,
        approver=user,
        approval_round=trip.approval_round,
    )

    if trip.status == TripStatus.SUBMITTED:
        trip.status = TripStatus.APPROVED
        trip.approved_at = approval.created_at
        trip.save(update_fields=["status", "approved_at", "updated_at"])
        update_change_reason(trip, "Approved trip")
    else:
        trip.save(update_fields=["updated_at"])
        update_change_reason(trip, "Recorded additional trip approval")

    return approval


@transaction.atomic
def invalidate_trip_approval(trip: Trip, user, reason: str) -> bool:
    if trip.status != TripStatus.APPROVED:
        return False

    trip.approval_round += 1
    trip.status = TripStatus.SUBMITTED
    trip.submitted_by = user
    trip.submitted_at = timezone.now()
    trip.approved_at = None
    trip.save(
        update_fields=[
            "approval_round",
            "status",
            "submitted_by",
            "submitted_at",
            "approved_at",
            "updated_at",
        ]
    )
    update_change_reason(trip, reason)
    return True


@transaction.atomic
def assign_job_to_site_visit(site_visit, job) -> SiteVisitJob:
    if job.status != JobStatus.UNASSIGNED:
        raise ValidationError("Only unassigned jobs can be assigned to a site visit.")

    assignment = SiteVisitJob(site_visit=site_visit, job=job)
    assignment.full_clean()
    assignment._change_reason = "Assigned job to site visit"
    assignment.save()

    job.status = JobStatus.ASSIGNED
    job.save(update_fields=["status", "updated_at"])
    update_change_reason(job, "Assigned to site visit")
    return assignment


@transaction.atomic
def unassign_site_visit_job(assignment: SiteVisitJob) -> None:
    job = assignment.job
    assignment._change_reason = "Unassigned job from site visit"
    assignment.delete()
    if job.status == JobStatus.ASSIGNED:
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

    for assignment in get_trip_assignments(trip).filter(job__status=JobStatus.ASSIGNED):
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
        job__status__in=[JobStatus.ASSIGNED, JobStatus.UNASSIGNED]
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
