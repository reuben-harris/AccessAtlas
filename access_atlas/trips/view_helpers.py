from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from access_atlas.sites.access_record_snapshots import build_access_record_snapshots
from access_atlas.sites.models import AccessRecord
from access_atlas.sites.view_helpers import build_site_access_map_data

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
            "label": "Map",
            "icon": "ti-map",
            "url": trip.get_map_url(),
            "is_active": active_section == "map",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": trip.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


def site_visit_time_label(site_visit: SiteVisit) -> str:
    if site_visit.planned_start is None:
        return "Time not set"
    start = timezone.localtime(site_visit.planned_start)
    if site_visit.planned_end is None:
        return date_format(start, "H:i")
    end = timezone.localtime(site_visit.planned_end)
    return f"{date_format(start, 'H:i')} - {date_format(end, 'H:i')}"


def build_trip_map_data(site_visits: list[SiteVisit]) -> dict[str, list[dict]]:
    """Build trip map markers plus access starts/tracks for visited sites."""

    visits = []
    group_labels = {}
    next_label = 1
    for site_visit in site_visits:
        if site_visit.planned_day and site_visit.planned_start is None:
            order_key = ("untimed-day", site_visit.planned_day.isoformat())
            order_note = "Order within day not set"
        else:
            order_key = ("visit", site_visit.pk)
            order_note = ""
        if order_key not in group_labels:
            group_labels[order_key] = str(next_label)
            next_label += 1

        visits.append(
            {
                "id": site_visit.pk,
                "url": site_visit.get_absolute_url(),
                "siteId": site_visit.site_id,
                "siteCode": site_visit.site.code,
                "siteName": site_visit.site.name,
                "siteUrl": site_visit.site.get_absolute_url(),
                "latitude": float(site_visit.site.latitude),
                "longitude": float(site_visit.site.longitude),
                "orderLabel": group_labels[order_key],
                "orderNote": order_note,
                "dateLabel": date_format(site_visit.planned_day, "j M Y")
                if site_visit.planned_day
                else "-",
                "timeLabel": site_visit_time_label(site_visit),
                "statusLabel": site_visit.get_status_display(),
            }
        )

    site_ids = {site_visit.site_id for site_visit in site_visits}
    access_records = list(
        AccessRecord.objects.filter(site_id__in=site_ids).select_related("site")
    )
    access_map_data = build_site_access_map_data(
        access_records,
        build_access_record_snapshots(access_records),
    )
    access_map_data["points"] = [
        point for point in access_map_data["points"] if point["type"] == "access_start"
    ]
    return {
        "visits": visits,
        "accessPoints": access_map_data["points"],
        "accessTracks": access_map_data["tracks"],
    }


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
