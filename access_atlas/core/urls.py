from django.urls import path

from . import views
from .autocomplete_views import (
    JobTemplateAutocompleteView,
    SiteAutocompleteView,
    TeamMemberAutocompleteView,
    UnassignedJobAutocompleteView,
    UnprogrammedJobAutocompleteView,
    WorkProgrammeAutocompleteView,
)

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("history/", views.global_history, name="global_history"),
    path(
        "history/<slug:object_type>/<int:history_id>/",
        views.global_history_detail,
        name="global_history_detail",
    ),
    path(
        "autocomplete/sites/",
        SiteAutocompleteView.as_view(),
        name="autocomplete_sites",
    ),
    path(
        "autocomplete/team-members/",
        TeamMemberAutocompleteView.as_view(),
        name="autocomplete_team_members",
    ),
    path(
        "autocomplete/job-templates/",
        JobTemplateAutocompleteView.as_view(),
        name="autocomplete_job_templates",
    ),
    path(
        "autocomplete/work-programmes/",
        WorkProgrammeAutocompleteView.as_view(),
        name="autocomplete_work_programmes",
    ),
    path(
        "autocomplete/unassigned-jobs/",
        UnassignedJobAutocompleteView.as_view(),
        name="autocomplete_unassigned_jobs",
    ),
    path(
        "autocomplete/unprogrammed-jobs/",
        UnprogrammedJobAutocompleteView.as_view(),
        name="autocomplete_unprogrammed_jobs",
    ),
]
