from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, F
from django.views.generic import ListView

from access_atlas.core.maps import map_basemap_config, map_basemap_preference
from access_atlas.core.mixins import (
    FilteredListMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)

from .filters import SiteVisitFilterSet, TripFilterSet
from .models import SiteVisit, Trip
from .view_helpers import (
    build_site_visit_map_data,
    site_visit_list_views,
    trip_list_views,
)


class TripListView(
    LoginRequiredMixin,
    SortableListMixin,
    FilteredListMixin,
    SearchablePaginatedListMixin,
    ListView,
):
    model = Trip
    template_name = "trips/trip_list.html"
    search_placeholder = "Search trips"
    filterset_class = TripFilterSet
    filter_preference_page_key = "trips"
    sort_preference_page_key = "trips"
    default_sort = "start-date"
    sort_field_map = {
        "name": "name",
        "start-date": "start_date",
        "end-date": "end_date",
        "leader": "trip_leader__email",
        "status": "status",
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("trip_leader")
        return self.apply_sort(self.apply_filters(queryset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trip_list_views"] = trip_list_views(
            "table",
            context.get("list_view_query_string", ""),
        )
        return context


class TripGanttView(FilteredListMixin, LoginRequiredMixin, ListView):
    model = Trip
    template_name = "trips/trip_gantt.html"
    filterset_class = TripFilterSet
    search_placeholder = "Search trips"
    filter_preference_page_key = "trips"

    def get_queryset(self):
        queryset = Trip.objects.select_related("trip_leader").prefetch_related(
            "site_visits__site"
        )
        return self.apply_filters(queryset).order_by("start_date", "name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        trip_rows = []
        unscheduled_visits = []

        for trip in context["object_list"]:
            scheduled_visits = []
            for site_visit in trip.site_visits.select_related("site").order_by(
                F("planned_day").asc(nulls_last=True),
                F("planned_start").asc(nulls_last=True),
                "site__code",
                "id",
            ):
                if site_visit.planned_start and site_visit.planned_end:
                    scheduled_visits.append(
                        {
                            "id": f"site-visit-{site_visit.pk}",
                            "tripId": trip.pk,
                            "tripName": trip.name,
                            "siteVisitId": site_visit.pk,
                            "siteCode": site_visit.site.code,
                            "siteName": site_visit.site.name,
                            "status": site_visit.status,
                            "statusLabel": site_visit.get_status_display(),
                            "start": site_visit.planned_start.isoformat(),
                            "end": site_visit.planned_end.isoformat(),
                            "url": site_visit.get_absolute_url(),
                        }
                    )
                else:
                    unscheduled_visits.append(
                        {
                            "tripName": trip.name,
                            "siteCode": site_visit.site.code,
                            "siteName": site_visit.site.name,
                            "url": site_visit.get_absolute_url(),
                        }
                    )

            trip_rows.append(
                {
                    "id": f"trip-{trip.pk}",
                    "tripId": trip.pk,
                    "tripName": trip.name,
                    "tripUrl": trip.get_absolute_url(),
                    "status": trip.status,
                    "statusLabel": trip.get_status_display(),
                    "start": trip.start_date.isoformat(),
                    "end": trip.end_date.isoformat(),
                    "siteVisits": scheduled_visits,
                }
            )

        context["trip_list_views"] = trip_list_views(
            "gantt",
            context.get("list_view_query_string", ""),
        )
        context["trip_gantt_rows"] = trip_rows
        context["unscheduled_site_visits"] = unscheduled_visits
        return context


class SiteVisitListView(
    LoginRequiredMixin,
    SortableListMixin,
    FilteredListMixin,
    SearchablePaginatedListMixin,
    ListView,
):
    model = SiteVisit
    template_name = "site_visits/list.html"
    search_placeholder = "Search site visits"
    filterset_class = SiteVisitFilterSet
    filter_preference_page_key = "site-visits"
    sort_preference_page_key = "site-visits"
    default_sort = "planned-day"
    sort_field_map = {
        "site": "site__code",
        "trip": "trip__name",
        "planned-day": "planned_day",
        "start-time": "planned_start",
        "status": "status",
        "jobs": "job_count",
    }

    def get_queryset(self):
        queryset = (
            SiteVisit.objects.select_related("site", "trip")
            .annotate(job_count=Count("jobs", distinct=True))
            .order_by()
        )
        return self.apply_sort(self.apply_filters(queryset))

    def apply_sort(self, queryset):
        sort_value = self.get_sort_value()
        descending = sort_value.startswith("-")
        sort_key = sort_value.removeprefix("-")
        sort_field = self.sort_field_map.get(sort_key)
        if not sort_field:
            return queryset
        if sort_key in {"planned-day", "start-time"}:
            primary = (
                F(sort_field).desc(nulls_last=True)
                if descending
                else F(sort_field).asc(nulls_last=True)
            )
            return queryset.order_by(primary, "site__code", "trip__name", "id")
        prefix = "-" if descending else ""
        return queryset.order_by(
            f"{prefix}{sort_field}",
            F("planned_day").asc(nulls_last=True),
            F("planned_start").asc(nulls_last=True),
            "site__code",
            "id",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_visit_list_views"] = site_visit_list_views(
            "table",
            context.get("list_view_query_string", ""),
        )
        return context


class SiteVisitMapView(FilteredListMixin, LoginRequiredMixin, ListView):
    model = SiteVisit
    template_name = "site_visits/map.html"
    filterset_class = SiteVisitFilterSet
    search_placeholder = "Search site visits"
    filter_preference_page_key = "site-visits"

    def get_queryset(self):
        queryset = SiteVisit.objects.select_related("site", "trip").annotate(
            job_count=Count("jobs", distinct=True)
        )
        return self.apply_filters(queryset).order_by(
            F("planned_day").asc(nulls_last=True),
            F("planned_start").asc(nulls_last=True),
            "site__code",
            "trip__name",
            "id",
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_visits = list(context["object_list"])
        context["site_visit_list_views"] = site_visit_list_views(
            "map",
            context.get("list_view_query_string", ""),
        )
        context["site_visit_map_visits"] = build_site_visit_map_data(site_visits)
        context["map_basemap_config"] = map_basemap_config()
        context["map_basemap_preference"] = map_basemap_preference(self.request.user)
        return context
