from django.urls import path

from . import views

urlpatterns = [
    path("", views.TripListView.as_view(), name="trip_list"),
    path("gantt/", views.TripGanttView.as_view(), name="trip_gantt"),
    path("new/", views.TripCreateView.as_view(), name="trip_create"),
    path("<int:pk>/map/", views.TripMapView.as_view(), name="trip_map"),
    path(
        "<int:pk>/requirements/",
        views.TripRequirementsView.as_view(),
        name="trip_requirements",
    ),
    path(
        "<int:trip_pk>/requirements/new/",
        views.TripRequirementCreateView.as_view(),
        name="trip_requirement_create",
    ),
    path(
        "<int:trip_pk>/requirements/<int:pk>/edit/",
        views.TripRequirementUpdateView.as_view(),
        name="trip_requirement_update",
    ),
    path(
        "<int:trip_pk>/requirements/<int:pk>/delete/",
        views.TripRequirementDeleteView.as_view(),
        name="trip_requirement_delete",
    ),
    path(
        "<int:pk>/requirements/<int:requirement_pk>/toggle/",
        views.toggle_trip_requirement,
        name="trip_requirement_toggle",
    ),
    path("<int:pk>/history/", views.TripHistoryView.as_view(), name="trip_history"),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.TripHistoryDetailView.as_view(),
        name="trip_history_detail",
    ),
    path("<int:pk>/", views.TripDetailView.as_view(), name="trip_detail"),
    path("<int:pk>/edit/", views.TripUpdateView.as_view(), name="trip_update"),
    path("<int:pk>/submit/", views.submit_trip_view, name="trip_submit"),
    path("<int:pk>/approve/", views.approve_trip_view, name="trip_approve"),
    path(
        "<int:pk>/return-to-draft/",
        views.return_trip_to_draft_view,
        name="trip_return_to_draft",
    ),
    path("<int:pk>/close/", views.close_trip_view, name="trip_close"),
    path(
        "<int:pk>/correct-closeout/",
        views.correct_trip_closeout_view,
        name="trip_closeout_correction",
    ),
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
        "site-visits/<int:pk>/history/",
        views.SiteVisitHistoryView.as_view(),
        name="site_visit_history",
    ),
    path(
        "site-visits/<int:pk>/history/<int:history_id>/",
        views.SiteVisitHistoryDetailView.as_view(),
        name="site_visit_history_detail",
    ),
    path(
        "site-visits/<int:pk>/edit/",
        views.SiteVisitUpdateView.as_view(),
        name="site_visit_update",
    ),
    path("site-visits/<int:pk>/assign/", views.assign_job, name="assign_job"),
    path("assignments/<int:pk>/unassign/", views.unassign_job, name="unassign_job"),
]
