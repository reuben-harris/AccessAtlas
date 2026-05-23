from django.urls import path

from . import views

urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("map/", views.JobMapView.as_view(), name="job_map"),
    path("charts/", views.JobChartsView.as_view(), name="job_charts"),
    path("bulk-edit/", views.bulk_edit_jobs_view, name="job_bulk_edit"),
    path("import/", views.import_jobs_view, name="job_import"),
    path("import/confirm/", views.confirm_jobs_import_view, name="job_import_confirm"),
    path("new/", views.JobCreateView.as_view(), name="job_create"),
    path(
        "from-template/",
        views.create_job_from_template_view,
        name="job_create_from_template",
    ),
    path("<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path(
        "<int:pk>/requirements/",
        views.JobRequirementsView.as_view(),
        name="job_requirements",
    ),
    path("<int:pk>/history/", views.JobHistoryView.as_view(), name="job_history"),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.JobHistoryDetailView.as_view(),
        name="job_history_detail",
    ),
    path("<int:pk>/edit/", views.JobUpdateView.as_view(), name="job_update"),
    path(
        "<int:job_pk>/requirements/new/",
        views.RequirementCreateView.as_view(),
        name="requirement_create",
    ),
    path(
        "requirements/<int:pk>/edit/",
        views.RequirementUpdateView.as_view(),
        name="requirement_update",
    ),
    path(
        "requirements/<int:pk>/toggle/",
        views.toggle_requirement,
        name="requirement_toggle",
    ),
    path(
        "requirements/<int:pk>/delete/",
        views.RequirementDeleteView.as_view(),
        name="requirement_delete",
    ),
]
