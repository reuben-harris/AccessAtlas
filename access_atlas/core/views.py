from dataclasses import dataclass
from itertools import chain

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from access_atlas.core.history import history_reason
from access_atlas.core.mixins import SearchablePaginatedListMixin
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
    reason: str
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
        reason=history_reason(record),
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
        model.history.select_related("history_user").all() for model in HISTORY_MODELS
    )
    entries = sorted(
        (build_history_entry(record) for record in records),
        key=lambda entry: entry.date,
        reverse=True,
    )
    search_query = request.GET.get("q", "").strip()
    if search_query:
        search_value = search_query.casefold()
        entries = [
            entry
            for entry in entries
            if search_value in entry.object_display.casefold()
            or search_value in entry.object_type.casefold()
            or search_value in entry.action.casefold()
            or search_value in (entry.reason or "").casefold()
            or search_value in str(entry.user or "System").casefold()
        ]

    try:
        per_page = int(request.GET.get("per_page", ""))
    except TypeError, ValueError:
        per_page = SearchablePaginatedListMixin.default_paginate_by
    if per_page <= 0:
        per_page = SearchablePaginatedListMixin.default_paginate_by
    page_size_options = list(SearchablePaginatedListMixin.page_size_options)
    if per_page not in page_size_options:
        page_size_options.append(per_page)
        page_size_options.sort()

    paginator = Paginator(entries, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    context = {
        "entries": page_obj.object_list,
        "is_paginated": page_obj.has_other_pages(),
        "page_obj": page_obj,
        "paginator": paginator,
        "page_range": paginator.get_elided_page_range(number=page_obj.number),
        "search_query": search_query,
        "search_param": "q",
        "search_placeholder": "Search history",
        "per_page": per_page,
        "page_size_param": "per_page",
        "page_size_options": page_size_options,
        "search_preserved_query_items": [
            (key, value)
            for key in request.GET
            if key not in {"q", "page"}
            for value in request.GET.getlist(key)
        ],
        "per_page_preserved_query_items": [
            (key, value)
            for key in request.GET
            if key not in {"per_page", "page"}
            for value in request.GET.getlist(key)
        ],
    }
    return render(request, "core/history.html", context)
