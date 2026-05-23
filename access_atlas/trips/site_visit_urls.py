from django.urls import path

from . import views

urlpatterns = [
    path("", views.SiteVisitListView.as_view(), name="site_visit_list"),
    path("map/", views.SiteVisitMapView.as_view(), name="site_visit_map"),
    path("<int:pk>/", views.SiteVisitDetailView.as_view(), name="site_visit_detail"),
    path(
        "<int:pk>/history/",
        views.SiteVisitHistoryView.as_view(),
        name="site_visit_history",
    ),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.SiteVisitHistoryDetailView.as_view(),
        name="site_visit_history_detail",
    ),
    path(
        "<int:pk>/edit/", views.SiteVisitUpdateView.as_view(), name="site_visit_update"
    ),
    path(
        "<int:pk>/delete/",
        views.SiteVisitDeleteView.as_view(),
        name="site_visit_delete",
    ),
    path("<int:pk>/assign/", views.assign_job, name="assign_job"),
    path(
        "assignments/<int:pk>/unassign/",
        views.unassign_job,
        name="unassign_job",
    ),
]
