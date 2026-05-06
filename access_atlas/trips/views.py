from django.contrib.auth.mixins import LoginRequiredMixin

from .action_views import (
    approve_trip_view,
    assign_job,
    cancel_trip_view,
    close_trip_view,
    submit_trip_view,
    unassign_job,
)
from .detail_views import (
    SiteVisitCreateView,
    SiteVisitDetailView,
    SiteVisitHistoryView,
    SiteVisitUpdateView,
    TripCreateView,
    TripDetailView,
    TripHistoryView,
    TripMapView,
    TripUpdateView,
)
from .list_views import TripGanttView, TripListView

__all__ = [
    "LoginRequiredMixin",
    "TripListView",
    "TripGanttView",
    "TripDetailView",
    "TripMapView",
    "TripHistoryView",
    "TripCreateView",
    "TripUpdateView",
    "SiteVisitDetailView",
    "SiteVisitHistoryView",
    "SiteVisitCreateView",
    "SiteVisitUpdateView",
    "assign_job",
    "unassign_job",
    "submit_trip_view",
    "approve_trip_view",
    "close_trip_view",
    "cancel_trip_view",
]
