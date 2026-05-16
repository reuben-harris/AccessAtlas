from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    DATE_OPERATORS,
    NUMBER_OPERATORS,
    RELATION_OPERATORS,
    REQUIRED_RELATION_OPERATORS,
    SEARCH_OPERATOR,
    TAG_OPERATORS,
    TEXT_OPERATORS,
    AccessAtlasFilterSet,
    EmptyValueFilter,
    FilterFieldSpec,
    ensure_querydict,
)
from access_atlas.core.status_display import status_filter_choice_attributes
from access_atlas.sites.filters import site_ids_matching_any_tag, site_tag_choices
from access_atlas.sites.models import Site

from .models import Job, JobStatus, JobTemplate, Priority, WorkProgramme

ACTIVE_STATE_CHOICES = (
    ("true", "Yes"),
    ("false", "No"),
)
ACTIVE_STATE_STATUS_VALUES = {
    "true": "active",
    "false": "retired",
}


def active_state_filter_choice_attributes(value: str) -> dict[str, str]:
    status_value = ACTIVE_STATE_STATUS_VALUES.get(value)
    if status_value is None:
        return {}
    return status_filter_choice_attributes(status_value)


def site_choices() -> list[tuple[str, str]]:
    return [(str(site.pk), str(site)) for site in Site.objects.order_by("code", "name")]


def work_programme_choices() -> list[tuple[str, str]]:
    return [
        (str(programme.pk), programme.name)
        for programme in WorkProgramme.objects.order_by("start_date", "name")
    ]


def job_status_predicate(values: list[str]) -> Q:
    values = [value for value in values if value in JobStatus.values]
    predicate = Q()
    regular_statuses = [value for value in values if value != JobStatus.UNASSIGNED]
    if regular_statuses:
        predicate |= Q(status__in=regular_statuses)
    if JobStatus.UNASSIGNED in values:
        predicate |= Q(
            status=JobStatus.UNASSIGNED,
            site_visit_assignment__isnull=True,
        )
    return predicate


def boolean_values(values: list[str]) -> set[bool]:
    return {value == "true" for value in values if value in {"true", "false"}}


class JobTemplateFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    title = django_filters.CharFilter(field_name="title", lookup_expr="exact")
    title__not = django_filters.CharFilter(
        field_name="title",
        lookup_expr="exact",
        exclude=True,
    )
    title__icontains = django_filters.CharFilter(
        field_name="title",
        lookup_expr="icontains",
    )
    title__istartswith = django_filters.CharFilter(
        field_name="title",
        lookup_expr="istartswith",
    )
    title__iendswith = django_filters.CharFilter(
        field_name="title",
        lookup_expr="iendswith",
    )
    title__iexact = django_filters.CharFilter(
        field_name="title",
        lookup_expr="iexact",
    )
    title__regex = django_filters.CharFilter(field_name="title", lookup_expr="regex")
    title__iregex = django_filters.CharFilter(field_name="title", lookup_expr="iregex")
    priority = django_filters.MultipleChoiceFilter(
        field_name="priority",
        choices=Priority.choices,
    )
    priority__not = django_filters.MultipleChoiceFilter(
        field_name="priority",
        choices=Priority.choices,
        exclude=True,
    )
    is_active = django_filters.MultipleChoiceFilter(
        method="filter_is_active",
        choices=ACTIVE_STATE_CHOICES,
    )
    is_active__not = django_filters.MultipleChoiceFilter(
        method="filter_is_active_not",
        choices=ACTIVE_STATE_CHOICES,
    )
    estimated_duration_minutes = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="exact",
    )
    estimated_duration_minutes__not = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="exact",
        exclude=True,
    )
    estimated_duration_minutes__gt = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="gt",
    )
    estimated_duration_minutes__gte = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="gte",
    )
    estimated_duration_minutes__lt = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="lt",
    )
    estimated_duration_minutes__lte = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="lte",
    )
    estimated_duration_minutes__empty = EmptyValueFilter(
        field_name="estimated_duration_minutes",
    )

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec(
            "is_active",
            "Active",
            "multiselect",
            CHOICE_OPERATORS,
            choices=ACTIVE_STATE_CHOICES,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all active states",
            choice_attributes=active_state_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "priority",
            "Default priority",
            "multiselect",
            CHOICE_OPERATORS,
            choices=Priority.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all priorities",
        ),
        FilterFieldSpec(
            "estimated_duration_minutes",
            "Estimate",
            "number",
            NUMBER_OPERATORS,
            placeholder="Minutes",
        ),
        FilterFieldSpec("title", "Title", "text", TEXT_OPERATORS),
    )

    class Meta:
        model = JobTemplate
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        data = kwargs.get("data")
        data = ensure_querydict(data)
        kwargs["data"] = data
        defaulted_filter_params: set[str] = set()
        if (
            data is not None
            and "is_active" not in data
            and "is_active__not" not in data
        ):
            data = data.copy()
            data.setlist("is_active", ["true"])
            kwargs["data"] = data
            defaulted_filter_params.add("is_active")

        super().__init__(*args, **kwargs)
        self.defaulted_filter_params = defaulted_filter_params

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )

    def filter_is_active(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        parsed_values = boolean_values(list(values))
        if not parsed_values:
            return queryset
        return queryset.filter(is_active__in=parsed_values)

    def filter_is_active_not(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        parsed_values = boolean_values(list(values))
        if not parsed_values:
            return queryset
        return queryset.exclude(is_active__in=parsed_values)


class WorkProgrammeFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    name = django_filters.CharFilter(field_name="name", lookup_expr="exact")
    name__not = django_filters.CharFilter(
        field_name="name",
        lookup_expr="exact",
        exclude=True,
    )
    name__icontains = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )
    name__istartswith = django_filters.CharFilter(
        field_name="name",
        lookup_expr="istartswith",
    )
    name__iendswith = django_filters.CharFilter(
        field_name="name",
        lookup_expr="iendswith",
    )
    name__iexact = django_filters.CharFilter(field_name="name", lookup_expr="iexact")
    name__regex = django_filters.CharFilter(field_name="name", lookup_expr="regex")
    name__iregex = django_filters.CharFilter(field_name="name", lookup_expr="iregex")
    start_date = django_filters.DateFilter(field_name="start_date")
    start_date__not = django_filters.DateFilter(
        field_name="start_date",
        exclude=True,
    )
    start_date__gt = django_filters.DateFilter(
        field_name="start_date",
        lookup_expr="gt",
    )
    start_date__gte = django_filters.DateFilter(
        field_name="start_date",
        lookup_expr="gte",
    )
    start_date__lt = django_filters.DateFilter(
        field_name="start_date",
        lookup_expr="lt",
    )
    start_date__lte = django_filters.DateFilter(
        field_name="start_date",
        lookup_expr="lte",
    )
    start_date__empty = EmptyValueFilter(field_name="start_date")
    end_date = django_filters.DateFilter(field_name="end_date")
    end_date__not = django_filters.DateFilter(
        field_name="end_date",
        exclude=True,
    )
    end_date__gt = django_filters.DateFilter(field_name="end_date", lookup_expr="gt")
    end_date__gte = django_filters.DateFilter(field_name="end_date", lookup_expr="gte")
    end_date__lt = django_filters.DateFilter(field_name="end_date", lookup_expr="lt")
    end_date__lte = django_filters.DateFilter(field_name="end_date", lookup_expr="lte")
    end_date__empty = EmptyValueFilter(field_name="end_date")
    job_count = django_filters.NumberFilter(field_name="job_count", lookup_expr="exact")
    job_count__not = django_filters.NumberFilter(
        field_name="job_count",
        lookup_expr="exact",
        exclude=True,
    )
    job_count__gt = django_filters.NumberFilter(
        field_name="job_count",
        lookup_expr="gt",
    )
    job_count__gte = django_filters.NumberFilter(
        field_name="job_count",
        lookup_expr="gte",
    )
    job_count__lt = django_filters.NumberFilter(
        field_name="job_count",
        lookup_expr="lt",
    )
    job_count__lte = django_filters.NumberFilter(
        field_name="job_count",
        lookup_expr="lte",
    )

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec("name", "Name", "text", TEXT_OPERATORS),
        FilterFieldSpec("start_date", "Start date", "date", DATE_OPERATORS),
        FilterFieldSpec("end_date", "Due date", "date", DATE_OPERATORS),
        FilterFieldSpec("job_count", "Jobs", "number", NUMBER_OPERATORS[:6]),
    )

    class Meta:
        model = WorkProgramme
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class JobFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    status = django_filters.MultipleChoiceFilter(
        method="filter_status",
        choices=JobStatus.choices,
    )
    status__not = django_filters.MultipleChoiceFilter(
        method="filter_status_not",
        choices=JobStatus.choices,
    )
    priority = django_filters.MultipleChoiceFilter(
        field_name="priority",
        choices=Priority.choices,
    )
    priority__not = django_filters.MultipleChoiceFilter(
        field_name="priority",
        choices=Priority.choices,
        exclude=True,
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name="site",
        queryset=Site.objects.order_by("code", "name"),
    )
    site__not = django_filters.ModelMultipleChoiceFilter(
        field_name="site",
        queryset=Site.objects.order_by("code", "name"),
        exclude=True,
    )
    site_tags = django_filters.MultipleChoiceFilter(
        method="filter_site_tags",
        choices=site_tag_choices,
    )
    site_tags__not = django_filters.MultipleChoiceFilter(
        method="filter_site_tags_not",
        choices=site_tag_choices,
    )
    work_programme = django_filters.ModelMultipleChoiceFilter(
        field_name="work_programme",
        queryset=WorkProgramme.objects.order_by("start_date", "name"),
    )
    work_programme__not = django_filters.ModelMultipleChoiceFilter(
        field_name="work_programme",
        queryset=WorkProgramme.objects.order_by("start_date", "name"),
        exclude=True,
    )
    work_programme__empty = EmptyValueFilter(field_name="work_programme")
    due_date = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="exact",
    )
    due_date__not = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="exact",
        exclude=True,
    )
    due_date__gt = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="gt",
    )
    due_date__gte = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="gte",
    )
    due_date__lt = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="lt",
    )
    due_date__lte = django_filters.DateFilter(
        field_name="work_programme__end_date",
        lookup_expr="lte",
    )
    due_date__empty = EmptyValueFilter(field_name="work_programme__end_date")
    estimated_duration_minutes = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="exact",
    )
    estimated_duration_minutes__not = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="exact",
        exclude=True,
    )
    estimated_duration_minutes__gt = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="gt",
    )
    estimated_duration_minutes__gte = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="gte",
    )
    estimated_duration_minutes__lt = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="lt",
    )
    estimated_duration_minutes__lte = django_filters.NumberFilter(
        field_name="estimated_duration_minutes",
        lookup_expr="lte",
    )
    estimated_duration_minutes__empty = EmptyValueFilter(
        field_name="estimated_duration_minutes",
    )

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec(
            "status",
            "Status",
            "multiselect",
            CHOICE_OPERATORS,
            choices=JobStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "priority",
            "Priority",
            "multiselect",
            CHOICE_OPERATORS,
            choices=Priority.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all priorities",
        ),
        FilterFieldSpec(
            "site",
            "Site",
            "multiselect",
            REQUIRED_RELATION_OPERATORS,
            choices=site_choices,
        ),
        FilterFieldSpec(
            "site_tags",
            "Site tags",
            "multiselect",
            TAG_OPERATORS,
            choices=site_tag_choices,
        ),
        FilterFieldSpec(
            "work_programme",
            "Work Programme",
            "multiselect",
            RELATION_OPERATORS,
            choices=work_programme_choices,
        ),
        FilterFieldSpec("due_date", "Due date", "date", DATE_OPERATORS),
        FilterFieldSpec(
            "estimated_duration_minutes",
            "Estimate",
            "number",
            NUMBER_OPERATORS,
            placeholder="Minutes",
        ),
    )

    class Meta:
        model = Job
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(description__icontains=value)
            | Q(site__code__icontains=value)
            | Q(site__name__icontains=value)
        )

    def filter_status(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.filter(job_status_predicate(list(values)))

    def filter_status_not(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.exclude(job_status_predicate(list(values)))

    def filter_site_tags(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.filter(site_id__in=site_ids_matching_any_tag(list(values)))

    def filter_site_tags_not(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.filter(
            site_id__in=site_ids_matching_any_tag(list(values), negate=True),
        )
