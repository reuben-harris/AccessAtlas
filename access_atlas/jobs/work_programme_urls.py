from django.urls import path

from . import views

urlpatterns = [
    path("", views.WorkProgrammeListView.as_view(), name="work_programme_list"),
    path("new/", views.WorkProgrammeCreateView.as_view(), name="work_programme_create"),
    path(
        "<int:pk>/",
        views.WorkProgrammeDetailView.as_view(),
        name="work_programme_detail",
    ),
    path(
        "<int:pk>/history/",
        views.WorkProgrammeHistoryView.as_view(),
        name="work_programme_history",
    ),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.WorkProgrammeHistoryDetailView.as_view(),
        name="work_programme_history_detail",
    ),
    path(
        "<int:pk>/edit/",
        views.WorkProgrammeUpdateView.as_view(),
        name="work_programme_update",
    ),
    path(
        "<int:pk>/assign-job/",
        views.assign_work_programme_job,
        name="work_programme_assign_job",
    ),
]
