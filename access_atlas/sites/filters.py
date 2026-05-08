from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    DATE_OPERATORS,
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

from .models import (
    AccessRecord,
    AccessRecordStatus,
    ArrivalMethod,
    Site,
    SiteSyncStatus,
)


def site_tag_choices() -> list[tuple[str, str]]:
    labels = {
        str(tag.get("label", "")).strip()
        for tags in Site.objects.values_list("tags", flat=True)
        for tag in tags
        if isinstance(tag, dict) and str(tag.get("label", "")).strip()
    }
    return [(label, label) for label in sorted(labels, key=str.casefold)]


def site_source_choices() -> list[tuple[str, str]]:
    sources = (
        Site.objects.order_by("source_name")
        .values_list("source_name", flat=True)
        .distinct()
    )
    return [(source, source) for source in sources if source]


def site_choices() -> list[tuple[str, str]]:
    return [(str(site.pk), str(site)) for site in Site.objects.order_by("code", "name")]


def site_ids_matching_any_tag(labels: list[str], *, negate: bool = False) -> list[int]:
    wanted = set(labels)
    matching_ids = []
    for site_id, tags in Site.objects.values_list("pk", "tags"):
        site_labels = {
            str(tag.get("label", "")).strip() for tag in tags if isinstance(tag, dict)
        }
        has_match = bool(wanted & site_labels)
        if has_match != negate:
            matching_ids.append(site_id)
    return matching_ids


class SiteFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    code = django_filters.CharFilter(field_name="code", lookup_expr="exact")
    code__not = django_filters.CharFilter(
        field_name="code",
        lookup_expr="exact",
        exclude=True,
    )
    code__icontains = django_filters.CharFilter(
        field_name="code",
        lookup_expr="icontains",
    )
    code__istartswith = django_filters.CharFilter(
        field_name="code",
        lookup_expr="istartswith",
    )
    code__iendswith = django_filters.CharFilter(
        field_name="code",
        lookup_expr="iendswith",
    )
    code__iexact = django_filters.CharFilter(
        field_name="code",
        lookup_expr="iexact",
    )
    code__regex = django_filters.CharFilter(field_name="code", lookup_expr="regex")
    code__iregex = django_filters.CharFilter(field_name="code", lookup_expr="iregex")
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
    name__iexact = django_filters.CharFilter(
        field_name="name",
        lookup_expr="iexact",
    )
    name__regex = django_filters.CharFilter(field_name="name", lookup_expr="regex")
    name__iregex = django_filters.CharFilter(field_name="name", lookup_expr="iregex")
    source_name = django_filters.MultipleChoiceFilter(
        field_name="source_name",
        choices=site_source_choices,
    )
    source_name__not = django_filters.MultipleChoiceFilter(
        field_name="source_name",
        choices=site_source_choices,
        exclude=True,
    )
    sync_status = django_filters.MultipleChoiceFilter(
        field_name="sync_status",
        choices=SiteSyncStatus.choices,
    )
    sync_status__not = django_filters.MultipleChoiceFilter(
        field_name="sync_status",
        choices=SiteSyncStatus.choices,
        exclude=True,
    )
    tags = django_filters.MultipleChoiceFilter(
        method="filter_tags",
        choices=site_tag_choices,
    )
    tags__not = django_filters.MultipleChoiceFilter(
        method="filter_tags_not",
        choices=site_tag_choices,
    )
    last_seen_at = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date",
    )
    last_seen_at__not = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date",
        exclude=True,
    )
    last_seen_at__gt = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date__gt",
    )
    last_seen_at__gte = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date__gte",
    )
    last_seen_at__lt = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date__lt",
    )
    last_seen_at__lte = django_filters.DateFilter(
        field_name="last_seen_at",
        lookup_expr="date__lte",
    )
    last_seen_at__empty = EmptyValueFilter(field_name="last_seen_at")

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec(
            "sync_status",
            "Status",
            "multiselect",
            CHOICE_OPERATORS,
            choices=SiteSyncStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "source_name",
            "Source",
            "multiselect",
            CHOICE_OPERATORS,
            site_source_choices,
        ),
        FilterFieldSpec("tags", "Tags", "multiselect", TAG_OPERATORS, site_tag_choices),
        FilterFieldSpec(
            "code",
            "Code",
            "text",
            TEXT_OPERATORS,
            placeholder="Site code",
        ),
        FilterFieldSpec(
            "name",
            "Name",
            "text",
            TEXT_OPERATORS,
            placeholder="Site name",
        ),
        FilterFieldSpec("last_seen_at", "Last seen", "date", DATE_OPERATORS),
    )
    clear_all_overrides = {
        "sync_status": [SiteSyncStatus.ACTIVE, SiteSyncStatus.STALE],
    }

    class Meta:
        model = Site
        fields: list[str] = []

    def __init__(self, *args, **kwargs):
        data = kwargs.get("data")
        data = ensure_querydict(data)
        kwargs["data"] = data
        defaulted_filter_params: set[str] = set()
        if (
            data is not None
            and "sync_status" not in data
            and "sync_status__not" not in data
        ):
            data = data.copy()
            data.setlist("sync_status", [SiteSyncStatus.ACTIVE])
            kwargs["data"] = data
            defaulted_filter_params.add("sync_status")

        super().__init__(*args, **kwargs)
        self.defaulted_filter_params = defaulted_filter_params

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(code__icontains=value)
            | Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(external_id__icontains=value)
            | Q(source_name__icontains=value)
        )

    def filter_tags(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.filter(pk__in=site_ids_matching_any_tag(list(values)))

    def filter_tags_not(
        self,
        queryset: QuerySet,
        _name: str,
        values: list[str],
    ) -> QuerySet:
        if not values:
            return queryset
        return queryset.filter(
            pk__in=site_ids_matching_any_tag(list(values), negate=True)
        )


class AccessRecordFilterSet(AccessAtlasFilterSet):
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
    source_name = django_filters.MultipleChoiceFilter(
        field_name="site__source_name",
        choices=site_source_choices,
    )
    source_name__not = django_filters.MultipleChoiceFilter(
        field_name="site__source_name",
        choices=site_source_choices,
        exclude=True,
    )
    status = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=AccessRecordStatus.choices,
    )
    status__not = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=AccessRecordStatus.choices,
        exclude=True,
    )
    arrival_method = django_filters.MultipleChoiceFilter(
        field_name="arrival_method",
        choices=ArrivalMethod.choices,
    )
    arrival_method__not = django_filters.MultipleChoiceFilter(
        field_name="arrival_method",
        choices=ArrivalMethod.choices,
        exclude=True,
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
            choices=AccessRecordStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "arrival_method",
            "Arrival method",
            "multiselect",
            CHOICE_OPERATORS,
            choices=ArrivalMethod.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all arrival methods",
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
            "source_name",
            "Source",
            "multiselect",
            CHOICE_OPERATORS,
            choices=site_source_choices,
        ),
        FilterFieldSpec("name", "Name", "text", TEXT_OPERATORS),
    )

    class Meta:
        model = AccessRecord
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(site__code__icontains=value)
            | Q(site__name__icontains=value)
            | Q(site__source_name__icontains=value)
            | Q(status__icontains=value)
            | Q(arrival_method__icontains=value)
        )

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
            site_id__in=site_ids_matching_any_tag(list(values), negate=True)
        )
