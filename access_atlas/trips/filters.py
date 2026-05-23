from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from access_atlas.accounts.models import User
from access_atlas.core.list_filters import (
    CHOICE_OPERATORS,
    DATE_OPERATORS,
    RELATIVE_DATE_CHOICES,
    REQUIRED_RELATION_OPERATORS,
    SEARCH_OPERATOR,
    AccessAtlasFilterSet,
    EmptyValueFilter,
    FilterFieldSpec,
    RelativeDateFilter,
)
from access_atlas.core.status_display import status_filter_choice_attributes
from access_atlas.sites.models import Site

from .models import SiteVisit, SiteVisitStatus, Trip, TripStatus


def trip_leader_choices() -> list[tuple[str, str]]:
    return [
        (str(user.pk), str(user))
        for user in User.objects.filter(led_trips__isnull=False)
        .order_by("email")
        .distinct()
    ]


def site_choices() -> list[tuple[str, str]]:
    return [(str(site.pk), str(site)) for site in Site.objects.order_by("code", "name")]


def trip_choices() -> list[tuple[str, str]]:
    return [(str(trip.pk), trip.name) for trip in Trip.objects.order_by("name")]


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


class SiteVisitFilterSet(AccessAtlasFilterSet):
    q = django_filters.CharFilter(method="filter_q")
    status = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=SiteVisitStatus.choices,
    )
    status__not = django_filters.MultipleChoiceFilter(
        field_name="status",
        choices=SiteVisitStatus.choices,
        exclude=True,
    )
    trip_status = django_filters.MultipleChoiceFilter(
        field_name="trip__status",
        choices=TripStatus.choices,
    )
    trip_status__not = django_filters.MultipleChoiceFilter(
        field_name="trip__status",
        choices=TripStatus.choices,
        exclude=True,
    )
    trip = django_filters.ModelMultipleChoiceFilter(
        field_name="trip",
        queryset=Trip.objects.order_by("name"),
    )
    trip__not = django_filters.ModelMultipleChoiceFilter(
        field_name="trip",
        queryset=Trip.objects.order_by("name"),
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
    planned_day = RelativeDateFilter(field_name="planned_day")
    planned_day__not = RelativeDateFilter(
        field_name="planned_day",
        exclude=True,
    )
    planned_day__gt = RelativeDateFilter(
        field_name="planned_day",
        lookup_expr="gt",
    )
    planned_day__gte = RelativeDateFilter(
        field_name="planned_day",
        lookup_expr="gte",
    )
    planned_day__lt = RelativeDateFilter(
        field_name="planned_day",
        lookup_expr="lt",
    )
    planned_day__lte = RelativeDateFilter(
        field_name="planned_day",
        lookup_expr="lte",
    )
    planned_day__empty = EmptyValueFilter(field_name="planned_day")

    filter_specs = (
        FilterFieldSpec(
            "q",
            "Search",
            "search",
            SEARCH_OPERATOR,
            show_control=False,
        ),
        FilterFieldSpec(
            "planned_day",
            "Visit day",
            "date",
            DATE_OPERATORS,
            choices=RELATIVE_DATE_CHOICES,
            placeholder="YYYY-MM-DD or today",
        ),
        FilterFieldSpec(
            "status",
            "Status",
            "multiselect",
            CHOICE_OPERATORS,
            choices=SiteVisitStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "trip_status",
            "Trip status",
            "multiselect",
            CHOICE_OPERATORS,
            choices=TripStatus.choices,
            collapse_chip_when_all_choices=True,
            all_choices_chip_label="all trip statuses",
            choice_attributes=status_filter_choice_attributes,
        ),
        FilterFieldSpec(
            "trip",
            "Trip",
            "multiselect",
            REQUIRED_RELATION_OPERATORS,
            choices=trip_choices,
        ),
        FilterFieldSpec(
            "site",
            "Site",
            "multiselect",
            REQUIRED_RELATION_OPERATORS,
            choices=site_choices,
        ),
    )

    class Meta:
        model = SiteVisit
        fields: list[str] = []

    def filter_q(self, queryset: QuerySet, _name: str, value: str) -> QuerySet:
        if not value:
            return queryset
        return queryset.filter(
            Q(site__code__icontains=value)
            | Q(site__name__icontains=value)
            | Q(trip__name__icontains=value)
            | Q(notes__icontains=value)
        )
