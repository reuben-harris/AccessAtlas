from django.urls import path

from . import views

urlpatterns = [
    path("", views.JobTemplateListView.as_view(), name="job_template_list"),
    path("import/", views.import_job_templates_view, name="job_template_import"),
    path(
        "import/confirm/",
        views.confirm_job_templates_import_view,
        name="job_template_import_confirm",
    ),
    path("new/", views.JobTemplateCreateView.as_view(), name="job_template_create"),
    path(
        "<int:pk>/", views.JobTemplateDetailView.as_view(), name="job_template_detail"
    ),
    path(
        "<int:pk>/history/",
        views.JobTemplateHistoryView.as_view(),
        name="job_template_history",
    ),
    path(
        "<int:pk>/history/<int:history_id>/",
        views.JobTemplateHistoryDetailView.as_view(),
        name="job_template_history_detail",
    ),
    path(
        "<int:pk>/edit/",
        views.JobTemplateUpdateView.as_view(),
        name="job_template_update",
    ),
    path(
        "<int:template_pk>/requirements/new/",
        views.TemplateRequirementCreateView.as_view(),
        name="template_requirement_create",
    ),
    path(
        "requirements/<int:pk>/edit/",
        views.TemplateRequirementUpdateView.as_view(),
        name="template_requirement_update",
    ),
    path(
        "requirements/<int:pk>/delete/",
        views.TemplateRequirementDeleteView.as_view(),
        name="template_requirement_delete",
    ),
]
