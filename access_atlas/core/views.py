import platform
from dataclasses import dataclass
from math import pi
from urllib.parse import urlencode

from django import __version__ as django_version
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, connection
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import TemplateView

from access_atlas.accounts.models import User
from access_atlas.core.global_history import (
    HISTORY_ACTION_CHOICES,
    build_global_history_entries,
    filter_global_history_entries,
    history_object_type_choices,
    history_user_choices,
    sort_global_history_entries,
)
from access_atlas.core.history_filters import GlobalHistoryFilterSet
from access_atlas.core.list_filters import (
    FILTER_STATE_PARAM,
    FILTER_STATE_UPDATE,
    cleaned_values,
    preserved_query_items,
    query_string_without_page,
)
from access_atlas.core.mixins import (
    FilterPreferenceMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)
from access_atlas.core.pagination import normalize_per_page, page_size_options_for
from access_atlas.core.search import (
    SEARCH_LOOKUP_OPTIONS,
    build_global_search_results,
    normalize_lookup_type,
    normalize_sort_value,
)
from access_atlas.jobs.models import Job, JobStatus
from access_atlas.sites.access_record_snapshots import build_access_record_snapshots
from access_atlas.sites.access_warnings import build_site_warnings
from access_atlas.sites.models import Site, SiteSyncStatus
from access_atlas.trips.models import Trip, TripStatus

JOB_STATUS_CHART_COLORS = {
    JobStatus.UNASSIGNED: "#667382",
    JobStatus.ASSIGNED: "#206bc4",
    JobStatus.COMPLETED: "#2fb344",
    JobStatus.CANCELLED: "#d63939",
}
JOB_STATUS_CHART_CIRCUMFERENCE = 2 * pi * 44


def healthz(request):
    """Return a narrow health response for container and load-balancer checks."""
    database_status = "ok"
    status_code = 200
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        database_status = "unavailable"
        status_code = 503

    return JsonResponse(
        {
            "status": "ok" if status_code == 200 else "degraded",
            "application": "Access Atlas",
            "django_version": django_version,
            "python_version": platform.python_version(),
            "database": {"status": database_status},
        },
        status=status_code,
    )


def page_not_found(request, exception):
    """Render a useful 404 page when Django debug error pages are disabled."""
    return render(request, "404.html", status=404)


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
    FilterPreferenceMixin,
    SortableListMixin,
    SearchablePaginatedListMixin,
    TemplateView,
):
    template_name = "core/history.html"
    search_placeholder = "Search history"
    filterset_class = GlobalHistoryFilterSet
    filter_preference_page_key = "history"
    sort_preference_page_key = "history"
    default_sort = "-date"
    sort_field_map = {
        "date": "date",
        "object": "object",
        "type": "type",
        "action": "action",
        "user": "user",
    }

    def get_filterset(self):
        return self.filterset_class(
            data=self.request.GET.copy(),
            queryset=User.objects.none(),
            request=self.request,
        )

    def get_history_filter_values(self, filterset):
        data = filterset.data
        object_types = cleaned_values(data.getlist("object_type")) or None
        excluded_object_types = cleaned_values(data.getlist("object_type__not"))
        actions = cleaned_values(data.getlist("action")) or None
        excluded_actions = cleaned_values(data.getlist("action__not"))
        users = cleaned_values(data.getlist("user")) or None
        excluded_users = cleaned_values(data.getlist("user__not"))

        if excluded_object_types:
            all_object_types = {
                value for value, _label in history_object_type_choices()
            }
            object_types = sorted(all_object_types - set(excluded_object_types))
        if excluded_actions:
            all_actions = {value for value, _label in HISTORY_ACTION_CHOICES}
            actions = sorted(all_actions - set(excluded_actions))
        if excluded_users:
            all_users = {value for value, _label in history_user_choices()}
            users = sorted(all_users - set(excluded_users))

        return {
            "object_types": object_types,
            "actions": actions,
            "users": users,
        }

    def get_context_data(self, **kwargs):
        filterset = self.get_filterset()
        history_filters = self.get_history_filter_values(filterset)
        entries = sort_global_history_entries(
            filter_global_history_entries(
                build_global_history_entries(),
                self.get_search_query(),
                **history_filters,
            ),
            self.get_sort_value(),
        )
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
                "filterset": filterset,
                "filter_controls": filterset.filter_controls(),
                "active_filter_chips": filterset.active_chips(self.request),
                "filter_clear_all_url": filterset.clear_all_url(self.request),
                "filter_state_param": FILTER_STATE_PARAM,
                "filter_state_update": FILTER_STATE_UPDATE,
                "filter_preserved_query_items": preserved_query_items(
                    self.request,
                    exclude=(filterset.filter_parameter_names() - {"q"})
                    | {"page", FILTER_STATE_PARAM},
                ),
                "search_preserved_query_items": preserved_query_items(
                    self.request,
                    exclude={"q", "page", FILTER_STATE_PARAM},
                ),
                "list_view_query_string": query_string_without_page(self.request),
            }
        )
        return context


global_history = login_required(GlobalHistoryView.as_view())
