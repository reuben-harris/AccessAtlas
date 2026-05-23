from django.urls import reverse

from .models import AccessRecord
from .presentation import (
    POINT_TYPE_DISPLAY,
    TRACK_SUITABILITY_COLOR,
    TRACK_SUITABILITY_DISPLAY,
    point_details,
)


def build_site_access_map_data(
    access_records: list[AccessRecord],
    snapshots_by_record_id,
) -> dict[str, list[dict]]:
    # Access map payloads are built from parsed snapshots rather than raw
    # GeoJSON so every view uses the same interpretation of points and tracks.
    points = []
    tracks = []
    for access_record in access_records:
        snapshot = snapshots_by_record_id.get(access_record.pk)
        if snapshot is None or snapshot.current_version is None:
            continue
        if snapshot.parse_error or snapshot.parsed is None:
            continue
        for point in snapshot.parsed.points:
            points.append(
                {
                    "recordId": access_record.pk,
                    "siteCode": access_record.site.code,
                    "siteName": access_record.site.name,
                    "siteUrl": access_record.site.get_absolute_url(),
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "type": point.feature_type,
                    "arrivalMethod": access_record.arrival_method,
                    "typeLabel": POINT_TYPE_DISPLAY.get(
                        point.feature_type, point.feature_type
                    ),
                    "recordName": access_record.name,
                    "label": point.label or POINT_TYPE_DISPLAY.get(point.feature_type),
                    "details": point_details(point),
                }
            )
        for track in snapshot.parsed.tracks:
            tracks.append(
                {
                    "recordId": access_record.pk,
                    "label": track.label or "Track",
                    "suitability": TRACK_SUITABILITY_DISPLAY.get(
                        track.suitability, track.suitability
                    )
                    if track.suitability
                    else None,
                    "color": TRACK_SUITABILITY_COLOR.get(track.suitability, "#667382"),
                    "path": [
                        {"latitude": latitude, "longitude": longitude}
                        for longitude, latitude in track.coordinates
                    ],
                }
            )
    return {"points": points, "tracks": tracks}


def access_record_list_views(
    active_view: str,
    query_string: str = "",
) -> list[dict[str, str | bool]]:
    suffix = f"?{query_string}" if query_string else ""
    return [
        {
            "label": "Table",
            "icon": "ti-table",
            "url": f"{reverse('access_record_list')}{suffix}",
            "is_active": active_view == "table",
        },
        {
            "label": "Map",
            "icon": "ti-map",
            "url": f"{reverse('access_record_global_map')}{suffix}",
            "is_active": active_view == "map",
        },
    ]


def access_record_detail_sections(
    access_record: AccessRecord, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": access_record.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "Map",
            "icon": "ti-map",
            "url": access_record.get_map_url(),
            "is_active": active_section == "map",
        },
        {
            "label": "Revisions",
            "icon": "ti-versions",
            "url": access_record.get_revisions_url(),
            "is_active": active_section == "revisions",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": access_record.get_history_url(),
            "is_active": active_section == "history",
        },
    ]
