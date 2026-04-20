from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("access_atlas.core.urls")),
    path("accounts/", include("access_atlas.accounts.urls")),
    path("sites/", include("access_atlas.sites.urls")),
    path("jobs/", include("access_atlas.jobs.urls")),
    path("trips/", include("access_atlas.trips.urls")),
]
