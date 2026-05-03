from django.urls import path

from access_atlas.sites.views import dummy_site_feed

from .autocomplete_views import (
    JobTemplateAutocompleteView,
    SiteAutocompleteView,
    TeamMemberAutocompleteView,
    UnassignedJobAutocompleteView,
)
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("history/", views.global_history, name="global_history"),
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
        "autocomplete/unassigned-jobs/",
        UnassignedJobAutocompleteView.as_view(),
        name="autocomplete_unassigned_jobs",
    ),
    path("dummy/site-feed.json", dummy_site_feed, name="dummy_site_feed"),
]
