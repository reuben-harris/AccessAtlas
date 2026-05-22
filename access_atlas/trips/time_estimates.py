from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import F, Prefetch
from django.utils import timezone
from django.utils.formats import date_format

from .models import SiteVisit, SiteVisitJob, Trip


@dataclass(frozen=True)
class TripTimeJob:
    title: str
    url: str
    estimated_duration_minutes: int | None
    duration_label: str


@dataclass(frozen=True)
class TripTimeVisit:
    site_visit: SiteVisit
    time_label: str
    estimate_note: str
    jobs: list[TripTimeJob]
    job_estimate_minutes: int
    job_estimate_label: str
    missing_job_estimate_count: int


@dataclass(frozen=True)
class TripTimeDay:
    day: date | None
    label: str
    visits: list[TripTimeVisit]
    job_estimate_minutes: int
    job_estimate_label: str
    missing_job_estimate_count: int


def format_duration(minutes: int | None) -> str:
    if minutes is None:
        return "-"
    hours, remainder = divmod(minutes, 60)
    if hours and remainder:
        return f"{hours} h {remainder} min"
    if hours:
        return f"{hours} h"
    return f"{remainder} min"


def build_trip_time_breakdown(trip: Trip) -> list[TripTimeDay]:
    """Build a read-only trip timeline from scheduled site visits and job estimates."""

    assignment_queryset = SiteVisitJob.objects.select_related("job").order_by(
        "assigned_at",
        "job__title",
    )
    site_visits = (
        SiteVisit.objects.filter(trip=trip)
        .select_related("site")
        .prefetch_related(Prefetch("sitevisitjob_set", queryset=assignment_queryset))
        .order_by(
            F("planned_day").asc(nulls_last=True),
            F("planned_start").asc(nulls_last=True),
            "site__code",
            "id",
        )
    )

    visits_by_day: dict[date | None, list[TripTimeVisit]] = {}
    for site_visit in site_visits:
        visit = build_trip_time_visit(site_visit)
        visits_by_day.setdefault(site_visit.planned_day, []).append(visit)

    days = []
    current_day = trip.start_date
    while current_day <= trip.end_date:
        days.append(
            build_trip_time_day(current_day, visits_by_day.pop(current_day, []))
        )
        current_day += timedelta(days=1)

    if visits_by_day:
        unscheduled_visits = []
        for day_visits in visits_by_day.values():
            unscheduled_visits.extend(day_visits)
        days.append(build_trip_time_day(None, unscheduled_visits))

    return days


def build_trip_time_visit(site_visit: SiteVisit) -> TripTimeVisit:
    assignments = list(site_visit.sitevisitjob_set.all())
    jobs = [
        TripTimeJob(
            title=assignment.job.title,
            url=assignment.job.get_absolute_url(),
            estimated_duration_minutes=assignment.job.estimated_duration_minutes,
            duration_label=format_duration(assignment.job.estimated_duration_minutes),
        )
        for assignment in assignments
    ]
    job_estimate_minutes = sum(
        job.estimated_duration_minutes or 0
        for job in jobs
        if job.estimated_duration_minutes is not None
    )
    missing_job_estimate_count = sum(
        1 for job in jobs if job.estimated_duration_minutes is None
    )

    return TripTimeVisit(
        site_visit=site_visit,
        time_label=site_visit_time_label(
            site_visit,
            job_estimate_minutes=job_estimate_minutes,
            missing_job_estimate_count=missing_job_estimate_count,
        ),
        estimate_note=site_visit_estimate_note(
            site_visit,
            job_estimate_minutes=job_estimate_minutes,
            missing_job_estimate_count=missing_job_estimate_count,
        ),
        jobs=jobs,
        job_estimate_minutes=job_estimate_minutes,
        job_estimate_label=format_duration(job_estimate_minutes),
        missing_job_estimate_count=missing_job_estimate_count,
    )


def build_trip_time_day(day: date | None, visits: list[TripTimeVisit]) -> TripTimeDay:
    missing_job_estimate_count = sum(
        visit.missing_job_estimate_count for visit in visits
    )
    job_estimate_minutes = sum(visit.job_estimate_minutes for visit in visits)
    return TripTimeDay(
        day=day,
        label=date_format(day, "l j M Y") if day is not None else "Unscheduled",
        visits=visits,
        job_estimate_minutes=job_estimate_minutes,
        job_estimate_label=format_duration(job_estimate_minutes),
        missing_job_estimate_count=missing_job_estimate_count,
    )


def site_visit_time_label(
    site_visit: SiteVisit,
    *,
    job_estimate_minutes: int,
    missing_job_estimate_count: int,
) -> str:
    if site_visit.planned_start is None:
        return "Time not set"

    start = timezone.localtime(site_visit.planned_start)
    if site_visit.planned_end is not None:
        end = timezone.localtime(site_visit.planned_end)
        return f"{date_format(start, 'H:i')} - {date_format(end, 'H:i')}"

    if job_estimate_minutes and missing_job_estimate_count == 0:
        estimated_end = start + timedelta(minutes=job_estimate_minutes)
        return f"{date_format(start, 'H:i')} - {date_format(estimated_end, 'H:i')} est"

    return date_format(start, "H:i")


def site_visit_estimate_note(
    site_visit: SiteVisit,
    *,
    job_estimate_minutes: int,
    missing_job_estimate_count: int,
) -> str:
    if site_visit.planned_start is None:
        return "Set a visit start time to place this in the day sequence."
    if site_visit.planned_end is not None:
        return ""
    if missing_job_estimate_count:
        return "End time cannot be estimated until all assigned jobs have estimates."
    if job_estimate_minutes:
        return "End time estimated from assigned job durations."
    return "Add job estimates to calculate an estimated end time."
