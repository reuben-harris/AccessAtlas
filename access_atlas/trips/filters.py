from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from access_atlas.accounts.models import User
from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    DATE_OPERATORS,
    REQUIRED_RELATION_OPERATORS,
    SEARCH_OPERATOR,
    AccessAtlasFilterSet,
    FilterFieldSpec,
)
from access_atlas.core.status_display import status_filter_choice_attributes

from .models import Trip, TripStatus


def trip_leader_choices() -> list[tuple[str, str]]:
    return [
        (str(user.pk), str(user))
        for user in User.objects.filter(led_trips__isnull=False)
        .order_by("email")
        .distinct()
    ]


class TripFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    status = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=TripStatus.choices,
    )
    status__not = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=TripStatus.choices,
        exclude=True,
    )
    trip_leader = django_filters.ModelMultipleChoiceFilter(
        field_name="trip_leader",
        queryset=User.objects.order_by("email"),
    )
    trip_leader__not = django_filters.ModelMultipleChoiceFilter(
        field_name="trip_leader",
        queryset=User.objects.order_by("email"),
        exclude=True,
    )
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
    end_date = django_filters.DateFilter(field_name="end_date")
    end_date__not = django_filters.DateFilter(
        field_name="end_date",
        exclude=True,
    )
    end_date__gt = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="gt",
    )
    end_date__gte = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="gte",
    )
    end_date__lt = django_filters.DateFilter(
        field_name="end_date",
        lookup_expr="lt",
    )
    end_date__lte = django_filters.DateFilter(
        field_name="end_date",
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
        FilterFieldSpec(
            "status",
            "Status",
            "multiselect",
            CHOICE_OPERATORS,
            choices=TripStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "trip_leader",
            "Trip Leader",
            "multiselect",
            REQUIRED_RELATION_OPERATORS,
            choices=trip_leader_choices,
        ),
        FilterFieldSpec("start_date", "Start date", "date", DATE_OPERATORS[:6]),
        FilterFieldSpec("end_date", "End date", "date", DATE_OPERATORS[:6]),
    )

    class Meta:
        model = Trip
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(notes__icontains=value)
            | Q(trip_leader__email__icontains=value)
            | Q(trip_leader__display_name__icontains=value)
        )
