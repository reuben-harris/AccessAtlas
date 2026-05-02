from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from access_atlas.core.history import HistoryReasonMixin
from access_atlas.core.mixins import (
    ObjectFormMixin,
    PaginatedObjectHistoryMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)

from .approval import (
    APPROVAL_CONFIRM_FIELD,
    APPROVAL_RESET_MESSAGE,
    ApprovedTripChangeMixin,
)
from .forms import AssignJobForm, SiteVisitForm, TripCloseoutForm, TripForm
from .models import SiteVisit, SiteVisitJob, Trip, TripStatus
from .services import (
    approve_trip,
    assign_job_to_site_visit,
    cancel_trip,
    close_trip,
    get_trip_cancel_summary,
    invalidate_trip_approval,
    submit_trip_for_approval,
    unassign_site_visit_job,
    user_can_approve_trip,
)


class TripListView(
    SortableListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = Trip
    template_name = "trips/trip_list.html"
    search_fields = ("name", "notes", "trip_leader__email", "trip_leader__display_name")
    search_placeholder = "Search trips"
    sort_preference_page_key = "trips"
    default_sort = "start-date"
    sort_field_map = {
        "name": "name",
        "start-date": "start_date",
        "end-date": "end_date",
        "leader": "trip_leader__email",
        "status": "status",
    }

    def get_queryset(self):
        queryset = super().get_queryset().select_related("trip_leader")
        return self.apply_sort(self.apply_search(queryset))


def _trip_detail_sections(
    trip: Trip, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": trip.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": trip.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


def _site_visit_detail_sections(
    site_visit: SiteVisit, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": site_visit.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": site_visit.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


def _trip_action_controls(trip: Trip, user) -> dict[str, object]:
    closed_state = trip.get_status_display().lower()
    submit_disabled_reason = None
    if trip.is_terminal:
        submit_disabled_reason = (
            f"This trip is already {closed_state} and cannot be submitted."
        )
    elif not trip.can_submit_for_approval:
        submit_disabled_reason = "This trip is already waiting for approval."

    approve_label = "Add approval" if trip.status == TripStatus.APPROVED else "Approve"
    approve_disabled_reason = None
    if trip.is_terminal:
        approve_disabled_reason = (
            f"This trip is already {closed_state} and cannot be approved."
        )
    elif trip.status not in {TripStatus.SUBMITTED, TripStatus.APPROVED}:
        approve_disabled_reason = (
            "Only submitted or approved trips can receive approvals."
        )
    elif trip.trip_leader_id == user.pk:
        approve_disabled_reason = "The trip leader cannot approve this trip."
    elif not user_can_approve_trip(trip, user):
        approve_disabled_reason = (
            "You have already approved this trip in the current round."
        )

    cancel_disabled_reason = None
    close_disabled_reason = None
    if trip.is_terminal:
        cancel_disabled_reason = (
            f"This trip is already {closed_state} and cannot be cancelled."
        )
        close_disabled_reason = (
            f"This trip is already {closed_state} and cannot be closed again."
        )

    return {
        "submit_enabled": submit_disabled_reason is None,
        "submit_disabled_reason": submit_disabled_reason,
        "approve_enabled": approve_disabled_reason is None,
        "approve_disabled_reason": approve_disabled_reason,
        "approve_label": approve_label,
        "cancel_enabled": cancel_disabled_reason is None,
        "cancel_disabled_reason": cancel_disabled_reason,
        "close_enabled": close_disabled_reason is None,
        "close_disabled_reason": close_disabled_reason,
    }


def _trip_approval_summary(trip: Trip) -> dict[str, object]:
    current_approvals = list(trip.current_approvals().select_related("approver"))
    return {
        "submitted_by": trip.submitted_by,
        "submitted_at": trip.submitted_at,
        "approved_at": trip.approved_at,
        "approvals": current_approvals,
        "approval_round": trip.approval_round,
    }


def _hidden_post_fields(post_data) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in post_data.items()
        if key not in {"csrfmiddlewaretoken", APPROVAL_CONFIRM_FIELD}
    ]


class TripDetailView(LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site_visits"] = self.object.site_visits.select_related(
            "site"
        ).order_by(
            F("planned_start").asc(nulls_last=True),
            "site__code",
            "id",
        )
        context["job_assignments"] = (
            SiteVisitJob.objects.filter(site_visit__trip=self.object)
            .select_related("site_visit__site", "job")
            .order_by(
                F("site_visit__planned_start").asc(nulls_last=True),
                "site_visit__site__code",
                "site_visit_id",
                "job__title",
            )
        )
        context["detail_sections"] = _trip_detail_sections(self.object, "overview")
        context["detail_navigation_label"] = "Trip sections"
        context["trip_action_controls"] = _trip_action_controls(
            self.object, self.request.user
        )
        context["approval_summary"] = _trip_approval_summary(self.object)
        return context


class TripHistoryView(PaginatedObjectHistoryMixin, LoginRequiredMixin, DetailView):
    model = Trip
    template_name = "trips/trip_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _trip_detail_sections(self.object, "history")
        context["detail_navigation_label"] = "Trip sections"
        context["trip_action_controls"] = _trip_action_controls(
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
        context["detail_sections"] = _site_visit_detail_sections(
            self.object, "overview"
        )
        context["detail_navigation_label"] = "Site visit sections"
        return context


class SiteVisitHistoryView(PaginatedObjectHistoryMixin, LoginRequiredMixin, DetailView):
    model = SiteVisit
    template_name = "trips/site_visit_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _site_visit_detail_sections(self.object, "history")
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
    template_name = "object_form.html"
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
    template_name = "object_form.html"
    approval_reset_reason = "Returned to submitted after site visit update"

    def get_approval_trip(self):
        return self.object.trip


@require_POST
@login_required
def assign_job(request, pk):
    site_visit = get_object_or_404(SiteVisit, pk=pk)
    form = AssignJobForm(request.POST, site=site_visit.site)
    if (
        request.method == "POST"
        and site_visit.trip.status == TripStatus.APPROVED
        and request.POST.get(APPROVAL_CONFIRM_FIELD) != "1"
    ):
        return render(
            request,
            "trips/trip_approval_confirm.html",
            {
                "trip": site_visit.trip,
                "title": "Confirm trip approval reset",
                "message": APPROVAL_RESET_MESSAGE,
                "submit_label": "Assign job",
                "cancel_url": site_visit.get_absolute_url(),
                "hidden_fields": _hidden_post_fields(request.POST),
                "confirm_field_name": APPROVAL_CONFIRM_FIELD,
            },
        )
    if form.is_valid():
        job = form.cleaned_data["job"]
        try:
            with transaction.atomic():
                assign_job_to_site_visit(site_visit, job)
                invalidate_trip_approval(
                    site_visit.trip,
                    request.user,
                    "Returned to submitted after job assignment change",
                )
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
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
    if (
        request.method == "POST"
        and site_visit.trip.status == TripStatus.APPROVED
        and request.POST.get(APPROVAL_CONFIRM_FIELD) != "1"
    ):
        return render(
            request,
            "trips/trip_approval_confirm.html",
            {
                "trip": site_visit.trip,
                "title": "Confirm trip approval reset",
                "message": APPROVAL_RESET_MESSAGE,
                "submit_label": "Unassign job",
                "cancel_url": site_visit.get_absolute_url(),
                "hidden_fields": [],
                "confirm_field_name": APPROVAL_CONFIRM_FIELD,
            },
        )
    with transaction.atomic():
        unassign_site_visit_job(assignment)
        invalidate_trip_approval(
            site_visit.trip,
            request.user,
            "Returned to submitted after job assignment change",
        )
    messages.success(request, f"Unassigned job: {job.title}")
    return redirect(site_visit)


@require_POST
@login_required
def submit_trip_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    try:
        submit_trip_for_approval(trip, request.user)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, f"Submitted trip for approval: {trip.name}")
    return redirect(request.POST.get("next") or trip)


@require_POST
@login_required
def approve_trip_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    was_approved = trip.status == TripStatus.APPROVED
    try:
        approve_trip(trip, request.user)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        label = "Added approval to" if was_approved else "Approved"
        messages.success(request, f"{label} trip: {trip.name}")
    return redirect(request.POST.get("next") or trip)


@login_required
def close_trip_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    if trip.is_terminal:
        messages.info(
            request, "This trip is already closed and cannot be closed again."
        )
        return redirect(trip)
    form = TripCloseoutForm(request.POST or None, trip=trip)
    if request.method == "POST" and form.is_valid():
        close_trip(trip, form.cleaned_data)
        messages.success(request, f"Closed trip: {trip.name}")
        return redirect(trip)
    return render(request, "trips/trip_closeout.html", {"trip": trip, "form": form})


@login_required
def cancel_trip_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    if trip.is_terminal:
        messages.info(
            request,
            "This trip is already closed and cannot be cancelled.",
        )
        return redirect(trip)
    summary = get_trip_cancel_summary(trip)
    if request.method == "POST":
        try:
            cancel_trip(trip)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, f"Cancelled trip: {trip.name}")
        return redirect(trip)
    return render(
        request,
        "trips/trip_cancel.html",
        {"trip": trip, "summary": summary},
    )
