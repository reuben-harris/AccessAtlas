from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
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
from access_atlas.core import bulk_edit as bulk_edit_utils
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
    ObjectHistoryDetailMixin,
    PaginatedObjectHistoryMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)
from access_atlas.sites.models import Site

from .filters import JobFilterSet, JobTemplateFilterSet, WorkProgrammeFilterSet
from .forms import (
    AssignWorkProgrammeJobForm,
    JobBulkEditForm,
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
from .services import (
    assign_jobs_to_work_programme,
    bulk_edit_jobs,
    bulk_editable_jobs_queryset,
    create_job_from_template,
    job_edit_frozen_reason,
    validate_bulk_edit_jobs,
)
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

JOB_REQUIREMENT_DEFAULT_ORDER = ("name", "id")
JOB_REQUIREMENT_SORT_FIELDS = {
    "confirmed": ("is_checked", "name", "id"),
    "requirement": ("name", "id"),
    "type": ("requirement_type", "name", "id"),
    "quantity": ("quantity", "name", "id"),
}


def job_requirement_sort_value(value: str | None) -> str:
    if not value:
        return ""
    sort_key = value.removeprefix("-")
    if sort_key not in JOB_REQUIREMENT_SORT_FIELDS:
        return ""
    return f"-{sort_key}" if value.startswith("-") else sort_key


def job_requirement_ordering(sort_value: str) -> tuple[str, ...]:
    if not sort_value:
        return JOB_REQUIREMENT_DEFAULT_ORDER
    descending = sort_value.startswith("-")
    fields = JOB_REQUIREMENT_SORT_FIELDS[sort_value.removeprefix("-")]
    if not descending:
        return fields
    return tuple(f"-{field}" for field in fields)


def job_requirement_queryset(job: Job, sort_value: str = ""):
    """Return requirements for one job using the job detail table sort."""
    return job.requirements.select_related(
        "job",
        "job__site_visit_assignment__site_visit__trip",
    ).order_by(*job_requirement_ordering(sort_value))


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
            "label": "Requirements",
            "icon": "ti-list-check",
            "url": job.get_requirements_url(),
            "is_active": active_section == "requirements",
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
        "completed-date": "completed_date",
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
                "site_visit_assignment__site_visit__trip",
            )
        )
        return self.apply_sort(self.apply_filters(queryset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        has_selectable_jobs_on_page = False
        for job in context["object_list"]:
            job.edit_frozen_reason = job_edit_frozen_reason(job)
            if not job.edit_frozen_reason:
                has_selectable_jobs_on_page = True
        bulk_selectable_count = bulk_editable_jobs_queryset(self.get_queryset()).count()
        context["has_selectable_jobs_on_page"] = has_selectable_jobs_on_page
        context["bulk_selectable_count"] = bulk_selectable_count
        context["bulk_excluded_count"] = max(
            0,
            context.get("search_result_count", 0) - bulk_selectable_count,
        )
        context["bulk_edit_filter_query_string"] = _job_bulk_edit_filter_query_string(
            self.request
        )
        return context


def _job_bulk_base_queryset():
    return Job.objects.select_related(
        "site",
        "template",
        "work_programme",
        "site_visit_assignment__site_visit__trip",
    )


def _integer_values_from_request(request, field_name: str) -> set[int]:
    return bulk_edit_utils.integer_values_from_request(request, field_name)


def _selected_job_ids_from_request(request) -> set[int]:
    return bulk_edit_utils.selected_object_ids_from_request(request)


def _excluded_job_ids_from_request(request) -> set[int]:
    return bulk_edit_utils.excluded_object_ids_from_request(request)


def _job_bulk_queryset_from_request(request):
    return bulk_edit_utils.bulk_queryset_from_request(
        request,
        base_queryset=_job_bulk_base_queryset(),
        filterset_class=JobFilterSet,
        select_all_queryset=bulk_editable_jobs_queryset,
    ).order_by(
        "site__code",
        "title",
    )


def _job_list_redirect_url(request) -> str:
    query_string = request.GET.urlencode()
    url = reverse("job_list")
    return f"{url}?{query_string}" if query_string else url


def _job_bulk_edit_filter_query_string(request) -> str:
    query = request.GET.copy()
    for parameter_name in ("pk", "_all", "_exclude", "errors_only", "page"):
        query.pop(parameter_name, None)
    return query.urlencode()


def _job_bulk_preview_url(request) -> str:
    return bulk_edit_utils.bulk_preview_url(request, route_name="job_bulk_edit")


def _job_bulk_selection_signature(queryset) -> list[int]:
    return bulk_edit_utils.bulk_selection_signature(queryset)


def _job_bulk_edit_session_data(post_data) -> dict[str, list[str]]:
    editable_fields = (
        "priority",
        "work_programme",
        "status",
        "completed_date",
        "closeout_note",
        "_nullify",
    )
    return bulk_edit_utils.bulk_edit_session_data(post_data, editable_fields)


def _bulk_edit_querydict_from_session(data: dict[str, list[str]]):
    return bulk_edit_utils.querydict_from_session(data)


def _store_bulk_edit_validation_attempt(request, queryset, post_data) -> None:
    bulk_edit_utils.store_bulk_edit_validation_attempt(
        request,
        session_key=JOB_BULK_EDIT_VALIDATION_SESSION_KEY,
        queryset=queryset,
        post_data=post_data,
        editable_fields=(
            "priority",
            "work_programme",
            "status",
            "completed_date",
            "closeout_note",
            "_nullify",
        ),
    )


def _clear_bulk_edit_validation_attempt(request) -> None:
    bulk_edit_utils.clear_bulk_edit_validation_attempt(
        request,
        session_key=JOB_BULK_EDIT_VALIDATION_SESSION_KEY,
    )


def _bulk_edit_validation_attempt(request, queryset) -> dict | None:
    return bulk_edit_utils.bulk_edit_validation_attempt(
        request,
        session_key=JOB_BULK_EDIT_VALIDATION_SESSION_KEY,
        queryset=queryset,
    )


def _bulk_edit_kwargs_from_form(form: JobBulkEditForm) -> dict:
    return {
        "priority": form.cleaned_data["priority"],
        "work_programme": form.cleaned_data["work_programme"],
        "clear_work_programme": "work_programme" in form.nullified_fields(),
        "status": form.cleaned_data["status"],
        "completed_date": form.cleaned_data["completed_date"],
        "clear_completed_date": "completed_date" in form.nullified_fields(),
        "closeout_note": form.cleaned_data["closeout_note"],
    }


BULK_PREVIEW_SORT_FIELD_MAP = {
    "title": "title",
    "site": "site__code",
    "work-programme": "work_programme__name",
    "due-date": "work_programme__end_date",
    "completed-date": "completed_date",
    "status": "status",
    "priority": "priority",
    "estimate": "estimated_duration_minutes",
}


def _normalize_bulk_preview_sort(value: str | None) -> str:
    return bulk_edit_utils.normalize_bulk_preview_sort(
        value,
        BULK_PREVIEW_SORT_FIELD_MAP,
    )


def _bulk_preview_context(request, selected_jobs, *, bulk_edit_issues: dict[int, str]):
    return bulk_edit_utils.bulk_preview_context(
        request,
        selected_jobs,
        bulk_edit_issues=bulk_edit_issues,
        sort_field_map=BULK_PREVIEW_SORT_FIELD_MAP,
        object_context_name="selected_jobs",
    )


@login_required
def bulk_edit_jobs_view(request):
    is_htmx = request.headers.get("HX-Request") == "true"
    if request.method == "POST" and "apply_bulk_edit" not in request.POST:
        _clear_bulk_edit_validation_attempt(request)
        return redirect(_job_bulk_preview_url(request))

    selected_jobs_queryset = _job_bulk_queryset_from_request(request)
    selected_count = selected_jobs_queryset.count()
    if not selected_count:
        messages.error(request, "Select one or more editable jobs to bulk edit.")
        if is_htmx:
            response = HttpResponse()
            response["HX-Redirect"] = _job_list_redirect_url(request)
            return response
        return redirect(_job_list_redirect_url(request))

    select_all = "_all" in request.POST or "_all" in request.GET
    excluded_count = len(_excluded_job_ids_from_request(request))
    validation_attempt = _bulk_edit_validation_attempt(request, selected_jobs_queryset)
    bulk_edit_issues: dict[int, str] = {}
    if "apply_bulk_edit" in request.POST:
        form = JobBulkEditForm(request.POST)
        if form.is_valid():
            bulk_edit_kwargs = _bulk_edit_kwargs_from_form(form)
            validation = validate_bulk_edit_jobs(
                selected_jobs_queryset,
                **bulk_edit_kwargs,
            )
            if validation.is_valid:
                result = bulk_edit_jobs(selected_jobs_queryset, **bulk_edit_kwargs)
                _clear_bulk_edit_validation_attempt(request)
                if result.updated:
                    messages.success(
                        request,
                        (
                            f"Bulk edit checked {selected_count} job(s). "
                            f"Updated {result.updated}."
                        ),
                    )
                else:
                    messages.info(
                        request,
                        (
                            f"Bulk edit checked {selected_count} job(s). "
                            "No changes were needed."
                        ),
                    )
                return redirect(_job_list_redirect_url(request))
            _store_bulk_edit_validation_attempt(
                request,
                selected_jobs_queryset,
                request.POST,
            )
            bulk_edit_issues = validation.by_object_id()
            form.add_error(
                None,
                (
                    "Resolve the blocking jobs in the selection preview before "
                    "applying this bulk edit."
                ),
            )
        else:
            _clear_bulk_edit_validation_attempt(request)
    elif validation_attempt:
        form = JobBulkEditForm(
            _bulk_edit_querydict_from_session(validation_attempt.get("data") or {})
        )
        if form.is_valid():
            validation = validate_bulk_edit_jobs(
                selected_jobs_queryset,
                **_bulk_edit_kwargs_from_form(form),
            )
            bulk_edit_issues = validation.by_object_id()
    else:
        form = JobBulkEditForm()

    preview_context = _bulk_preview_context(
        request,
        selected_jobs_queryset,
        bulk_edit_issues=bulk_edit_issues,
    )
    for job in preview_context["selected_jobs"]:
        job.bulk_edit_blocker_reason = bulk_edit_issues.get(job.pk, "")

    return render(
        request,
        "jobs/_job_bulk_edit_preview.html" if is_htmx else "jobs/job_bulk_edit.html",
        {
            "form": form,
            "selected_count": selected_count,
            "selected_ids": []
            if select_all
            else list(selected_jobs_queryset.values_list("pk", flat=True)),
            **preview_context,
            "select_all": select_all,
            "excluded_count": excluded_count,
            "has_bulk_edit_issues": bool(bulk_edit_issues),
            "bulk_edit_issue_count": len(bulk_edit_issues),
            "nullified_fields": form.nullified_fields() if form.is_bound else set(),
            "nullable_field_labels": form.nullable_field_label_map(),
            "cancel_url": _job_list_redirect_url(request),
            "is_htmx": is_htmx,
        },
    )


class JobMapView(FilteredListMixin, LoginRequiredMixin, ListView):
    model = Job
    template_name = "jobs/job_map.html"
    filterset_class = JobFilterSet
    search_placeholder = "Search jobs"
    filter_preference_page_key = "jobs"

    def get_queryset(self):
        queryset = Job.objects.select_related(
            "site",
            "work_programme",
            "site_visit_assignment__site_visit__trip",
        ).filter(
            status__in=JobStatus.values,
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
            frozen_reason = job_edit_frozen_reason(job)
            site_data = sites.setdefault(
                site.pk,
                {
                    "site": {
                        "id": site.pk,
                        "code": site.display_code,
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
                    "id": job.pk,
                    "title": job.title,
                    "url": job.get_absolute_url(),
                    "statusValue": job.status,
                    "status": job.get_status_display(),
                    "priority": job.get_priority_display(),
                    "workProgramme": str(job.work_programme)
                    if job.work_programme
                    else "",
                    "dueDate": job.due_date.isoformat() if job.due_date else "",
                    "bulkEditable": not bool(frozen_reason),
                    "bulkDisabledReason": frozen_reason,
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
        context["bulk_edit_filter_query_string"] = _job_bulk_edit_filter_query_string(
            self.request
        )
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
        context["job_edit_frozen_reason"] = job_edit_frozen_reason(self.object)
        return context


class JobRequirementsView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_requirements.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort_value = job_requirement_sort_value(self.request.GET.get("sort"))
        requirements_readonly = job_requirements_readonly(self.object)
        context["detail_sections"] = _job_detail_sections(self.object, "requirements")
        context["detail_navigation_label"] = "Job sections"
        context["job_edit_frozen_reason"] = job_edit_frozen_reason(self.object)
        context["requirements"] = job_requirement_queryset(self.object, sort_value)
        context["requirements_readonly"] = requirements_readonly
        context["requirements_frozen_reason"] = job_requirements_frozen_reason(
            self.object
        )
        context["add_requirement_url"] = (
            reverse("requirement_create", kwargs={"job_pk": self.object.pk})
            if not requirements_readonly
            else ""
        )
        context["current_sort"] = sort_value
        context["current_sort_field"] = sort_value.removeprefix("-")
        context["current_sort_descending"] = sort_value.startswith("-")
        context["sort_param"] = "sort"
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
    HistoryReasonMixin, ObjectFormMixin, LoginRequiredMixin, UpdateView
):
    model = Job
    form_class = JobForm
    template_name = "object_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        frozen_reason = job_edit_frozen_reason(self.object)
        if frozen_reason:
            messages.info(request, frozen_reason)
            return redirect(self.object)
        return super().dispatch(request, *args, **kwargs)


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
                    "completed-date": lambda row: row.completed_date or "",
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


def job_requirements_readonly(job: Job) -> bool:
    return job_requirements_frozen_reason(job) != ""


def job_requirements_frozen_reason(job: Job) -> str:
    if job.is_terminal:
        return (
            f"This job is {job.get_status_display().lower()}, so its requirements "
            "are frozen."
        )
    assignment = getattr(job, "site_visit_assignment", None)
    if assignment is None or not assignment.site_visit.trip.is_terminal:
        return ""
    trip = assignment.site_visit.trip
    return (
        f"This job is assigned to {trip.get_status_display().lower()} trip "
        f'"{trip.name}", so its requirements are frozen.'
    )


def requirement_is_readonly(requirement: Requirement) -> bool:
    return requirement.is_frozen


@login_required
@require_POST
def toggle_requirement(request, pk):
    requirement = get_object_or_404(
        Requirement.objects.select_related(
            "job",
            "job__site_visit_assignment__site_visit__trip",
        ),
        pk=pk,
    )
    if requirement_is_readonly(requirement):
        return HttpResponseForbidden(requirement.frozen_reason)

    requirement.is_checked = "is_checked" in request.POST
    requirement._change_reason = "Updated requirement checklist state"
    requirement.save(update_fields=["is_checked"])
    return render(
        request,
        "jobs/_job_requirement_row.html",
        {
            "requirement": requirement,
            "requirements_readonly": False,
        },
    )


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

    def get_job(self):
        if hasattr(self, "_job"):
            return self._job
        self._job = get_object_or_404(Job, pk=self.kwargs["job_pk"])
        return self._job

    def dispatch(self, request, *args, **kwargs):
        job = self.get_job()
        if job_requirements_readonly(job):
            messages.info(request, job_requirements_frozen_reason(job))
            return redirect(job.get_requirements_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["fixed_job"] = self.get_job()
        return kwargs

    def form_valid(self, form):
        form.instance.job = self.get_job()
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.job.get_requirements_url()

    def get_cancel_url(self):
        return self.get_job().get_requirements_url()


class RequirementUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = Requirement
    form_class = RequirementForm
    template_name = "object_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if requirement_is_readonly(self.object):
            messages.info(request, job_requirements_frozen_reason(self.object.job))
            return redirect(self.object.job.get_requirements_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["fixed_job"] = self.object.job
        return kwargs

    def get_success_url(self):
        return self.object.job.get_requirements_url()

    def get_cancel_url(self):
        return self.object.job.get_requirements_url()


class RequirementDeleteView(LoginRequiredMixin, DeleteView):
    model = Requirement
    template_name = "object_confirm_delete.html"

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if requirement_is_readonly(self.object):
            messages.info(request, job_requirements_frozen_reason(self.object.job))
            return redirect(self.object.job.get_requirements_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_title"] = "Delete job requirement"
        context["delete_message"] = (
            f'Are you sure you want to delete "{self.object.name}" from '
            f'"{self.object.job}"?'
        )
        return context

    def get_success_url(self):
        return self.object.job.get_requirements_url()

    def get_cancel_url(self):
        return self.object.job.get_requirements_url()


class JobTemplateHistoryDetailView(
    ObjectHistoryDetailMixin,
    JobTemplateHistoryView,
):
    pass


class WorkProgrammeHistoryDetailView(
    ObjectHistoryDetailMixin,
    WorkProgrammeHistoryView,
):
    pass


class JobHistoryDetailView(
    ObjectHistoryDetailMixin,
    JobHistoryView,
):
    pass


JOB_BULK_EDIT_VALIDATION_SESSION_KEY = "jobs.bulk_edit.validation_attempt"
