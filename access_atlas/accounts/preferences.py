from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from .models import User, UserPreference

JOBS_MAP_PREFERENCE_KEY = "jobs.map"
MAP_BASEMAP_PREFERENCE_KEY = "maps.basemap"
SITES_MAP_PREFERENCE_KEY = "sites.map"
UI_THEME_PREFERENCE_KEY = "ui.theme"
SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX = "sites.map."
LIST_SORT_PREFERENCE_KEY_PREFIX = "lists.sort."
LIST_FILTER_PREFERENCE_KEY_PREFIX = "lists.filters."
MAX_PREFERENCE_KEY_LENGTH = 120

ALLOWED_PREFERENCE_KEYS = {
    JOBS_MAP_PREFERENCE_KEY,
    MAP_BASEMAP_PREFERENCE_KEY,
    SITES_MAP_PREFERENCE_KEY,
    UI_THEME_PREFERENCE_KEY,
}
ALLOWED_LIST_SORT_PREFERENCE_PAGES = {
    "sites",
    "trips",
    "jobs",
    "job-templates",
    "work-programmes",
    "access-records",
    "history",
}
ALLOWED_LIST_FILTER_PREFERENCE_PAGES = {
    "access-records",
    "history",
    "job-templates",
    "jobs",
    "sites",
    "trips",
    "work-programmes",
}
ALLOWED_THEME_MODES = {"system", "light", "dark"}
BASEMAP_LAYER_CARTO_DARK = "carto-dark"
BASEMAP_LAYER_CARTO_VOYAGER = "carto-voyager"
BASEMAP_LAYER_ESRI_IMAGERY_STREETS = "esri-imagery-streets"
BASEMAP_LAYER_ESRI_WORLD_IMAGERY = "esri-world-imagery"
BASEMAP_LAYER_OSM_STANDARD = "osm-standard"
BASEMAP_LAYER_TRACESTRACK_TOPO = "tracestrack-topo"
ALLOWED_BASEMAP_LAYER_IDS = {
    BASEMAP_LAYER_CARTO_DARK,
    BASEMAP_LAYER_CARTO_VOYAGER,
    BASEMAP_LAYER_ESRI_IMAGERY_STREETS,
    BASEMAP_LAYER_ESRI_WORLD_IMAGERY,
    BASEMAP_LAYER_OSM_STANDARD,
    BASEMAP_LAYER_TRACESTRACK_TOPO,
}
MIN_MAP_VIEWPORT_LONGITUDE = -540
MAX_MAP_VIEWPORT_LONGITUDE = 540


def default_jobs_map_preference() -> dict[str, Any]:
    return {}


def default_sites_map_preference() -> dict[str, Any]:
    return {}


def default_map_basemap_preference() -> dict[str, Any]:
    return {"light": "carto-voyager", "dark": "carto-dark"}


def default_theme_preference() -> dict[str, Any]:
    return {"mode": "system"}


def site_access_map_preference_key(site_id: int) -> str:
    return f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}{site_id}"


def list_sort_preference_key(page_key: str) -> str:
    return f"{LIST_SORT_PREFERENCE_KEY_PREFIX}{page_key}"


def list_filter_preference_key(page_key: str) -> str:
    return f"{LIST_FILTER_PREFERENCE_KEY_PREFIX}{page_key}"


def is_allowed_preference_key(key: str) -> bool:
    if key in ALLOWED_PREFERENCE_KEYS:
        return True
    if key.startswith(LIST_SORT_PREFERENCE_KEY_PREFIX):
        page_key = key.removeprefix(LIST_SORT_PREFERENCE_KEY_PREFIX)
        return page_key in ALLOWED_LIST_SORT_PREFERENCE_PAGES
    if key.startswith(LIST_FILTER_PREFERENCE_KEY_PREFIX):
        page_key = key.removeprefix(LIST_FILTER_PREFERENCE_KEY_PREFIX)
        return page_key in ALLOWED_LIST_FILTER_PREFERENCE_PAGES
    if not key.startswith(SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX):
        return False
    site_id = key.removeprefix(SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX)
    return site_id.isdigit()


def is_valid_viewport_longitude(value: object) -> bool:
    """Allow Leaflet world-copy longitudes while rejecting unbounded input."""
    return (
        isinstance(value, int | float)
        and MIN_MAP_VIEWPORT_LONGITUDE <= value <= MAX_MAP_VIEWPORT_LONGITUDE
    )


def validate_preference(key: str, value: object) -> dict[str, Any]:
    # Preferences are intentionally schema-validated here so the rest of the
    # app can treat saved view state as trusted input instead of re-checking
    # every payload at read time.
    if not is_allowed_preference_key(key):
        raise ValidationError("Unknown preference key.")
    if not isinstance(value, dict):
        raise ValidationError("Preference value must be an object.")

    if key == JOBS_MAP_PREFERENCE_KEY:
        cleaned_value: dict[str, Any] = {}

        viewport = value.get("viewport")
        if viewport is not None:
            if not isinstance(viewport, dict):
                raise ValidationError("viewport must be an object.")
            latitude = viewport.get("lat")
            longitude = viewport.get("lng")
            zoom = viewport.get("zoom")
            if not isinstance(latitude, int | float) or not -90 <= latitude <= 90:
                raise ValidationError("viewport lat is invalid.")
            if not is_valid_viewport_longitude(longitude):
                raise ValidationError("viewport lng is invalid.")
            if not isinstance(zoom, int) or not 0 <= zoom <= 22:
                raise ValidationError("viewport zoom is invalid.")
            cleaned_value["viewport"] = {
                "lat": latitude,
                "lng": longitude,
                "zoom": zoom,
            }

        return cleaned_value

    if key == SITES_MAP_PREFERENCE_KEY:
        viewport = value.get("viewport")
        cleaned_value: dict[str, Any] = {}
        if viewport is not None:
            if not isinstance(viewport, dict):
                raise ValidationError("viewport must be an object.")
            latitude = viewport.get("lat")
            longitude = viewport.get("lng")
            zoom = viewport.get("zoom")
            if not isinstance(latitude, int | float) or not -90 <= latitude <= 90:
                raise ValidationError("viewport lat is invalid.")
            if not is_valid_viewport_longitude(longitude):
                raise ValidationError("viewport lng is invalid.")
            if not isinstance(zoom, int) or not 0 <= zoom <= 22:
                raise ValidationError("viewport zoom is invalid.")
            cleaned_value["viewport"] = {
                "lat": latitude,
                "lng": longitude,
                "zoom": zoom,
            }
        return cleaned_value

    if key == MAP_BASEMAP_PREFERENCE_KEY:
        cleaned_value = default_map_basemap_preference()
        for theme in ("light", "dark"):
            layer_id = value.get(theme)
            if layer_id is None:
                continue
            if (
                not isinstance(layer_id, str)
                or layer_id not in ALLOWED_BASEMAP_LAYER_IDS
            ):
                raise ValidationError(f"{theme} basemap layer is invalid.")
            cleaned_value[theme] = layer_id
        return cleaned_value

    if key == UI_THEME_PREFERENCE_KEY:
        mode = value.get("mode")
        if not isinstance(mode, str) or mode not in ALLOWED_THEME_MODES:
            raise ValidationError("mode must be system, light, or dark.")
        return {"mode": mode}

    if key.startswith(LIST_SORT_PREFERENCE_KEY_PREFIX):
        sort_value = value.get("value")
        if not isinstance(sort_value, str) or not sort_value.strip():
            raise ValidationError("value must be a non-empty string.")
        return {"value": sort_value.strip()}

    if key.startswith(LIST_FILTER_PREFERENCE_KEY_PREFIX):
        params = value.get("params")
        if not isinstance(params, dict):
            raise ValidationError("params must be an object.")
        cleaned_params: dict[str, list[str]] = {}
        for param_name, param_values in params.items():
            if not isinstance(param_name, str) or not param_name.strip():
                raise ValidationError("params contains an invalid parameter name.")
            if len(param_name) > 80:
                raise ValidationError(
                    "params contains a parameter name that is too long."
                )
            if not isinstance(param_values, list):
                raise ValidationError("params values must be lists.")
            cleaned_values: list[str] = []
            for param_value in param_values:
                if not isinstance(param_value, str):
                    raise ValidationError("params values must be strings.")
                cleaned_value = param_value.strip()
                if len(cleaned_value) > 500:
                    raise ValidationError("params contains a value that is too long.")
                if cleaned_value and cleaned_value not in cleaned_values:
                    cleaned_values.append(cleaned_value)
            if cleaned_values:
                cleaned_params[param_name.strip()] = cleaned_values
        return {"params": cleaned_params}

    if key.startswith(SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX):
        visible_record_ids = value.get("visible_record_ids")
        if not isinstance(visible_record_ids, list):
            raise ValidationError("visible_record_ids must be a list.")
        cleaned_ids: list[int] = []
        for record_id in visible_record_ids:
            if not isinstance(record_id, int) or record_id <= 0:
                raise ValidationError(
                    "visible_record_ids contains an invalid record id."
                )
            if record_id not in cleaned_ids:
                cleaned_ids.append(record_id)
        cleaned_value = {"visible_record_ids": cleaned_ids}
        animate_tracks = value.get("animate_tracks")
        if animate_tracks is not None:
            if not isinstance(animate_tracks, bool):
                raise ValidationError("animate_tracks must be a boolean.")
            cleaned_value["animate_tracks"] = animate_tracks
        return cleaned_value

    raise ValidationError("Unknown preference key.")


def get_user_preference(
    user: User,
    key: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Invalid persisted values should degrade to defaults rather than breaking
    # page rendering. Validation happens on writes, but reads still stay
    # defensive because preferences are user-controlled state.
    try:
        preference = user.preferences.get(key=key)
    except UserPreference.DoesNotExist:
        return default or {}
    if not isinstance(preference.value, dict):
        return default or {}
    return preference.value


def set_user_preference(user: User, key: str, value: object) -> UserPreference:
    cleaned_value = validate_preference(key, value)
    preference, _created = UserPreference.objects.update_or_create(
        user=user,
        key=key[:MAX_PREFERENCE_KEY_LENGTH],
        defaults={"value": cleaned_value},
    )
    return preference
