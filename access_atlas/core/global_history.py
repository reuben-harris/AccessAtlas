from __future__ import annotations

from dataclasses import dataclass
from itertools import chain

from access_atlas.core.history import history_reason
from access_atlas.jobs.models import Job, JobTemplate, Requirement, TemplateRequirement
from access_atlas.sites.models import Site, SitePhoto
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip


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
    SitePhoto,
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


def build_global_history_entries() -> list[HistoryEntry]:
    """Collect model history records into the row shape used by global history."""

    records = chain.from_iterable(
        model.history.select_related("history_user").all() for model in HISTORY_MODELS
    )
    return [build_history_entry(record) for record in records]


def filter_global_history_entries(
    entries: list[HistoryEntry],
    search_query: str,
) -> list[HistoryEntry]:
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


def sort_global_history_entries(
    entries: list[HistoryEntry],
    sort_value: str,
) -> list[HistoryEntry]:
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
