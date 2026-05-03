from django.db.models import F
from django.views.generic import ListView

from access_atlas.core.mixins import SearchablePaginatedListMixin, SortableListMixin

from .models import Trip
from .view_helpers import trip_list_views


class TripListView(
    SortableListMixin,
    SearchablePaginatedListMixin,
    ListView,
):
    model = Trip
    template_name = "trips/trip_list.html"
    search_fields = ("name", "notes", "trip_leader__email", "trip_leader__display_name")
    search_placeholder = "Search trips"
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
        return self.apply_sort(self.apply_search(queryset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["trip_list_views"] = trip_list_views("table")
        return context


class TripGanttView(ListView):
    model = Trip
    template_name = "trips/trip_gantt.html"

    def get_queryset(self):
        return (
            Trip.objects.select_related("trip_leader")
            .prefetch_related("site_visits__site")
            .order_by("start_date", "name")
        )

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

        context["trip_list_views"] = trip_list_views("gantt")
        context["trip_gantt_rows"] = trip_rows
        context["unscheduled_site_visits"] = unscheduled_visits
        return context
