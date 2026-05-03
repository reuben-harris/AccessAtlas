from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import CreateView, DetailView, UpdateView

from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.mixins import (
    ObjectFormMixin,
    PaginatedObjectHistoryMixin,
)

from .approval import ApprovedTripChangeMixin
from .forms import AssignJobForm, SiteVisitForm, TripForm
from .models import SiteVisit, SiteVisitJob, Trip
from .view_helpers import (
    site_visit_detail_sections,
    trip_action_controls,
    trip_approval_summary,
    trip_detail_sections,
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
