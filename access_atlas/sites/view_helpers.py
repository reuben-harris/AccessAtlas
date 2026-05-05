from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse

from access_atlas.accounts.preferences import (
    get_user_preference,
    site_access_map_preference_key,
)

from .access_record_snapshots import build_access_record_snapshots
from .access_warnings import build_site_warnings
from .models import AccessRecord, Site
from .presentation import (
    POINT_TYPE_DISPLAY,
    TRACK_SUITABILITY_COLOR,
    TRACK_SUITABILITY_DISPLAY,
    point_details,
    select_primary_access_start,
)


def coordinates_value(latitude, longitude) -> str:
    return f"{float(latitude):.6f},{float(longitude):.6f}"


def google_maps_search_url(latitude, longitude) -> str:
    query = urlencode({"api": 1, "query": coordinates_value(latitude, longitude)})
    return f"https://www.google.com/maps/search/?{query}"


def google_maps_nav_url(latitude, longitude) -> str:
    query = urlencode({"api": 1, "destination": coordinates_value(latitude, longitude)})
    return f"https://www.google.com/maps/dir/?{query}"


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


def build_site_list_map_data(
    sites: list[Site], warning_site_ids: set[int]
) -> list[dict]:
    payload: list[dict] = []
    for site in sites:
        payload.append(
            {
                "code": site.code,
                "name": site.name,
                "url": site.get_absolute_url(),
                "latitude": float(site.latitude),
                "longitude": float(site.longitude),
                "syncStatus": site.sync_status,
                "syncStatusLabel": site.get_sync_status_display(),
                "hasWarnings": site.pk in warning_site_ids,
            }
        )
    return payload


def site_list_views(active_view: str) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Table",
            "icon": "ti-table",
            "url": reverse("site_list"),
            "is_active": active_view == "table",
        },
        {
            "label": "Map",
            "icon": "ti-map",
            "url": reverse("site_map"),
            "is_active": active_view == "map",
        },
    ]


def access_record_list_views(active_view: str) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Table",
            "icon": "ti-table",
            "url": reverse("access_record_list"),
            "is_active": active_view == "table",
        },
        {
            "label": "Map",
            "icon": "ti-map",
            "url": reverse("access_record_global_map"),
            "is_active": active_view == "map",
        },
    ]


def site_detail_sections(
    site: Site, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": site.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "Access Records",
            "icon": "ti-route-2",
            "url": site.get_access_records_url(),
            "is_active": active_section == "access-records",
        },
        {
            "label": "Photos",
            "icon": "ti-photo",
            "url": site.get_photos_url(),
            "is_active": active_section == "photos",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": site.get_history_url(),
            "is_active": active_section == "history",
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


def map_tile_layer() -> dict[str, object]:
    return {
        "light": {
            "url": settings.MAP_TILE_URL,
            "attribution": settings.MAP_TILE_ATTRIBUTION,
        },
        "dark": {
            "url": settings.MAP_TILE_DARK_URL,
            "attribution": settings.MAP_TILE_DARK_ATTRIBUTION,
        },
        "maxZoom": settings.MAP_TILE_MAX_ZOOM,
    }


def site_warning_site_ids(sites: list[Site]) -> set[int]:
    # The list/map views only need a boolean warning flag per site, so compute
    # that once up front instead of repeating full warning rendering in the
    # template layer.
    warning_site_ids = set()
    for site in sites:
        access_records = list(site.access_records.all())
        snapshots_by_record_id = build_access_record_snapshots(access_records)
        if build_site_warnings(site, snapshots_by_record_id=snapshots_by_record_id):
            warning_site_ids.add(site.pk)
    return warning_site_ids


class SiteDetailContextMixin:
    model = Site

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records__versions")

    def _site_detail_data(self) -> dict:
        if hasattr(self, "_cached_site_detail_data"):
            return self._cached_site_detail_data

        # Site detail, access records, and history all need the same access
        # record snapshot/warning context. Cache it on the view instance so the
        # shared detail pages do not rebuild it multiple times per request.
        access_records = list(self.object.access_records.all())
        snapshots_by_record_id = build_access_record_snapshots(access_records)
        site_search_url = google_maps_search_url(
            self.object.latitude, self.object.longitude
        )
        for access_record in access_records:
            snapshot = snapshots_by_record_id.get(access_record.pk)
            access_record.latest_version = (
                snapshot.current_version if snapshot is not None else None
            )
            if snapshot is not None and snapshot.parsed is not None:
                access_start = select_primary_access_start(snapshot.parsed.points)
            else:
                access_start = select_primary_access_start([])
            if access_start.primary is not None:
                primary_point = access_start.primary
                access_record.access_start_search_url = google_maps_search_url(
                    primary_point.latitude,
                    primary_point.longitude,
                )
                access_record.access_start_nav_url = google_maps_nav_url(
                    primary_point.latitude,
                    primary_point.longitude,
                )
                access_record.access_start_available = True
            else:
                access_record.access_start_search_url = None
                access_record.access_start_nav_url = None
                access_record.access_start_available = False
        self._cached_site_detail_data = {
            "site_access_records": access_records,
            "access_warnings": build_site_warnings(
                self.object,
                snapshots_by_record_id=snapshots_by_record_id,
            ),
            "site_search_url": site_search_url,
            "snapshots_by_record_id": snapshots_by_record_id,
        }
        return self._cached_site_detail_data

    def _site_access_records_context(self) -> dict:
        data = self._site_detail_data()
        access_records = data["site_access_records"]
        preference_key = site_access_map_preference_key(self.object.pk)
        default_record_ids = [record.pk for record in access_records]
        # Keep a permissive default here so newly added records appear on the
        # map unless the user has explicitly hidden them before.
        map_preference = get_user_preference(
            self.request.user,
            preference_key,
            {"visible_record_ids": default_record_ids, "animate_tracks": True},
        )
        if "animate_tracks" not in map_preference:
            map_preference["animate_tracks"] = True
        return {
            "site_access_map_data": build_site_access_map_data(
                access_records,
                data["snapshots_by_record_id"],
            ),
            "site_access_map_preference": {
                "key": preference_key,
                "value": map_preference,
            },
            "map_tile_layer": map_tile_layer(),
        }

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = self.get_detail_sections()
        context["detail_navigation_label"] = "Site sections"
        return context
