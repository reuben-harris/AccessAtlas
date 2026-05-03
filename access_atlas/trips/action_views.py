from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .approval import APPROVAL_CONFIRM_FIELD, APPROVAL_RESET_MESSAGE
from .forms import AssignJobForm, TripCloseoutForm
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
)


def hidden_post_fields(post_data) -> list[tuple[str, str]]:
    return [
        (key, value)
        for key, value in post_data.items()
        if key not in {"csrfmiddlewaretoken", APPROVAL_CONFIRM_FIELD}
    ]


@login_required
@require_POST
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
                "hidden_fields": hidden_post_fields(request.POST),
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


@login_required
@require_POST
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


@login_required
@require_POST
def submit_trip_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    try:
        submit_trip_for_approval(trip, request.user)
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, f"Submitted trip for approval: {trip.name}")
    return redirect(request.POST.get("next") or trip)


@login_required
@require_POST
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
