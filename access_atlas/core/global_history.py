from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from urllib.parse import urlencode

from django.urls import NoReverseMatch, reverse

from access_atlas.accounts.models import User
from access_atlas.core.history import history_reason
from access_atlas.jobs.models import Job, JobTemplate, Requirement, TemplateRequirement
from access_atlas.sites.models import AccessRecord, Site, SitePhoto
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip


@dataclass(frozen=True)
class HistoryEntry:
    date: object
    action: str
    reason: str
    object_type: str
    object_type_slug: str
    object_id: str
    object_display: str
    object_url: str
    history_detail_url: str
    user: object


HISTORY_MODELS = [
    Site,
    AccessRecord,
    SitePhoto,
    JobTemplate,
    TemplateRequirement,
    Job,
    Requirement,
    Trip,
    SiteVisit,
    SiteVisitJob,
]
HISTORY_ACTION_CHOICES = (
    ("Created", "Created"),
    ("Changed", "Changed"),
    ("Deleted", "Deleted"),
)
SYSTEM_HISTORY_USER_VALUE = "__system__"
HISTORY_MODEL_SLUGS = {
    Site: "site",
    AccessRecord: "access-record",
    SitePhoto: "site-photo",
    JobTemplate: "job-template",
    TemplateRequirement: "template-requirement",
    Job: "job",
    Requirement: "requirement",
    Trip: "trip",
    SiteVisit: "site-visit",
    SiteVisitJob: "site-visit-job",
}
HISTORY_MODELS_BY_SLUG = {slug: model for model, slug in HISTORY_MODEL_SLUGS.items()}


def history_object_type_choices() -> list[tuple[str, str]]:
    return [
        (HISTORY_MODEL_SLUGS[model], model._meta.verbose_name.title())
        for model in HISTORY_MODELS
        if model in HISTORY_MODEL_SLUGS
    ]


def history_user_choices() -> list[tuple[str, str]]:
    choices = [(SYSTEM_HISTORY_USER_VALUE, "System")]
    choices.extend(
        (str(user.pk), str(user))
        for user in User.objects.order_by("email", "display_name")
    )
    return choices


def build_history_entry(record) -> HistoryEntry:
    instance = record.instance
    object_type_slug = HISTORY_MODEL_SLUGS.get(type(instance), "")
    object_url = ""
    if record.history_type != "-" and hasattr(instance, "get_absolute_url"):
        object_url = instance.get_absolute_url()
    return HistoryEntry(
        date=record.history_date,
        action=record.get_history_type_display(),
        reason=history_reason(record),
        object_type=instance._meta.verbose_name.title(),
        object_type_slug=object_type_slug,
        object_id=str(instance.pk),
        object_display=str(instance),
        object_url=object_url,
        history_detail_url=history_detail_url(record),
        user=record.history_user,
    )


def history_detail_url(record) -> str:
    instance = record.instance
    object_type = HISTORY_MODEL_SLUGS.get(type(instance))
    if not object_type:
        return ""
    try:
        return reverse(
            "global_history_detail",
            kwargs={
                "object_type": object_type,
                "history_id": record.history_id,
            },
        )
    except NoReverseMatch:
        return ""


def history_object_filter_query(instance) -> str:
    object_type = HISTORY_MODEL_SLUGS.get(type(instance), "")
    if not object_type or instance.pk is None:
        return ""
    return urlencode({"object_type": object_type, "object_id": instance.pk})


def append_query_string(url: str, query_string: str) -> str:
    if not url or not query_string:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{query_string}"


def history_model_for_slug(object_type: str):
    return HISTORY_MODELS_BY_SLUG.get(object_type)


def adjacent_history_records(model, history_record):
    object_pk_field = model._meta.pk.name
    object_pk = getattr(history_record, object_pk_field)
    records = list(
        model.history.filter(**{object_pk_field: object_pk}).order_by(
            "history_date",
            "history_id",
        )
    )
    record_ids = [record.history_id for record in records]
    if history_record.history_id not in record_ids:
        return None, None
    index = record_ids.index(history_record.history_id)
    previous_record = records[index - 1] if index > 0 else None
    next_record = records[index + 1] if index < len(records) - 1 else None
    return previous_record, next_record


def build_global_history_entries() -> list[HistoryEntry]:
    """Collect model history records into the row shape used by global history."""

    records = chain.from_iterable(
        model.history.select_related("history_user").all() for model in HISTORY_MODELS
    )
    return [build_history_entry(record) for record in records]


def filter_global_history_entries(
    entries: list[HistoryEntry],
    search_query: str,
    *,
    object_types: list[str] | None = None,
    object_ids: list[str] | None = None,
    excluded_object_ids: list[str] | None = None,
    actions: list[str] | None = None,
    users: list[str] | None = None,
) -> list[HistoryEntry]:
    if object_types is not None:
        allowed_object_types = set(object_types)
        entries = [
            entry for entry in entries if entry.object_type_slug in allowed_object_types
        ]
    if object_ids is not None:
        allowed_object_ids = set(object_ids)
        entries = [entry for entry in entries if entry.object_id in allowed_object_ids]
    if excluded_object_ids is not None:
        blocked_object_ids = set(excluded_object_ids)
        entries = [
            entry for entry in entries if entry.object_id not in blocked_object_ids
        ]
    if actions is not None:
        allowed_actions = set(actions)
        entries = [entry for entry in entries if entry.action in allowed_actions]
    if users is not None:
        allowed_users = set(users)
        entries = [
            entry
            for entry in entries
            if (
                str(entry.user.pk)
                if entry.user is not None
                else SYSTEM_HISTORY_USER_VALUE
            )
            in allowed_users
        ]
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
