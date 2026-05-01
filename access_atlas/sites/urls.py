from django.urls import path

from . import views

urlpatterns = [
    path("", views.SiteListView.as_view(), name="site_list"),
    path("sync/", views.sync_sites_view, name="sync_sites"),
    path(
        "<int:pk>/access-records/",
        views.SiteAccessRecordsView.as_view(),
        name="site_access_records",
    ),
    path(
        "<int:pk>/history/",
        views.SiteHistoryView.as_view(),
        name="site_history",
    ),
    path(
        "<int:site_pk>/access-records/new/",
        views.AccessRecordCreateView.as_view(),
        name="access_record_create",
    ),
    path(
        "access-records/<int:pk>/upload/",
        views.AccessRecordVersionCreateView.as_view(),
        name="access_record_version_create",
    ),
    path(
        "access-records/<int:pk>/edit/",
        views.AccessRecordUpdateView.as_view(),
        name="access_record_update",
    ),
    path(
        "access-records/<int:pk>/",
        views.AccessRecordDetailView.as_view(),
        name="access_record_detail",
    ),
    path(
        "access-records/<int:pk>/history/",
        views.AccessRecordHistoryView.as_view(),
        name="access_record_history",
    ),
    path(
        "access-records/<int:pk>/revisions/",
        views.AccessRecordRevisionsView.as_view(),
        name="access_record_revisions",
    ),
    path(
        "access-records/<int:pk>/map/",
        views.AccessRecordMapView.as_view(),
        name="access_record_map",
    ),
    path(
        "access-records/<int:pk>/download.geojson",
        views.access_record_geojson_download,
        name="access_record_geojson_download",
    ),
    path(
        "access-records/<int:pk>/download.kml",
        views.access_record_kml_download,
        name="access_record_kml_download",
    ),
    path(
        "access-records/<int:record_pk>/versions/<int:version_pk>/download.geojson",
        views.access_record_version_geojson_download,
        name="access_record_version_geojson_download",
    ),
    path(
        "access-records/<int:record_pk>/versions/<int:version_pk>/download.kml",
        views.access_record_version_kml_download,
        name="access_record_version_kml_download",
    ),
    path("<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
]
