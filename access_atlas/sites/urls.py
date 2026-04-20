from django.urls import path

from . import views

urlpatterns = [
    path("", views.SiteListView.as_view(), name="site_list"),
    path("sync/", views.sync_sites_view, name="sync_sites"),
    path("<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
]
