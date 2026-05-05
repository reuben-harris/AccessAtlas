from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("access_atlas.core.urls")),
    path("accounts/", include("access_atlas.accounts.urls")),
    path("accounts/sso/", include("allauth.urls")),
    path("sites/", include("access_atlas.sites.urls")),
    path("jobs/", include("access_atlas.jobs.urls")),
    path("trips/", include("access_atlas.trips.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
