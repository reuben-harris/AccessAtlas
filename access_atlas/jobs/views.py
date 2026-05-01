from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    default_jobs_map_preference,
    get_user_preference,
)
from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.mixins import ObjectFormMixin
from access_atlas.sites.models import Site

from .forms import (
    JobForm,
    JobFromTemplateForm,
    JobImportUploadForm,
    JobTemplateForm,
    RequirementForm,
    TemplateRequirementForm,
)
from .imports import (
    SESSION_KEY as JOB_IMPORT_SESSION_KEY,
)
from .imports import (
    create_jobs_from_import_rows,
    has_import_errors,
    parse_job_import_csv,
    rows_from_session,
)
from .models import Job, JobStatus, JobTemplate, Requirement, TemplateRequirement
from .services import create_job_from_template


class JobTemplateListView(LoginRequiredMixin, ListView):
    model = JobTemplate
    template_name = "jobs/job_template_list.html"


def _job_template_detail_sections(
    job_template: JobTemplate, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": job_template.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": job_template.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


def _job_detail_sections(job: Job, active_section: str) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": job.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": job.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


class JobTemplateDetailView(LoginRequiredMixin, DetailView):
    model = JobTemplate
    template_name = "jobs/job_template_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_template_detail_sections(
            self.object, "overview"
        )
        context["detail_navigation_label"] = "Job template sections"
        return context


class JobTemplateHistoryView(LoginRequiredMixin, DetailView):
    model = JobTemplate
    template_name = "jobs/job_template_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_template_detail_sections(
            self.object, "history"
        )
        context["detail_navigation_label"] = "Job template sections"
        context["history_records"] = self.object.history.all()
        return context


class JobTemplateCreateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    CreateView,
):
    history_action = "Created"
    model = JobTemplate
    form_class = JobTemplateForm
    template_name = "object_form.html"


class JobTemplateUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = JobTemplate
    form_class = JobTemplateForm
    template_name = "object_form.html"


class TemplateRequirementCreateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    CreateView,
):
    history_action = "Created"
    model = TemplateRequirement
    form_class = TemplateRequirementForm
    template_name = "object_form.html"

    def form_valid(self, form):
        form.instance.job_template = get_object_or_404(
            JobTemplate,
            pk=self.kwargs["template_pk"],
        )
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.job_template.get_absolute_url()

    def get_cancel_url(self):
        return get_object_or_404(
            JobTemplate, pk=self.kwargs["template_pk"]
        ).get_absolute_url()


class TemplateRequirementUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = TemplateRequirement
    form_class = TemplateRequirementForm
    template_name = "object_form.html"

    def get_success_url(self):
        return self.object.job_template.get_absolute_url()

    def get_cancel_url(self):
        return self.object.job_template.get_absolute_url()


class TemplateRequirementDeleteView(LoginRequiredMixin, DeleteView):
    model = TemplateRequirement
    template_name = "object_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_title"] = "Delete job template requirement"
        context["delete_message"] = (
            f'Are you sure you want to delete "{self.object.name}" from '
            f'"{self.object.job_template}"?'
        )
        return context

    def get_success_url(self):
        return self.object.job_template.get_absolute_url()

    def get_cancel_url(self):
        return self.object.job_template.get_absolute_url()


class JobListView(LoginRequiredMixin, ListView):
    model = Job
    paginate_by = 50
    template_name = "jobs/job_list.html"

    def get_queryset(self):
        queryset = super().get_queryset().select_related("site", "template")
        status = self.request.GET.get("status")
        if status == "unassigned":
            queryset = queryset.filter(
                status=JobStatus.UNASSIGNED,
                site_visit_assignment__isnull=True,
            )
        return queryset


class JobMapView(LoginRequiredMixin, ListView):
    model = Job
    template_name = "jobs/job_map.html"

    def get_queryset(self):
        return (
            Job.objects.select_related("site")
            .filter(status__in=JobStatus.values)
            .order_by("site__code", "title")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        map_preference = get_user_preference(
            self.request.user,
            JOBS_MAP_PREFERENCE_KEY,
            default_jobs_map_preference(),
        )
        visible_statuses = set(map_preference.get("visible_statuses", []))
        sites = {}
        for job in context["object_list"]:
            site = job.site
            site_data = sites.setdefault(
                site.pk,
                {
                    "site": {
                        "code": site.code,
                        "name": site.name,
                        "url": site.get_absolute_url(),
                        "latitude": float(site.latitude),
                        "longitude": float(site.longitude),
                    },
                    "jobs": [],
                },
            )
            site_data["jobs"].append(
                {
                    "title": job.title,
                    "url": job.get_absolute_url(),
                    "statusValue": job.status,
                    "status": job.get_status_display(),
                    "priority": job.get_priority_display(),
                }
            )
        context["map_sites"] = list(sites.values())
        context["map_status_layers"] = [
            {
                "value": JobStatus.UNASSIGNED,
                "label": JobStatus.UNASSIGNED.label,
                "color": "#667382",
                "rank": 20,
                "visible": JobStatus.UNASSIGNED in visible_statuses,
            },
            {
                "value": JobStatus.PLANNED,
                "label": JobStatus.PLANNED.label,
                "color": "#206bc4",
                "rank": 30,
                "visible": JobStatus.PLANNED in visible_statuses,
            },
            {
                "value": JobStatus.COMPLETED,
                "label": JobStatus.COMPLETED.label,
                "color": "#2fb344",
                "rank": 10,
                "visible": JobStatus.COMPLETED in visible_statuses,
            },
            {
                "value": JobStatus.CANCELLED,
                "label": JobStatus.CANCELLED.label,
                "color": "#d63939",
                "rank": 40,
                "visible": JobStatus.CANCELLED in visible_statuses,
            },
        ]
        context["map_preference"] = {
            "key": JOBS_MAP_PREFERENCE_KEY,
            "value": map_preference,
        }
        context["map_tile_layer"] = {
            "light": {
                "url": settings.MAP_TILE_URL,
                "attribution": settings.MAP_TILE_ATTRIBUTION,
            },
            "dark": {
                "url": settings.MAP_TILE_DARK_URL,
                "attribution": settings.MAP_TILE_DARK_ATTRIBUTION,
            },
            "maxZoom": settings.MAP_TILE_MAX_ZOOM,
        }
        return context


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_detail_sections(self.object, "overview")
        context["detail_navigation_label"] = "Job sections"
        return context


class JobHistoryView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_detail_sections(self.object, "history")
        context["detail_navigation_label"] = "Job sections"
        context["history_records"] = self.object.history.all()
        return context


class JobCreateView(
    HistoryReasonMixin, ObjectFormMixin, LoginRequiredMixin, CreateView
):
    history_action = "Created"
    model = Job
    form_class = JobForm
    template_name = "object_form.html"


class JobUpdateView(
    HistoryReasonMixin, ObjectFormMixin, LoginRequiredMixin, UpdateView
):
    model = Job
    form_class = JobForm
    template_name = "object_form.html"


@login_required
def create_job_from_template_view(request):
    form = JobFromTemplateForm(request.POST or None, site_queryset=Site.objects.all())
    if request.method == "POST" and form.is_valid():
        job = create_job_from_template(
            site=form.cleaned_data["site"],
            template=form.cleaned_data["template"],
        )
        messages.success(request, f"Created job from template: {job.title}")
        return redirect(job)
    return render(request, "jobs/job_from_template.html", {"form": form})


@login_required
def import_jobs_view(request):
    form = JobImportUploadForm(request.POST or None, request.FILES or None)
    rows = None
    if request.method == "POST" and form.is_valid():
        rows = parse_job_import_csv(form.cleaned_data["csv_file"])
        if not has_import_errors(rows):
            request.session[JOB_IMPORT_SESSION_KEY] = [
                row.as_session_data() for row in rows
            ]
            request.session.modified = True
        else:
            request.session.pop(JOB_IMPORT_SESSION_KEY, None)
            request.session.modified = True

    return render(
        request,
        "jobs/job_import.html",
        {
            "form": form,
            "rows": rows,
            "has_errors": has_import_errors(rows) if rows is not None else False,
        },
    )


@login_required
def confirm_jobs_import_view(request):
    if request.method != "POST":
        return redirect("job_import")

    session_rows = request.session.get(JOB_IMPORT_SESSION_KEY)
    if not session_rows:
        messages.error(request, "Upload and review a valid jobs CSV before importing.")
        return redirect("job_import")

    rows = rows_from_session(session_rows)
    jobs = create_jobs_from_import_rows(rows)
    request.session.pop(JOB_IMPORT_SESSION_KEY, None)
    request.session.modified = True
    messages.success(request, f"Imported {len(jobs)} jobs.")
    return redirect("job_list")


class RequirementCreateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    CreateView,
):
    history_action = "Created"
    model = Requirement
    form_class = RequirementForm
    template_name = "object_form.html"

    def form_valid(self, form):
        form.instance.job = get_object_or_404(Job, pk=self.kwargs["job_pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.job.get_absolute_url()

    def get_cancel_url(self):
        return get_object_or_404(Job, pk=self.kwargs["job_pk"]).get_absolute_url()


class RequirementUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = Requirement
    form_class = RequirementForm
    template_name = "object_form.html"

    def get_success_url(self):
        return self.object.job.get_absolute_url()

    def get_cancel_url(self):
        return self.object.job.get_absolute_url()


class RequirementDeleteView(LoginRequiredMixin, DeleteView):
    model = Requirement
    template_name = "object_confirm_delete.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_title"] = "Delete job requirement"
        context["delete_message"] = (
            f'Are you sure you want to delete "{self.object.name}" from '
            f'"{self.object.job}"?'
        )
        return context

    def get_success_url(self):
        return self.object.job.get_absolute_url()

    def get_cancel_url(self):
        return self.object.job.get_absolute_url()
