from django.urls import path

from access_atlas.sites.views import dummy_site_feed

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("dummy/site-feed.json", dummy_site_feed, name="dummy_site_feed"),
]
