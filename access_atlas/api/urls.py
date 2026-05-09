from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("sites", views.SiteViewSet, basename="site-api")
router.register("job-templates", views.JobTemplateViewSet, basename="job-template-api")
router.register(
    "template-requirements",
    views.TemplateRequirementViewSet,
    basename="template-requirement-api",
)
router.register(
    "work-programmes",
    views.WorkProgrammeViewSet,
    basename="work-programme-api",
)
router.register("jobs", views.JobViewSet, basename="job-api")
router.register("requirements", views.RequirementViewSet, basename="requirement-api")
router.register("trips", views.TripViewSet, basename="trip-api")
router.register("site-visits", views.SiteVisitViewSet, basename="site-visit-api")
router.register(
    "site-visit-jobs",
    views.SiteVisitJobViewSet,
    basename="site-visit-job-api",
)
router.register(
    "access-records",
    views.AccessRecordViewSet,
    basename="access-record-api",
)
router.register(
    "access-record-versions",
    views.AccessRecordVersionViewSet,
    basename="access-record-version-api",
)
router.register("site-photos", views.SitePhotoViewSet, basename="site-photo-api")

urlpatterns = [
    path("schema/", SpectacularAPIView.as_view(), name="api_schema"),
    path(
        "schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="api_schema"),
        name="api_schema_swagger_ui",
    ),
    path("", include(router.urls)),
]
