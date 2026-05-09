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
    assign_jobs_to_site_visit,
    cancel_trip,
    close_trip,
    correct_trip_closeout,
    get_trip_cancel_summary,
    invalidate_trip_approval,
    return_trip_to_draft,
    submit_trip_for_approval,
    unassign_site_visit_job,
)


def hidden_post_fields(post_data) -> list[tuple[str, str]]:
    # The approval confirmation page needs to replay the original POST without
    # duplicating CSRF tokens or the confirmation checkbox itself.
    return [
        (key, value)
        for key, values in post_data.lists()
        for value in values
        if key not in {"csrfmiddlewaretoken", APPROVAL_CONFIRM_FIELD}
    ]


@login_required
@require_POST
def assign_job(request, pk):
    site_visit = get_object_or_404(SiteVisit, pk=pk)
    if site_visit.trip.is_terminal:
        messages.info(
            request,
            "Jobs cannot be assigned to completed or cancelled trips.",
        )
        return redirect(site_visit)
    form = AssignJobForm(request.POST, site=site_visit.site)
    if (
        request.method == "POST"
        and site_visit.trip.status == TripStatus.APPROVED
        and request.POST.get(APPROVAL_CONFIRM_FIELD) != "1"
    ):
        # Assignment changes are planning changes, so approved trips must route
        # through the same explicit reset confirmation as edit forms.
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
        jobs = form.cleaned_data["jobs"]
        try:
            assigned_count = assign_jobs_to_site_visit(site_visit, jobs, request.user)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, f"Assigned {assigned_count} job(s).")
    else:
        messages.error(request, "Select one or more unassigned jobs for this site.")
    return redirect(site_visit)


@login_required
@require_POST
def unassign_job(request, pk):
    assignment = get_object_or_404(SiteVisitJob, pk=pk)
    site_visit = assignment.site_visit
    job = assignment.job
    if site_visit.trip.is_terminal:
        messages.info(
            request,
            "Jobs cannot be unassigned from completed or cancelled trips.",
        )
        return redirect(site_visit)
    if (
        request.method == "POST"
        and site_visit.trip.status == TripStatus.APPROVED
        and request.POST.get(APPROVAL_CONFIRM_FIELD) != "1"
    ):
        # Unassign follows the same reset flow as assign for consistency.
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
def return_trip_to_draft_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    if trip.status not in {TripStatus.SUBMITTED, TripStatus.APPROVED}:
        messages.info(
            request,
            "Only submitted or approved trips can be returned to draft.",
        )
        return redirect(trip)
    if request.method == "POST":
        try:
            return_trip_to_draft(trip)
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, f"Returned trip to draft: {trip.name}")
        return redirect(trip)
    return render(request, "trips/trip_return_to_draft.html", {"trip": trip})


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
        # Closeout writes to both the trip and its linked planning objects, so
        # keep the orchestration inside the service layer.
        close_trip(trip, form.cleaned_data)
        messages.success(request, f"Closed trip: {trip.name}")
        return redirect(trip)
    return render(request, "trips/trip_closeout.html", {"trip": trip, "form": form})


@login_required
def correct_trip_closeout_view(request, pk):
    trip = get_object_or_404(Trip, pk=pk)
    if trip.status != TripStatus.COMPLETED:
        messages.info(
            request,
            "Closeout correction is only available for completed trips.",
        )
        return redirect(trip)
    form = TripCloseoutForm(request.POST or None, trip=trip, correction=True)
    if request.method == "POST" and form.is_valid():
        correct_trip_closeout(trip, form.cleaned_data)
        messages.success(request, f"Corrected closeout: {trip.name}")
        return redirect(trip)
    return render(
        request,
        "trips/trip_closeout.html",
        {
            "trip": trip,
            "form": form,
            "page_title": f"Correct closeout for {trip.name}",
            "form_notice": (
                "Closeout correction updates still-linked site visits and jobs. "
                "Jobs already returned to unassigned are not available here."
            ),
            "submit_label": "Save correction",
            "submit_icon": "ti-device-floppy",
            "empty_jobs_message": "No still-linked jobs are available to correct.",
        },
    )


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
