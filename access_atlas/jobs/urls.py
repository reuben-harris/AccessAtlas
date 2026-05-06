from django.urls import path

from . import views

urlpatterns = [
    path("", views.JobListView.as_view(), name="job_list"),
    path("map/", views.JobMapView.as_view(), name="job_map"),
    path("import/", views.import_jobs_view, name="job_import"),
    path("import/confirm/", views.confirm_jobs_import_view, name="job_import_confirm"),
    path(
        "work-programmes/",
        views.WorkProgrammeListView.as_view(),
        name="work_programme_list",
    ),
    path(
        "work-programmes/new/",
        views.WorkProgrammeCreateView.as_view(),
        name="work_programme_create",
    ),
    path(
        "work-programmes/<int:pk>/",
        views.WorkProgrammeDetailView.as_view(),
        name="work_programme_detail",
    ),
    path(
        "work-programmes/<int:pk>/history/",
        views.WorkProgrammeHistoryView.as_view(),
        name="work_programme_history",
    ),
    path(
        "work-programmes/<int:pk>/edit/",
        views.WorkProgrammeUpdateView.as_view(),
        name="work_programme_update",
    ),
    path("new/", views.JobCreateView.as_view(), name="job_create"),
    path(
        "from-template/",
        views.create_job_from_template_view,
        name="job_create_from_template",
    ),
    path("<int:pk>/", views.JobDetailView.as_view(), name="job_detail"),
    path("<int:pk>/history/", views.JobHistoryView.as_view(), name="job_history"),
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
        "requirements/<int:pk>/delete/",
        views.RequirementDeleteView.as_view(),
        name="requirement_delete",
    ),
    path("templates/", views.JobTemplateListView.as_view(), name="job_template_list"),
    path(
        "templates/import/",
        views.import_job_templates_view,
        name="job_template_import",
    ),
    path(
        "templates/import/confirm/",
        views.confirm_job_templates_import_view,
        name="job_template_import_confirm",
    ),
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
        "templates/<int:pk>/history/",
        views.JobTemplateHistoryView.as_view(),
        name="job_template_history",
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
    path(
        "templates/requirements/<int:pk>/edit/",
        views.TemplateRequirementUpdateView.as_view(),
        name="template_requirement_update",
    ),
    path(
        "templates/requirements/<int:pk>/delete/",
        views.TemplateRequirementDeleteView.as_view(),
        name="template_requirement_delete",
    ),
]
