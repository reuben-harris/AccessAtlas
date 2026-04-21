from django.urls import path

from . import views

urlpatterns = [
    path("", views.TripListView.as_view(), name="trip_list"),
    path("new/", views.TripCreateView.as_view(), name="trip_create"),
    path("<int:pk>/", views.TripDetailView.as_view(), name="trip_detail"),
    path("<int:pk>/edit/", views.TripUpdateView.as_view(), name="trip_update"),
    path("<int:pk>/close/", views.close_trip_view, name="trip_close"),
    path("<int:pk>/cancel/", views.cancel_trip_view, name="trip_cancel"),
    path(
        "<int:trip_pk>/site-visits/new/",
        views.SiteVisitCreateView.as_view(),
        name="site_visit_create",
    ),
    path(
        "site-visits/<int:pk>/",
        views.SiteVisitDetailView.as_view(),
        name="site_visit_detail",
    ),
    path(
        "site-visits/<int:pk>/edit/",
        views.SiteVisitUpdateView.as_view(),
        name="site_visit_update",
    ),
    path("site-visits/<int:pk>/assign/", views.assign_job, name="assign_job"),
    path("assignments/<int:pk>/unassign/", views.unassign_job, name="unassign_job"),
]
