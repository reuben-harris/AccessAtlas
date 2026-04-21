from dataclasses import dataclass
from itertools import chain

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from access_atlas.jobs.models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
)
from access_atlas.sites.models import Site
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip, TripStatus


@dataclass(frozen=True)
class HistoryEntry:
    date: object
    action: str
    object_type: str
    object_display: str
    object_url: str
    user: object


HISTORY_MODELS = [
    Site,
    JobTemplate,
    TemplateRequirement,
    Job,
    Requirement,
    Trip,
    SiteVisit,
    SiteVisitJob,
]


def build_history_entry(record) -> HistoryEntry:
    instance = record.instance
    object_url = ""
    if record.history_type != "-" and hasattr(instance, "get_absolute_url"):
        object_url = instance.get_absolute_url()
    return HistoryEntry(
        date=record.history_date,
        action=record.get_history_type_display(),
        object_type=instance._meta.verbose_name.title(),
        object_display=str(instance),
        object_url=object_url,
        user=record.history_user,
    )


@login_required
def dashboard(request):
    context = {
        "planned_trips": Trip.objects.exclude(status=TripStatus.COMPLETED)[:5],
        "unassigned_jobs": Job.objects.filter(
            status=JobStatus.UNASSIGNED,
            site_visit_assignment__isnull=True,
        )[:10],
        "blocked_jobs": Job.objects.filter(status=JobStatus.BLOCKED)[:10],
        "site_count": Site.objects.count(),
        "job_template_count": JobTemplate.objects.filter(is_active=True).count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    results = {
        "sites": [],
        "jobs": [],
        "job_templates": [],
        "trips": [],
    }
    if query:
        results["sites"] = Site.objects.filter(
            Q(code__icontains=query) | Q(name__icontains=query)
        )[:10]
        results["jobs"] = Job.objects.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(site__code__icontains=query)
            | Q(site__name__icontains=query)
        )[:10]
        results["job_templates"] = JobTemplate.objects.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )[:10]
        results["trips"] = Trip.objects.filter(
            Q(name__icontains=query) | Q(notes__icontains=query)
        )[:10]
    return render(request, "core/search.html", {"query": query, "results": results})


@login_required
def global_history(request):
    records = chain.from_iterable(
        model.history.select_related("history_user").all()[:25]
        for model in HISTORY_MODELS
    )
    entries = sorted(
        (build_history_entry(record) for record in records),
        key=lambda entry: entry.date,
        reverse=True,
    )[:100]
    return render(request, "core/history.html", {"entries": entries})
