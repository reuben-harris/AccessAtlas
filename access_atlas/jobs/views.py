from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from access_atlas.accounts.preferences import (
    JOBS_MAP_PREFERENCE_KEY,
    default_jobs_map_preference,
    get_user_preference,
)
from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.imports import (
    clear_import_review,
    decode_uploaded_csv,
    import_review_context,
    load_import_rows,
    store_import_rows,
)
from access_atlas.core.maps import map_basemap_config, map_basemap_preference
from access_atlas.core.mixins import (
    FilteredListMixin,
    ObjectFormMixin,
    PaginatedObjectHistoryMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)
from access_atlas.sites.models import Site
from access_atlas.trips.approval import ApprovedTripChangeMixin

from .filters import JobFilterSet, JobTemplateFilterSet, WorkProgrammeFilterSet
from .forms import (
    AssignWorkProgrammeJobForm,
    JobForm,
    JobFromTemplateForm,
    JobImportUploadForm,
    JobTemplateForm,
    JobTemplateImportUploadForm,
    RequirementForm,
    TemplateRequirementForm,
    WorkProgrammeForm,
)
from .imports import (
    CSV_SESSION_KEY as JOB_IMPORT_CSV_SESSION_KEY,
)
from .imports import (
    SESSION_KEY as JOB_IMPORT_SESSION_KEY,
)
from .imports import (
    build_job_import_rows,
    create_jobs_from_import_rows,
    has_import_errors,
    parse_job_import_csv_text,
    rows_from_session,
)
from .models import (
    Job,
    JobStatus,
    JobTemplate,
    Requirement,
    TemplateRequirement,
    WorkProgramme,
)
from .services import assign_jobs_to_work_programme, create_job_from_template
from .status_display import JOB_STATUS_COLORS
from .template_imports import (
    CSV_SESSION_KEY as JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY,
)
from .template_imports import (
    SESSION_KEY as JOB_TEMPLATE_IMPORT_SESSION_KEY,
)
from .template_imports import (
    build_job_template_import_rows,
    create_job_templates_from_import_rows,
    has_template_import_errors,
    parse_job_template_import_csv_text,
    template_rows_from_session,
)

IMPORT_ACTION_REFRESH = "refresh"
IMPORT_ACTION_DISCARD = "discard"


def store_import_review(
    request,
    *,
    rows_session_key: str,
    csv_session_key: str,
    rows,
    csv_text: str | None,
) -> None:
    """Persist both the review rows and original CSV text for manual refresh."""

    store_import_rows(request, session_key=rows_session_key, rows=rows)
    if csv_text is None:
        request.session.pop(csv_session_key, None)
    else:
        request.session[csv_session_key] = csv_text
    request.session.modified = True


class JobTemplateListView(
    SortableListMixin,
    FilteredListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = JobTemplate
    template_name = "jobs/job_template_list.html"
    search_placeholder = "Search job templates"
    filterset_class = JobTemplateFilterSet
    filter_preference_page_key = "job-templates"
    sort_preference_page_key = "job-templates"
    default_sort = "title"
    sort_field_map = {
        "title": "title",
        "priority": "priority",
        "estimate": "estimated_duration_minutes",
        "active": "is_active",
    }

    def get_queryset(self):
        return self.apply_sort(self.apply_filters(super().get_queryset()))


class WorkProgrammeListView(
    SortableListMixin,
    FilteredListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = WorkProgramme
    template_name = "jobs/work_programme_list.html"
    search_placeholder = "Search work programmes"
    filterset_class = WorkProgrammeFilterSet
    filter_preference_page_key = "work-programmes"
    sort_preference_page_key = "work-programmes"
    default_sort = "start-date"
    sort_field_map = {
        "name": "name",
        "start-date": "start_date",
        "end-date": "end_date",
        "jobs": "job_count",
    }

    def get_queryset(self):
        queryset = super().get_queryset().annotate(job_count=Count("jobs"))
        return self.apply_sort(self.apply_filters(queryset))


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


def _work_programme_detail_sections(
    work_programme: WorkProgramme, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": work_programme.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": work_programme.get_history_url(),
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


class JobTemplateHistoryView(
    PaginatedObjectHistoryMixin,
    LoginRequiredMixin,
    DetailView,
):
    model = JobTemplate
    template_name = "jobs/job_template_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_template_detail_sections(
            self.object, "history"
        )
        context["detail_navigation_label"] = "Job template sections"
        context.update(self.get_history_context())
        return context


class WorkProgrammeDetailView(LoginRequiredMixin, DetailView):
    model = WorkProgramme
    template_name = "jobs/work_programme_detail.html"

    def get_queryset(self):
        return WorkProgramme.objects.prefetch_related("jobs__site")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _work_programme_detail_sections(
            self.object, "overview"
        )
        context["detail_navigation_label"] = "Work programme sections"
        context["assign_form"] = AssignWorkProgrammeJobForm()
        return context


@login_required
@require_POST
def assign_work_programme_job(request, pk):
    work_programme = get_object_or_404(WorkProgramme, pk=pk)
    form = AssignWorkProgrammeJobForm(request.POST)
    if form.is_valid():
        jobs = form.cleaned_data["jobs"]
        try:
            assigned_count = assign_jobs_to_work_programme(jobs, work_programme)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, f"Assigned {assigned_count} job(s).")
    else:
        messages.error(request, "Select one or more jobs without a work programme.")
    return redirect(work_programme)


class WorkProgrammeHistoryView(
    PaginatedObjectHistoryMixin,
    LoginRequiredMixin,
    DetailView,
):
    model = WorkProgramme
    template_name = "jobs/work_programme_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _work_programme_detail_sections(
            self.object, "history"
        )
        context["detail_navigation_label"] = "Work programme sections"
        context.update(self.get_history_context())
        return context


class WorkProgrammeCreateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    CreateView,
):
    history_action = "Created"
    model = WorkProgramme
    form_class = WorkProgrammeForm
    template_name = "object_form.html"


class WorkProgrammeUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = WorkProgramme
    form_class = WorkProgrammeForm
    template_name = "object_form.html"


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


@login_required
def import_job_templates_view(request):
    form = JobTemplateImportUploadForm(request.POST or None, request.FILES or None)
    rows = None
    if request.method == "POST":
        action = request.POST.get("import_action")
        if action == IMPORT_ACTION_DISCARD:
            clear_import_review(
                request,
                rows_session_key=JOB_TEMPLATE_IMPORT_SESSION_KEY,
                csv_session_key=JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY,
            )
            messages.info(request, "Discarded the retained job template import review.")
            return redirect("job_template_import")
        if action == IMPORT_ACTION_REFRESH:
            csv_text = request.session.get(JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY)
            if not csv_text:
                messages.error(request, "Upload a CSV before refreshing the review.")
                return redirect("job_template_import")
            rows = parse_job_template_import_csv_text(str(csv_text))
            store_import_review(
                request,
                rows_session_key=JOB_TEMPLATE_IMPORT_SESSION_KEY,
                csv_session_key=JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY,
                rows=rows,
                csv_text=str(csv_text),
            )
            messages.success(request, "Refreshed the job template import review.")
            return redirect("job_template_import")
        if form.is_valid():
            csv_text, csv_error = decode_uploaded_csv(form.cleaned_data["csv_file"])
            rows = (
                build_job_template_import_rows(None, csv_error)
                if csv_error
                else parse_job_template_import_csv_text(csv_text)
            )
            store_import_review(
                request,
                rows_session_key=JOB_TEMPLATE_IMPORT_SESSION_KEY,
                csv_session_key=JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY,
                rows=rows,
                csv_text=None if csv_error else csv_text,
            )
    elif request.method == "GET":
        rows = load_import_rows(
            request,
            session_key=JOB_TEMPLATE_IMPORT_SESSION_KEY,
            row_loader=template_rows_from_session,
        )

    return render(
        request,
        "jobs/job_template_import.html",
        {
            "form": form,
            "example_path": "docs/examples/job-template-test-import.csv",
            "confirm_url_name": "job_template_import_confirm",
            "confirm_button_label": "Create job templates",
            "retained_csv_available": bool(
                request.session.get(JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY)
            ),
            **import_review_context(
                request,
                rows=rows,
                sort_field_map={
                    "row": lambda row: row.row_number,
                    "title": lambda row: row.title.casefold(),
                    "default-priority": lambda row: row.priority_label.casefold(),
                    "estimate": lambda row: row.estimated_duration_minutes or 0,
                    "active": lambda row: row.active_label,
                    "result": lambda row: (row.is_valid, row.error.casefold()),
                },
            ),
        },
    )


@login_required
def confirm_job_templates_import_view(request):
    if request.method != "POST":
        return redirect("job_template_import")

    session_rows = request.session.get(JOB_TEMPLATE_IMPORT_SESSION_KEY)
    if not session_rows:
        messages.error(
            request,
            "Upload and review a valid job templates CSV before importing.",
        )
        return redirect("job_template_import")

    rows = template_rows_from_session(session_rows)
    if has_template_import_errors(rows):
        messages.error(
            request,
            "Upload and review a valid job templates CSV before importing.",
        )
        return redirect("job_template_import")
    templates = create_job_templates_from_import_rows(rows)
    clear_import_review(
        request,
        rows_session_key=JOB_TEMPLATE_IMPORT_SESSION_KEY,
        csv_session_key=JOB_TEMPLATE_IMPORT_CSV_SESSION_KEY,
    )
    messages.success(request, f"Imported {len(templates)} job templates.")
    return redirect("job_template_list")


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


class JobListView(
    SortableListMixin,
    FilteredListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = Job
    template_name = "jobs/job_list.html"
    search_placeholder = "Search jobs"
    filterset_class = JobFilterSet
    filter_preference_page_key = "jobs"
    sort_preference_page_key = "jobs"
    default_sort = "title"
    sort_field_map = {
        "title": "title",
        "site": "site__code",
        "work-programme": "work_programme__name",
        "due-date": "work_programme__end_date",
        "status": "status",
        "priority": "priority",
        "estimate": "estimated_duration_minutes",
    }

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related(
                "site",
                "template",
                "work_programme",
            )
        )
        return self.apply_sort(self.apply_filters(queryset))


class JobMapView(FilteredListMixin, LoginRequiredMixin, ListView):
    model = Job
    template_name = "jobs/job_map.html"
    filterset_class = JobFilterSet
    search_placeholder = "Search jobs"
    filter_preference_page_key = "jobs"

    def get_queryset(self):
        queryset = Job.objects.select_related("site", "work_programme").filter(
            status__in=JobStatus.values
        )
        return self.apply_filters(queryset).order_by("site__code", "title")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        map_preference = get_user_preference(
            self.request.user,
            JOBS_MAP_PREFERENCE_KEY,
            default_jobs_map_preference(),
        )
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
                    "workProgramme": str(job.work_programme)
                    if job.work_programme
                    else "",
                    "dueDate": job.due_date.isoformat() if job.due_date else "",
                }
            )
        context["map_sites"] = list(sites.values())
        context["map_status_layers"] = [
            {
                "value": JobStatus.UNASSIGNED,
                "label": JobStatus.UNASSIGNED.label,
                "color": JOB_STATUS_COLORS[JobStatus.UNASSIGNED],
                "rank": 40,
            },
            {
                "value": JobStatus.ASSIGNED,
                "label": JobStatus.ASSIGNED.label,
                "color": JOB_STATUS_COLORS[JobStatus.ASSIGNED],
                "rank": 30,
            },
            {
                "value": JobStatus.COMPLETED,
                "label": JobStatus.COMPLETED.label,
                "color": JOB_STATUS_COLORS[JobStatus.COMPLETED],
                "rank": 20,
            },
            {
                "value": JobStatus.CANCELLED,
                "label": JobStatus.CANCELLED.label,
                "color": JOB_STATUS_COLORS[JobStatus.CANCELLED],
                "rank": 10,
            },
        ]
        context["map_preference"] = {
            "key": JOBS_MAP_PREFERENCE_KEY,
            "value": map_preference,
        }
        context["map_basemap_config"] = map_basemap_config()
        context["map_basemap_preference"] = map_basemap_preference(self.request.user)
        return context


class JobChartsView(FilteredListMixin, LoginRequiredMixin, TemplateView):
    model = Job
    template_name = "jobs/job_charts.html"
    filterset_class = JobFilterSet
    search_placeholder = "Search jobs"
    filter_preference_page_key = "jobs"

    def get_context_data(self, **kwargs):
        queryset = Job.objects.select_related("site", "work_programme")
        filtered_jobs = self.apply_filters(queryset)
        context = super().get_context_data(**kwargs)
        counts = {
            row["status"]: row["count"]
            for row in filtered_jobs.values("status")
            .order_by()
            .annotate(count=Count("id"))
        }
        status_rows = [
            {
                "value": status,
                "label": status.label,
                "count": counts.get(status, 0),
                "color": JOB_STATUS_COLORS[status],
            }
            for status in JobStatus
        ]
        context["job_status_chart"] = {
            "total": sum(item["count"] for item in status_rows),
            "labels": [item["label"] for item in status_rows],
            "counts": [item["count"] for item in status_rows],
            "colors": [item["color"] for item in status_rows],
            "rows": status_rows,
        }
        context["search_result_count"] = filtered_jobs.count()
        return context


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_detail_sections(self.object, "overview")
        context["detail_navigation_label"] = "Job sections"
        return context


class JobHistoryView(PaginatedObjectHistoryMixin, LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _job_detail_sections(self.object, "history")
        context["detail_navigation_label"] = "Job sections"
        context.update(self.get_history_context())
        return context


class JobCreateView(
    HistoryReasonMixin, ObjectFormMixin, LoginRequiredMixin, CreateView
):
    history_action = "Created"
    model = Job
    form_class = JobForm
    template_name = "object_form.html"


class JobUpdateView(
    ApprovedTripChangeMixin,
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = Job
    form_class = JobForm
    template_name = "object_form.html"
    approval_reset_reason = "Returned to submitted after job update"

    def get_approval_trip(self):
        assignment = getattr(self.object, "site_visit_assignment", None)
        if assignment is None:
            return None
        return assignment.site_visit.trip


@login_required
def create_job_from_template_view(request):
    form = JobFromTemplateForm(request.POST or None, site_queryset=Site.objects.all())
    if request.method == "POST" and form.is_valid():
        job = create_job_from_template(
            site=form.cleaned_data["site"],
            template=form.cleaned_data["template"],
            work_programme=form.cleaned_data["work_programme"],
        )
        messages.success(request, f"Created job from template: {job.title}")
        return redirect(job)
    return render(request, "jobs/job_from_template.html", {"form": form})


@login_required
def import_jobs_view(request):
    form = JobImportUploadForm(request.POST or None, request.FILES or None)
    rows = None
    if request.method == "POST":
        action = request.POST.get("import_action")
        if action == IMPORT_ACTION_DISCARD:
            clear_import_review(
                request,
                rows_session_key=JOB_IMPORT_SESSION_KEY,
                csv_session_key=JOB_IMPORT_CSV_SESSION_KEY,
            )
            messages.info(request, "Discarded the retained jobs import review.")
            return redirect("job_import")
        if action == IMPORT_ACTION_REFRESH:
            csv_text = request.session.get(JOB_IMPORT_CSV_SESSION_KEY)
            if not csv_text:
                messages.error(request, "Upload a CSV before refreshing the review.")
                return redirect("job_import")
            rows = parse_job_import_csv_text(str(csv_text))
            store_import_review(
                request,
                rows_session_key=JOB_IMPORT_SESSION_KEY,
                csv_session_key=JOB_IMPORT_CSV_SESSION_KEY,
                rows=rows,
                csv_text=str(csv_text),
            )
            messages.success(request, "Refreshed the jobs import review.")
            return redirect("job_import")
        if form.is_valid():
            csv_text, csv_error = decode_uploaded_csv(form.cleaned_data["csv_file"])
            rows = (
                build_job_import_rows(None, csv_error)
                if csv_error
                else parse_job_import_csv_text(csv_text)
            )
            store_import_review(
                request,
                rows_session_key=JOB_IMPORT_SESSION_KEY,
                csv_session_key=JOB_IMPORT_CSV_SESSION_KEY,
                rows=rows,
                csv_text=None if csv_error else csv_text,
            )
    elif request.method == "GET":
        rows = load_import_rows(
            request,
            session_key=JOB_IMPORT_SESSION_KEY,
            row_loader=rows_from_session,
        )

    return render(
        request,
        "jobs/job_import.html",
        {
            "form": form,
            "example_path": "docs/examples/job-test-import.csv",
            "confirm_url_name": "job_import_confirm",
            "confirm_button_label": "Create jobs",
            "retained_csv_available": bool(
                request.session.get(JOB_IMPORT_CSV_SESSION_KEY)
            ),
            **import_review_context(
                request,
                rows=rows,
                sort_field_map={
                    "row": lambda row: row.row_number,
                    "site-code": lambda row: row.site_code.casefold(),
                    "template-title": lambda row: row.template_title.casefold(),
                    "work-programme": lambda row: row.work_programme_name.casefold(),
                    "status": lambda row: row.status_label.casefold(),
                    "closeout-note": lambda row: row.closeout_note.casefold(),
                    "result": lambda row: (row.is_valid, row.error.casefold()),
                },
            ),
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
    if has_import_errors(rows):
        messages.error(request, "Upload and review a valid jobs CSV before importing.")
        return redirect("job_import")
    jobs = create_jobs_from_import_rows(rows)
    clear_import_review(
        request,
        rows_session_key=JOB_IMPORT_SESSION_KEY,
        csv_session_key=JOB_IMPORT_CSV_SESSION_KEY,
    )
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
