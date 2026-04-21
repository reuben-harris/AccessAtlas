from django.urls import path

from . import views

urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("map/", views.JobMapView.as_view(), name="job_map"),
    path("import/", views.import_jobs_view, name="job_import"),
    path("import/confirm/", views.confirm_jobs_import_view, name="job_import_confirm"),
    path("new/", views.JobCreateView.as_view(), name="job_create"),
    path(
        "from-template/",
        views.create_job_from_template_view,
        name="job_create_from_template",
    ),
    path("<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
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
    path("templates/", views.JobTemplateListView.as_view(), name="job_template_list"),
    path(
        "templates/new/",
        views.JobTemplateCreateView.as_view(),
        name="job_template_create",
    ),
    path(
        "templates/<int:pk>/",
        views.JobTemplateDetailView.as_view(),
        name="job_template_detail",
    ),
    path(
        "templates/<int:pk>/edit/",
        views.JobTemplateUpdateView.as_view(),
        name="job_template_update",
    ),
    path(
        "templates/<int:template_pk>/requirements/new/",
        views.TemplateRequirementCreateView.as_view(),
        name="template_requirement_create",
    ),
]
