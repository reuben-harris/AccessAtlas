from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.mixins import ObjectFormMixin
from access_atlas.sites.models import Site

from .forms import (
    JobForm,
    JobFromTemplateForm,
    JobTemplateForm,
    RequirementForm,
    TemplateRequirementForm,
)
from .models import Job, JobStatus, JobTemplate, Requirement, TemplateRequirement
from .services import create_job_from_template


class JobTemplateListView(LoginRequiredMixin, ListView):
    model = JobTemplate
    template_name = "jobs/job_template_list.html"


class JobTemplateDetailView(LoginRequiredMixin, DetailView):
    model = JobTemplate
    template_name = "jobs/job_template_detail.html"


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


class JobDetailView(LoginRequiredMixin, DetailView):
    model = Job
    template_name = "jobs/job_detail.html"


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
