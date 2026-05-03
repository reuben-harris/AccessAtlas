from django.urls import reverse

from .models import SiteVisit, Trip, TripStatus
from .services import user_can_approve_trip


def trip_list_views(active_view: str) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Table",
            "icon": "ti-table",
            "url": reverse("trip_list"),
            "is_active": active_view == "table",
        },
        {
            "label": "Gantt",
            "icon": "ti-chart-bar",
            "url": reverse("trip_gantt"),
            "is_active": active_view == "gantt",
        },
    ]


def trip_detail_sections(
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


def site_visit_detail_sections(
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


def trip_action_controls(trip: Trip, user) -> dict[str, object]:
    """Build the trip action/button state that drives the overview template."""

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
        # Approvals are tracked per round. Once a user approves the current
        # round, the button should explain why they cannot approve again.
        approve_disabled_reason = "You have already approved this trip."

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


def trip_approval_summary(trip: Trip) -> dict[str, object]:
    """Return the current approval round summary for the trip overview card."""
    current_approvals = list(trip.current_approvals().select_related("approver"))
    return {
        "submitted_by": trip.submitted_by,
        "submitted_at": trip.submitted_at,
        "approved_at": trip.approved_at,
        "approvals": current_approvals,
        "approval_round": trip.approval_round,
    }
