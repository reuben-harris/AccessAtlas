from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from access_atlas.jobs.models import JobStatus

from .forms import AssignJobForm, SiteVisitForm, TripForm
from .models import SiteVisit, SiteVisitJob, Trip


class TripListView(LoginRequiredMixin, ListView):
    model = Trip
    paginate_by = 50
    template_name = "trips/trip_list.html"


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_detail.html"


class TripCreateView(LoginRequiredMixin, CreateView):
    model = Trip
    form_class = TripForm
    template_name = "object_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["trip_leader"] = self.request.user
        return initial


class TripUpdateView(LoginRequiredMixin, UpdateView):
    model = Trip
    form_class = TripForm
    template_name = "object_form.html"


class SiteVisitDetailView(LoginRequiredMixin, DetailView):
    model = SiteVisit
    template_name = "trips/site_visit_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["assign_form"] = AssignJobForm(site=self.object.site)
        return context


class SiteVisitCreateView(LoginRequiredMixin, CreateView):
    model = SiteVisit
    form_class = SiteVisitForm
    template_name = "object_form.html"

    def form_valid(self, form):
        form.instance.trip = get_object_or_404(Trip, pk=self.kwargs["trip_pk"])
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.trip.get_absolute_url()


class SiteVisitUpdateView(LoginRequiredMixin, UpdateView):
    model = SiteVisit
    form_class = SiteVisitForm
    template_name = "object_form.html"


@require_POST
@login_required
def assign_job(request, pk):
    site_visit = get_object_or_404(SiteVisit, pk=pk)
    form = AssignJobForm(request.POST, site=site_visit.site)
    if form.is_valid():
        job = form.cleaned_data["job"]
        SiteVisitJob.objects.create(site_visit=site_visit, job=job)
        messages.success(request, f"Assigned job: {job.title}")
    else:
        messages.error(request, "Select an unassigned job for this site.")
    return redirect(site_visit)


@require_POST
@login_required
def unassign_job(request, pk):
    assignment = get_object_or_404(SiteVisitJob, pk=pk)
    site_visit = assignment.site_visit
    job = assignment.job
    assignment.delete()
    if job.status == JobStatus.PLANNED:
        job.status = JobStatus.UNASSIGNED
        job.save(update_fields=["status", "updated_at"])
    messages.success(request, f"Unassigned job: {job.title}")
    return redirect(site_visit)
