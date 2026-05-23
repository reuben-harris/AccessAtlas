from urllib.parse import urlencode

from django.urls import reverse

from access_atlas.access_records.presentation import select_primary_access_start
from access_atlas.access_records.snapshots import build_access_record_snapshots
from access_atlas.access_records.warnings import build_site_warnings

from .models import Site


def coordinates_value(latitude, longitude) -> str:
    return f"{float(latitude):.6f},{float(longitude):.6f}"


def google_maps_search_url(latitude, longitude) -> str:
    query = urlencode({"api": 1, "query": coordinates_value(latitude, longitude)})
    return f"https://www.google.com/maps/search/?{query}"


def google_maps_nav_url(latitude, longitude) -> str:
    query = urlencode({"api": 1, "destination": coordinates_value(latitude, longitude)})
    return f"https://www.google.com/maps/dir/?{query}"


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


def site_list_views(
    active_view: str,
    query_string: str = "",
) -> list[dict[str, str | bool]]:
    suffix = f"?{query_string}" if query_string else ""
    return [
        {
            "label": "Table",
            "icon": "ti-table",
            "url": f"{reverse('site_list')}{suffix}",
            "is_active": active_view == "table",
        },
        {
            "label": "Map",
            "icon": "ti-map",
            "url": f"{reverse('site_map')}{suffix}",
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

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = self.get_detail_sections()
        context["detail_navigation_label"] = "Site sections"
        return context
