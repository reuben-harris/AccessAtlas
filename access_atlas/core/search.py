import re
from dataclasses import dataclass

from django.db import DatabaseError
from django.db.models import Q

from access_atlas.jobs.models import Job, JobTemplate, WorkProgramme
from access_atlas.sites.models import AccessRecord, Site
from access_atlas.trips.models import SiteVisit, Trip

SEARCH_LOOKUP_OPTIONS = (
    ("iexact", "Exact match"),
    ("istartswith", "Starts with"),
    ("iendswith", "Ends with"),
    ("iregex", "Regex"),
)
SEARCH_LOOKUP_VALUES = {value for value, _label in SEARCH_LOOKUP_OPTIONS}
DEFAULT_SEARCH_LOOKUP = "istartswith"
DEFAULT_SEARCH_SORT = "type"
SEARCH_SORT_FIELDS = {"type", "value", "object"}
DEFAULT_SEARCH_PER_PAGE = 25
SEARCH_PAGE_SIZE_OPTIONS = (25, 50, 100)


@dataclass(frozen=True)
class SearchResultRow:
    object_type: str
    value: str
    object_label: str
    object_url: str


@dataclass(frozen=True)
class SearchResults:
    rows: list[SearchResultRow]
    total: int
    error: str = ""


def normalize_lookup_type(value: str | None) -> str:
    return value if value in SEARCH_LOOKUP_VALUES else DEFAULT_SEARCH_LOOKUP


def normalize_sort_value(value: str | None) -> str:
    if not value:
        return DEFAULT_SEARCH_SORT
    direction = "-" if value.startswith("-") else ""
    sort_key = value.removeprefix("-")
    if sort_key not in SEARCH_SORT_FIELDS:
        return DEFAULT_SEARCH_SORT
    return f"{direction}{sort_key}"


def normalize_per_page(value: str | None) -> int:
    try:
        per_page = int(value or "")
    except TypeError, ValueError:
        return DEFAULT_SEARCH_PER_PAGE
    return per_page if per_page > 0 else DEFAULT_SEARCH_PER_PAGE


def page_size_options_for(per_page: int) -> list[int]:
    options = list(SEARCH_PAGE_SIZE_OPTIONS)
    if per_page not in options:
        options.append(per_page)
        options.sort()
    return options


def first_matching_value(
    query: str,
    candidates: list[str],
    lookup_type: str,
) -> str:
    """Return the first candidate that matches the active lookup mode."""

    if lookup_type == "iregex":
        try:
            pattern = re.compile(query, re.IGNORECASE)
        except re.error:
            return candidates[0] if candidates else ""
        for candidate in candidates:
            if pattern.search(candidate):
                return candidate
        return candidates[0] if candidates else ""

    normalized_query = query.casefold()
    for candidate in candidates:
        normalized_candidate = candidate.casefold()
        if lookup_type == "iexact" and normalized_candidate == normalized_query:
            return candidate
        if lookup_type == "istartswith" and normalized_candidate.startswith(
            normalized_query
        ):
            return candidate
        if lookup_type == "iendswith" and normalized_candidate.endswith(
            normalized_query
        ):
            return candidate
        if normalized_query in normalized_candidate:
            return candidate
    return candidates[0] if candidates else ""


def build_search_predicate(
    field_names: tuple[str, ...],
    query: str,
    lookup_type: str,
) -> Q:
    predicate = Q()
    for field_name in field_names:
        predicate |= Q(**{f"{field_name}__{lookup_type}": query})
    return predicate


def build_site_rows(queryset, query: str, lookup_type: str) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Site",
            value=first_matching_value(
                query,
                [site.code, site.name, site.description],
                lookup_type,
            ),
            object_label=str(site),
            object_url=site.get_absolute_url(),
        )
        for site in queryset
    ]


def build_job_rows(queryset, query: str, lookup_type: str) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Job",
            value=first_matching_value(
                query,
                [
                    job.title,
                    job.description,
                    job.site.code,
                    job.site.name,
                    job.work_programme.name if job.work_programme else "",
                ],
                lookup_type,
            ),
            object_label=job.title,
            object_url=job.get_absolute_url(),
        )
        for job in queryset
    ]


def build_job_template_rows(
    queryset,
    query: str,
    lookup_type: str,
) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Job Template",
            value=first_matching_value(
                query,
                [job_template.title, job_template.description],
                lookup_type,
            ),
            object_label=job_template.title,
            object_url=job_template.get_absolute_url(),
        )
        for job_template in queryset
    ]


def build_work_programme_rows(
    queryset,
    query: str,
    lookup_type: str,
) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Work Programme",
            value=first_matching_value(
                query,
                [work_programme.name, work_programme.description],
                lookup_type,
            ),
            object_label=work_programme.name,
            object_url=work_programme.get_absolute_url(),
        )
        for work_programme in queryset
    ]


def build_trip_rows(queryset, query: str, lookup_type: str) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Trip",
            value=first_matching_value(query, [trip.name], lookup_type),
            object_label=trip.name,
            object_url=trip.get_absolute_url(),
        )
        for trip in queryset
    ]


def build_site_visit_rows(
    queryset,
    query: str,
    lookup_type: str,
) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Site Visit",
            value=first_matching_value(
                query,
                [site_visit.trip.name, site_visit.site.code, site_visit.site.name],
                lookup_type,
            ),
            object_label=f"{site_visit.trip.name} - {site_visit.site.code}",
            object_url=site_visit.get_absolute_url(),
        )
        for site_visit in queryset
    ]


def build_access_record_rows(
    queryset,
    query: str,
    lookup_type: str,
) -> list[SearchResultRow]:
    return [
        SearchResultRow(
            object_type="Access Record",
            value=first_matching_value(
                query,
                [access_record.name, access_record.site.code, access_record.site.name],
                lookup_type,
            ),
            object_label=str(access_record),
            object_url=access_record.get_absolute_url(),
        )
        for access_record in queryset
    ]


def sort_search_rows(
    rows: list[SearchResultRow], sort_value: str
) -> list[SearchResultRow]:
    sort_value = normalize_sort_value(sort_value)
    descending = sort_value.startswith("-")
    sort_key = sort_value.removeprefix("-")

    def stable_suffix(row: SearchResultRow) -> tuple[str, str, str]:
        return (
            row.object_type.casefold(),
            row.object_label.casefold(),
            row.value.casefold(),
        )

    key_functions = {
        "type": lambda row: (
            row.object_type.casefold(),
            row.object_label.casefold(),
            row.value.casefold(),
        ),
        "value": lambda row: (row.value.casefold(), *stable_suffix(row)),
        "object": lambda row: (row.object_label.casefold(), *stable_suffix(row)),
    }
    return sorted(rows, key=key_functions[sort_key], reverse=descending)


def build_global_search_results(
    *,
    query: str,
    lookup_type: str,
    sort_value: str,
) -> SearchResults:
    """Search all object types and return one sorted table-ready row list."""

    if not query:
        return SearchResults(rows=[], total=0)

    lookup_type = normalize_lookup_type(lookup_type)
    if lookup_type == "iregex":
        try:
            re.compile(query, re.IGNORECASE)
        except re.error:
            return SearchResults(rows=[], total=0, error="Invalid regular expression.")

    try:
        site_matches = Site.objects.filter(
            build_search_predicate(("code", "name", "description"), query, lookup_type)
        )
        job_matches = Job.objects.select_related("site", "work_programme").filter(
            build_search_predicate(
                (
                    "title",
                    "description",
                    "site__code",
                    "site__name",
                    "work_programme__name",
                ),
                query,
                lookup_type,
            )
        )
        job_template_matches = JobTemplate.objects.filter(
            build_search_predicate(("title", "description"), query, lookup_type)
        )
        work_programme_matches = WorkProgramme.objects.filter(
            build_search_predicate(("name", "description"), query, lookup_type)
        )
        trip_matches = Trip.objects.filter(
            build_search_predicate(("name",), query, lookup_type)
        )
        site_visit_matches = SiteVisit.objects.select_related("trip", "site").filter(
            build_search_predicate(
                ("trip__name", "site__code", "site__name"),
                query,
                lookup_type,
            )
        )
        access_record_matches = AccessRecord.objects.select_related("site").filter(
            build_search_predicate(
                ("name", "site__code", "site__name"),
                query,
                lookup_type,
            )
        )
        # Force queryset evaluation inside the error boundary because database
        # regex failures happen when PostgreSQL evaluates the query, not when the
        # queryset is constructed.
        rows = [
            *build_site_rows(site_matches, query, lookup_type),
            *build_job_rows(job_matches, query, lookup_type),
            *build_job_template_rows(job_template_matches, query, lookup_type),
            *build_work_programme_rows(work_programme_matches, query, lookup_type),
            *build_trip_rows(trip_matches, query, lookup_type),
            *build_site_visit_rows(site_visit_matches, query, lookup_type),
            *build_access_record_rows(access_record_matches, query, lookup_type),
        ]
    except DatabaseError:
        return SearchResults(
            rows=[],
            total=0,
            error="The search pattern could not be processed.",
        )
    return SearchResults(rows=sort_search_rows(rows, sort_value), total=len(rows))
