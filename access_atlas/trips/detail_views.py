from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, UpdateView

from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.maps import map_basemap_config, map_basemap_preference
from access_atlas.core.mixins import (
    ObjectFormMixin,
    PaginatedObjectHistoryMixin,
)
from access_atlas.jobs.forms import RequirementForm
from access_atlas.jobs.models import Job, Requirement

from .approval import ApprovedTripChangeMixin
from .forms import AssignJobForm, SiteVisitForm, TripForm
from .models import SiteVisit, SiteVisitJob, Trip
from .view_helpers import (
    build_trip_map_data,
    site_visit_detail_sections,
    trip_action_controls,
    trip_approval_summary,
    trip_detail_sections,
)

TRIP_REQUIREMENT_DEFAULT_ORDER = ("job__site__code", "job__title", "name", "id")
TRIP_REQUIREMENT_SORT_FIELDS = {
    "confirmed": ("is_checked", "job__site__code", "job__title", "name", "id"),
    "requirement": ("name", "job__site__code", "job__title", "id"),
    "type": ("requirement_type", "name", "job__site__code", "job__title", "id"),
    "quantity": ("quantity", "job__site__code", "job__title", "name", "id"),
    "job": ("job__title", "job__site__code", "name", "id"),
    "site": ("job__site__code", "job__site__name", "job__title", "name", "id"),
}


def trip_requirement_sort_value(value: str | None) -> str:
    if not value:
        return ""
    sort_key = value.removeprefix("-")
    if sort_key not in TRIP_REQUIREMENT_SORT_FIELDS:
        return ""
    return f"-{sort_key}" if value.startswith("-") else sort_key


def trip_requirement_ordering(sort_value: str) -> tuple[str, ...]:
    if not sort_value:
        return TRIP_REQUIREMENT_DEFAULT_ORDER
    descending = sort_value.startswith("-")
    fields = TRIP_REQUIREMENT_SORT_FIELDS[sort_value.removeprefix("-")]
    if not descending:
        return fields
    return tuple(f"-{field}" for field in fields)


def trip_requirement_queryset(trip: Trip, sort_value: str = ""):
    """Return requirements for jobs planned into this trip."""
    return (
        Requirement.objects.filter(job__site_visit_assignment__site_visit__trip=trip)
        .select_related("job", "job__site")
        .order_by(*trip_requirement_ordering(sort_value))
    )


def trip_requirement_job_queryset(trip: Trip):
    return (
        Job.objects.filter(site_visit_assignment__site_visit__trip=trip)
        .select_related("site")
        .order_by("site__code", "title", "id")
    )


def trip_requirements_frozen_reason(trip: Trip) -> str:
    if not trip.is_terminal:
        return ""
    return (
        f"This trip is {trip.get_status_display().lower()}, so its requirements "
        "are frozen."
    )


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_visits"] = self.object.site_visits.select_related(
            "site"
        ).order_by(
            F("planned_day").asc(nulls_last=True),
            F("planned_start").asc(nulls_last=True),
            "site__code",
            "id",
        )
        context["job_assignments"] = (
            SiteVisitJob.objects.filter(site_visit__trip=self.object)
            .select_related("site_visit__site", "job")
            .order_by(
                F("site_visit__planned_day").asc(nulls_last=True),
                F("site_visit__planned_start").asc(nulls_last=True),
                "site_visit__site__code",
                "site_visit_id",
                "job__title",
            )
        )
        context["detail_sections"] = trip_detail_sections(self.object, "overview")
        context["detail_navigation_label"] = "Trip sections"
        context["trip_action_controls"] = trip_action_controls(
            self.object, self.request.user
        )
        context["approval_summary"] = trip_approval_summary(self.object)
        return context


class TripHistoryView(PaginatedObjectHistoryMixin, LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = trip_detail_sections(self.object, "history")
        context["detail_navigation_label"] = "Trip sections"
        context["trip_action_controls"] = trip_action_controls(
            self.object, self.request.user
        )
        context.update(self.get_history_context())
        return context


class TripMapView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_map.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        site_visits = list(
            self.object.site_visits.select_related("site").order_by(
                F("planned_day").asc(nulls_last=True),
                F("planned_start").asc(nulls_last=True),
                "site__code",
                "id",
            )
        )
        context["detail_sections"] = trip_detail_sections(self.object, "map")
        context["detail_navigation_label"] = "Trip sections"
        context["trip_action_controls"] = trip_action_controls(
            self.object, self.request.user
        )
        context["trip_map_data"] = build_trip_map_data(site_visits)
        context["map_basemap_config"] = map_basemap_config()
        context["map_basemap_preference"] = map_basemap_preference(self.request.user)
        return context


class TripRequirementsView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_requirements.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sort_value = trip_requirement_sort_value(self.request.GET.get("sort"))
        assigned_jobs = trip_requirement_job_queryset(self.object)
        requirements_frozen_reason = trip_requirements_frozen_reason(self.object)
        context["trip"] = self.object
        context["requirements"] = trip_requirement_queryset(self.object, sort_value)
        context["requirements_readonly"] = self.object.is_terminal
        context["requirements_frozen_reason"] = requirements_frozen_reason
        context["has_assigned_jobs"] = assigned_jobs.exists()
        context["add_requirement_url"] = (
            reverse("trip_requirement_create", kwargs={"trip_pk": self.object.pk})
            if context["has_assigned_jobs"] and not self.object.is_terminal
            else ""
        )
        if self.object.is_terminal:
            context["add_requirement_disabled_reason"] = requirements_frozen_reason
        elif not context["has_assigned_jobs"]:
            context["add_requirement_disabled_reason"] = (
                "Add jobs to this trip before creating requirements."
            )
        else:
            context["add_requirement_disabled_reason"] = ""
        context["detail_sections"] = trip_detail_sections(
            self.object,
            "requirements",
        )
        context["detail_navigation_label"] = "Trip sections"
        context["current_sort"] = sort_value
        context["current_sort_field"] = sort_value.removeprefix("-")
        context["current_sort_descending"] = sort_value.startswith("-")
        context["sort_param"] = "sort"
        context["trip_action_controls"] = trip_action_controls(
            self.object,
            self.request.user,
        )
        return context


@login_required
@require_POST
def toggle_trip_requirement(request, pk, requirement_pk):
    trip = get_object_or_404(Trip, pk=pk)
    requirement = get_object_or_404(
        trip_requirement_queryset(trip),
        pk=requirement_pk,
    )
    if trip.is_terminal:
        return HttpResponseForbidden(
            "Requirements cannot be updated on completed or cancelled trips."
        )

    requirement.is_checked = "is_checked" in request.POST
    requirement._change_reason = "Updated requirement checklist state"
    requirement.save(update_fields=["is_checked"])
    return render(
        request,
        "trips/_trip_requirement_row.html",
        {
            "trip": trip,
            "requirement": requirement,
            "requirements_readonly": False,
        },
    )


class TripRequirementContextMixin:
    model = Requirement

    def get_trip(self):
        if hasattr(self, "_trip"):
            return self._trip
        self._trip = get_object_or_404(Trip, pk=self.kwargs["trip_pk"])
        return self._trip

    def get_job_queryset(self):
        return trip_requirement_job_queryset(self.get_trip())

    def dispatch(self, request, *args, **kwargs):
        trip = self.get_trip()
        if trip.is_terminal:
            messages.info(request, trip_requirements_frozen_reason(trip))
            return redirect(trip.get_requirements_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_trip().get_requirements_url()

    def get_cancel_url(self):
        return self.get_trip().get_requirements_url()


class TripRequirementCreateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    TripRequirementContextMixin,
    CreateView,
):
    history_action = "Created"
    form_class = RequirementForm
    template_name = "object_form.html"

    def dispatch(self, request, *args, **kwargs):
        trip = self.get_trip()
        if not trip.is_terminal and not self.get_job_queryset().exists():
            messages.info(
                request,
                "Add jobs to this trip before creating requirements.",
            )
            return redirect(trip.get_requirements_url())
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["job_queryset"] = self.get_job_queryset()
        return kwargs


class TripRequirementUpdateView(
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    TripRequirementContextMixin,
    UpdateView,
):
    form_class = RequirementForm
    template_name = "object_form.html"

    def get_queryset(self):
        return trip_requirement_queryset(self.get_trip())

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["job_queryset"] = self.get_job_queryset()
        return kwargs


class TripRequirementDeleteView(
    LoginRequiredMixin,
    TripRequirementContextMixin,
    DeleteView,
):
    template_name = "object_confirm_delete.html"

    def get_queryset(self):
        return trip_requirement_queryset(self.get_trip())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["delete_title"] = "Delete trip requirement"
        context["delete_message"] = (
            f'Are you sure you want to delete "{self.object.name}" from '
            f'"{self.object.job}"? This also removes it from the job.'
        )
        return context


class TripCreateView(
    HistoryReasonMixin, ObjectFormMixin, LoginRequiredMixin, CreateView
):
    history_action = "Created"
    model = Trip
    form_class = TripForm
    template_name = "object_form.html"

    def get_initial(self):
        initial = super().get_initial()
        initial["trip_leader"] = self.request.user
        return initial


class TripUpdateView(
    ApprovedTripChangeMixin,
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = Trip
    form_class = TripForm
    template_name = "object_form.html"
    approval_reset_reason = "Returned to submitted after trip update"

    def get_approval_trip(self):
        return self.object


class SiteVisitDetailView(LoginRequiredMixin, DetailView):
    model = SiteVisit
    template_name = "trips/site_visit_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if not self.object.trip.is_terminal:
            context["assign_form"] = AssignJobForm(site=self.object.site)
        context["detail_sections"] = site_visit_detail_sections(self.object, "overview")
        context["detail_navigation_label"] = "Site visit sections"
        return context


class SiteVisitHistoryView(PaginatedObjectHistoryMixin, LoginRequiredMixin, DetailView):
    model = SiteVisit
    template_name = "trips/site_visit_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = site_visit_detail_sections(self.object, "history")
        context["detail_navigation_label"] = "Site visit sections"
        context.update(self.get_history_context())
        return context


class SiteVisitCreateView(
    ApprovedTripChangeMixin,
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    CreateView,
):
    history_action = "Created"
    model = SiteVisit
    form_class = SiteVisitForm
    template_name = "trips/site_visit_form.html"
    approval_reset_reason = "Returned to submitted after site visit creation"

    def get_trip(self):
        if hasattr(self, "_trip"):
            return self._trip
        self._trip = get_object_or_404(Trip, pk=self.kwargs["trip_pk"])
        return self._trip

    def get_approval_trip(self):
        return self.get_trip()

    def dispatch(self, request, *args, **kwargs):
        trip = self.get_trip()
        if trip.is_terminal:
            messages.info(
                request,
                "Site visits cannot be added to completed or cancelled trips.",
            )
            return redirect(trip)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["trip"] = self.get_trip()
        return kwargs

    def form_valid(self, form):
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.trip.get_absolute_url()

    def get_cancel_url(self):
        return self.get_trip().get_absolute_url()


class SiteVisitUpdateView(
    ApprovedTripChangeMixin,
    HistoryReasonMixin,
    ObjectFormMixin,
    LoginRequiredMixin,
    UpdateView,
):
    model = SiteVisit
    form_class = SiteVisitForm
    template_name = "trips/site_visit_form.html"
    approval_reset_reason = "Returned to submitted after site visit update"

    def get_approval_trip(self):
        return self.object.trip
