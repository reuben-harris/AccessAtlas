from django.urls import path

from access_atlas.access_records import views as access_record_views

from . import views

urlpatterns = [
    path("", views.SiteListView.as_view(), name="site_list"),
    path("map/", views.SiteMapView.as_view(), name="site_map"),
    path("sync/", views.sync_sites_view, name="sync_sites"),
    path(
        "<int:pk>/access-records/",
        views.SiteAccessRecordsView.as_view(),
        name="site_access_records",
    ),
    path(
        "<int:pk>/photos/",
        views.SitePhotosView.as_view(),
        name="site_photos",
    ),
    path(
        "<int:pk>/photos/hide/",
        views.SitePhotoBulkHideView.as_view(),
        name="site_photo_bulk_hide",
    ),
    path(
        "<int:pk>/photos/download/",
        views.SitePhotoBulkDownloadView.as_view(),
        name="site_photo_bulk_download",
    ),
    path(
        "<int:pk>/history/",
        views.SiteHistoryView.as_view(),
        name="site_history",
    ),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.SiteHistoryDetailView.as_view(),
        name="site_history_detail",
    ),
    path(
        "<int:site_pk>/access-records/new/",
        access_record_views.AccessRecordCreateView.as_view(),
        name="access_record_create",
    ),
    path("<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
]
