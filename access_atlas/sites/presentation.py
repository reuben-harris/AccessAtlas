from __future__ import annotations

from dataclasses import dataclass

# Shared, user-facing labels for parsed point types.
# Keep these centralized so map popups and feature summary tables stay consistent.
POINT_TYPE_DISPLAY = {
    "access_start": "Access Start",
    "site": "Site",
    "gate": "Gate",
    "note": "Note",
}

# Shared badge classes used by summary views.
# Centralizing these avoids color/label drift across templates and views.
POINT_TYPE_BADGE_CLASS = {
    "access_start": "bg-blue-lt",
    "site": "bg-green-lt",
    "gate": "bg-yellow-lt",
    "note": "bg-purple-lt",
}

TRACK_SUITABILITY_DISPLAY = {
    "4wd": "4WD",
    "luv": "LUV",
    "walking": "Walking",
}

TRACK_SUITABILITY_COLOR = {
    "4wd": "#1a5fb4",
    "luv": "#f59f00",
    "walking": "#a51d2d",
}


@dataclass(frozen=True)
class AccessStartSelection:
    """Result of selecting a primary access-start point from a parsed revision.

    `primary` is the first access-start point when present.
    `has_multiple` flags whether more than one access-start point exists.
    """

    primary: object | None
    has_multiple: bool


def select_primary_access_start(points: list[object]) -> AccessStartSelection:
    """Pick the first access-start point and report if the revision has many.

    Access Atlas currently resolves navigation actions against the first point,
    while still warning users when multiple access-start points are present.
    """

    access_start_points = [
        point
        for point in points
        if getattr(point, "feature_type", None) == "access_start"
    ]
    if not access_start_points:
        return AccessStartSelection(primary=None, has_multiple=False)
    return AccessStartSelection(
        primary=access_start_points[0],
        has_multiple=len(access_start_points) > 1,
    )


def point_details(point: object) -> str | None:
    """Return the human-facing details line for a parsed point feature.

    Rules are intentionally shared between map popups and feature summaries.
    """

    feature_type = getattr(point, "feature_type", None)
    properties = getattr(point, "properties", {}) or {}
    if feature_type == "gate" and properties.get("code"):
        return f"Code: {properties['code']}"
    details = properties.get("details") or properties.get("notes")
    if details:
        return str(details)
    return None
