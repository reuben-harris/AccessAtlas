from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    REQUIRED_RELATION_OPERATORS,
    SEARCH_OPERATOR,
    TAG_OPERATORS,
    TEXT_OPERATORS,
    AccessAtlasFilterSet,
    FilterFieldSpec,
)
from access_atlas.core.status_display import status_filter_choice_attributes
from access_atlas.sites.filters import (
    site_choices,
    site_ids_matching_any_tag,
    site_source_choices,
    site_tag_choices,
)
from access_atlas.sites.models import Site

from .models import AccessRecord, AccessRecordStatus, ArrivalMethod


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
