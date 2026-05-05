from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from access_atlas.jobs.models import JobStatus

from .models import User, UserPreference

JOBS_MAP_PREFERENCE_KEY = "jobs.map"
SITES_MAP_PREFERENCE_KEY = "sites.map"
UI_THEME_PREFERENCE_KEY = "ui.theme"
SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX = "sites.map."
LIST_SORT_PREFERENCE_KEY_PREFIX = "lists.sort."
MAX_PREFERENCE_KEY_LENGTH = 120

ALLOWED_PREFERENCE_KEYS = {
    JOBS_MAP_PREFERENCE_KEY,
    SITES_MAP_PREFERENCE_KEY,
    UI_THEME_PREFERENCE_KEY,
}
ALLOWED_LIST_SORT_PREFERENCE_PAGES = {
    "sites",
    "trips",
    "jobs",
    "job-templates",
    "history",
}
ALLOWED_JOB_STATUSES = set(JobStatus.values)
ALLOWED_THEME_MODES = {"system", "light", "dark"}


def default_jobs_map_preference() -> dict[str, Any]:
    return {"visible_statuses": [JobStatus.UNASSIGNED, JobStatus.ASSIGNED]}


def default_sites_map_preference() -> dict[str, Any]:
    return {}


def default_theme_preference() -> dict[str, Any]:
    return {"mode": "system"}


def site_access_map_preference_key(site_id: int) -> str:
    return f"{SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX}{site_id}"


def list_sort_preference_key(page_key: str) -> str:
    return f"{LIST_SORT_PREFERENCE_KEY_PREFIX}{page_key}"


def is_allowed_preference_key(key: str) -> bool:
    if key in ALLOWED_PREFERENCE_KEYS:
        return True
    if key.startswith(LIST_SORT_PREFERENCE_KEY_PREFIX):
        page_key = key.removeprefix(LIST_SORT_PREFERENCE_KEY_PREFIX)
        return page_key in ALLOWED_LIST_SORT_PREFERENCE_PAGES
    if not key.startswith(SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX):
        return False
    site_id = key.removeprefix(SITE_ACCESS_MAP_PREFERENCE_KEY_PREFIX)
    return site_id.isdigit()


def validate_preference(key: str, value: object) -> dict[str, Any]:
    # Preferences are intentionally schema-validated here so the rest of the
    # app can treat saved view state as trusted input instead of re-checking
    # every payload at read time.
    if not is_allowed_preference_key(key):
        raise ValidationError("Unknown preference key.")
    if not isinstance(value, dict):
        raise ValidationError("Preference value must be an object.")

    if key == JOBS_MAP_PREFERENCE_KEY:
        visible_statuses = value.get("visible_statuses")
        if not isinstance(visible_statuses, list):
            raise ValidationError("visible_statuses must be a list.")
        cleaned_statuses = []
        for status in visible_statuses:
            if not isinstance(status, str) or status not in ALLOWED_JOB_STATUSES:
                raise ValidationError("visible_statuses contains an unknown status.")
            if status not in cleaned_statuses:
                cleaned_statuses.append(status)
        cleaned_value: dict[str, Any] = {"visible_statuses": cleaned_statuses}

        viewport = value.get("viewport")
        if viewport is not None:
            if not isinstance(viewport, dict):
                raise ValidationError("viewport must be an object.")
            latitude = viewport.get("lat")
            longitude = viewport.get("lng")
            zoom = viewport.get("zoom")
            if not isinstance(latitude, int | float) or not -90 <= latitude <= 90:
                raise ValidationError("viewport lat is invalid.")
            if not isinstance(longitude, int | float) or not -180 <= longitude <= 180:
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
            if not isinstance(longitude, int | float) or not -180 <= longitude <= 180:
                raise ValidationError("viewport lng is invalid.")
            if not isinstance(zoom, int) or not 0 <= zoom <= 22:
                raise ValidationError("viewport zoom is invalid.")
            cleaned_value["viewport"] = {
                "lat": latitude,
                "lng": longitude,
                "zoom": zoom,
            }
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
