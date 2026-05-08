from __future__ import annotations

STATUS_BADGE_CLASSES = {
    "active": "bg-blue-lt",
    "cancelled": "bg-red-lt",
    "completed": "bg-green-lt",
    "draft": "bg-secondary-lt",
    "submitted": "bg-orange-lt",
    "approved": "bg-blue-lt",
    "assigned": "bg-blue-lt",
    "retired": "bg-yellow-lt",
    "skipped": "bg-yellow-lt",
    "stale": "bg-secondary-lt",
    "unassigned": "bg-secondary-lt",
}

STATUS_FILTER_COLORS = {
    "bg-blue-lt": "var(--tblr-blue)",
    "bg-green-lt": "var(--tblr-green)",
    "bg-orange-lt": "var(--tblr-orange)",
    "bg-red-lt": "var(--tblr-red)",
    "bg-secondary-lt": "var(--tblr-secondary)",
    "bg-yellow-lt": "var(--tblr-yellow)",
}


def status_badge_class_for_value(value: object) -> str:
    return STATUS_BADGE_CLASSES.get(str(value), "bg-secondary-lt")


def status_filter_choice_attributes(value: str) -> dict[str, str]:
    """Expose the table status hue to TomSelect filter choices."""

    color = STATUS_FILTER_COLORS.get(status_badge_class_for_value(value))
    return {"color": color} if color else {}
