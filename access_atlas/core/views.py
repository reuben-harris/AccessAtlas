from dataclasses import dataclass
from itertools import chain
from math import pi
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from access_atlas.core.history import history_reason
from access_atlas.core.mixins import SearchablePaginatedListMixin, SortableListMixin
from access_atlas.core.search import (
    SEARCH_LOOKUP_OPTIONS,
    build_global_search_results,
    normalize_lookup_type,
    normalize_per_page,
    normalize_sort_value,
    page_size_options_for,
)
from access_atlas.jobs.models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
)
from access_atlas.sites.access_record_snapshots import build_access_record_snapshots
from access_atlas.sites.access_warnings import build_site_warnings
from access_atlas.sites.models import Site, SiteSyncStatus
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

JOB_STATUS_CHART_COLORS = {
    JobStatus.UNASSIGNED: "#667382",
    JobStatus.PLANNED: "#206bc4",
    JobStatus.COMPLETED: "#2fb344",
    JobStatus.CANCELLED: "#d63939",
}
JOB_STATUS_CHART_CIRCUMFERENCE = 2 * pi * 44


@dataclass(frozen=True)
class DashboardJobStatusSlice:
    value: str
    label: str
    count: int
    color: str
    url: str
    dasharray: str
    dashoffset: str


def _dashboard_job_filter_url(status: str) -> str:
    query = urlencode({"status": status})
    return f"{reverse('job_list')}?{query}"


def build_dashboard_job_status_chart() -> dict[str, object]:
    counts = {
        row["status"]: row["count"]
        for row in Job.objects.values("status").order_by().annotate(count=Count("id"))
    }
    total = sum(counts.values())
    progress = 0.0
    slices: list[DashboardJobStatusSlice] = []
    legend_items: list[dict[str, object]] = []

    for status in JobStatus:
        count = counts.get(status, 0)
        legend_items.append(
            {
                "value": status,
                "label": status.label,
                "count": count,
                "color": JOB_STATUS_CHART_COLORS[status],
                "url": _dashboard_job_filter_url(status),
            }
        )
        if total == 0 or count == 0:
            continue
        segment_length = JOB_STATUS_CHART_CIRCUMFERENCE * (count / total)
        slices.append(
            DashboardJobStatusSlice(
                value=status,
                label=status.label,
                count=count,
                color=JOB_STATUS_CHART_COLORS[status],
                url=_dashboard_job_filter_url(status),
                dasharray=(
                    f"{segment_length:.3f} "
                    f"{JOB_STATUS_CHART_CIRCUMFERENCE - segment_length:.3f}"
                ),
                dashoffset=f"{-progress:.3f}",
            )
        )
        progress += segment_length

    return {
        "total": total,
        "circumference": f"{JOB_STATUS_CHART_CIRCUMFERENCE:.3f}",
        "slices": slices,
        "legend_items": legend_items,
    }


def build_dashboard_attention_groups() -> dict[str, object]:
    stale_sites: list[Site] = []
    warning_sites: list[Site] = []
    sites = list(
        Site.objects.prefetch_related("access_records__versions").order_by("code")
    )
    for site in sites:
        if site.sync_status == SiteSyncStatus.STALE:
            stale_sites.append(site)
        access_records = list(site.access_records.all())
        snapshots_by_record_id = build_access_record_snapshots(access_records)
        if build_site_warnings(site, snapshots_by_record_id=snapshots_by_record_id):
            warning_sites.append(site)

    return {
        "warning_sites": warning_sites[:6],
        "warning_sites_count": len(warning_sites),
        "warning_sites_has_more": len(warning_sites) > 6,
        "stale_sites": stale_sites[:6],
        "stale_sites_count": len(stale_sites),
        "stale_sites_has_more": len(stale_sites) > 6,
    }


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
    today = timezone.localdate()
    upcoming_cutoff = today + timezone.timedelta(days=30)
    job_status_chart = build_dashboard_job_status_chart()
    attention_groups = build_dashboard_attention_groups()
    context = {
        "job_status_chart": job_status_chart,
        "upcoming_trips": Trip.objects.select_related("trip_leader")
        .exclude(status__in=[TripStatus.COMPLETED, TripStatus.CANCELLED])
        .filter(start_date__gte=today, start_date__lte=upcoming_cutoff)
        .order_by("start_date", "name")[:8],
        "upcoming_trips_window_end": upcoming_cutoff,
        **attention_groups,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def search(request):
    query = request.GET.get("q", "").strip()
    lookup_type = normalize_lookup_type(request.GET.get("lookup"))
    sort_value = normalize_sort_value(request.GET.get("sort"))
    per_page = normalize_per_page(request.GET.get("per_page"))
    results = build_global_search_results(
        query=query,
        lookup_type=lookup_type,
        sort_value=sort_value,
    )
    paginator = Paginator(results.rows, per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    result_rows = list(page_obj.object_list)
    current_sort_field = sort_value.removeprefix("-")
    return render(
        request,
        "core/search.html",
        {
            "query": query,
            "lookup_type": lookup_type,
            "highlight_query": f"{lookup_type}::{query}" if query else "",
            "lookup_options": SEARCH_LOOKUP_OPTIONS,
            "search_error": results.error,
            "result_rows": result_rows,
            "total_results": results.total,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "page_range": paginator.get_elided_page_range(number=page_obj.number),
            "current_sort": sort_value,
            "current_sort_field": current_sort_field,
            "current_sort_descending": sort_value.startswith("-"),
            "sort_param": "sort",
            "per_page": per_page,
            "page_size_param": "per_page",
            "page_size_options": page_size_options_for(per_page),
        },
    )


class GlobalHistoryView(
    SortableListMixin,
    SearchablePaginatedListMixin,
    TemplateView,
):
    template_name = "core/history.html"
    search_placeholder = "Search history"
    sort_preference_page_key = "history"
    default_sort = "-date"
    sort_field_map = {
        "date": "date",
        "object": "object",
        "type": "type",
        "action": "action",
        "user": "user",
    }

    def get_entries(self) -> list[HistoryEntry]:
        records = chain.from_iterable(
            model.history.select_related("history_user").all()
            for model in HISTORY_MODELS
        )
        return [build_history_entry(record) for record in records]

    def filter_entries(self, entries: list[HistoryEntry]) -> list[HistoryEntry]:
        search_query = self.get_search_query()
        if not search_query:
            return entries
        search_value = search_query.casefold()
        return [
            entry
            for entry in entries
            if search_value in entry.object_display.casefold()
            or search_value in entry.object_type.casefold()
            or search_value in entry.action.casefold()
            or search_value in (entry.reason or "").casefold()
            or search_value in str(entry.user or "System").casefold()
        ]

    def sort_entries(self, entries: list[HistoryEntry]) -> list[HistoryEntry]:
        sort_value = self.get_sort_value()
        descending = sort_value.startswith("-")
        sort_key = sort_value.removeprefix("-")
        sort_functions = {
            "date": lambda entry: entry.date,
            "object": lambda entry: entry.object_display.casefold(),
            "type": lambda entry: entry.object_type.casefold(),
            "action": lambda entry: entry.action.casefold(),
            "user": lambda entry: str(entry.user or "System").casefold(),
        }
        key_function = sort_functions.get(sort_key, sort_functions["date"])
        return sorted(entries, key=key_function, reverse=descending)

    def get_context_data(self, **kwargs):
        entries = self.sort_entries(self.filter_entries(self.get_entries()))
        paginator = Paginator(entries, self.get_per_page())
        page_obj = paginator.get_page(self.request.GET.get("page"))
        context = super().get_context_data(
            page_obj=page_obj,
            paginator=paginator,
            is_paginated=page_obj.has_other_pages(),
            **kwargs,
        )
        context.update(
            {
                "entries": page_obj.object_list,
            }
        )
        return context


global_history = login_required(GlobalHistoryView.as_view())
