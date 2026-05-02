from dataclasses import dataclass
from itertools import chain

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.generic import TemplateView

from access_atlas.core.history import history_reason
from access_atlas.core.mixins import SearchablePaginatedListMixin, SortableListMixin
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
