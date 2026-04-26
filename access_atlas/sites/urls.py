from django.urls import path

from . import views

urlpatterns = [
    path("", views.SiteListView.as_view(), name="site_list"),
    path("sync/", views.sync_sites_view, name="sync_sites"),
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
    path("<int:pk>/", views.SiteDetailView.as_view(), name="site_detail"),
]
