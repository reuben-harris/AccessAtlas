from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from access_atlas.jobs.models import JobStatus

from .models import User, UserPreference

JOBS_MAP_PREFERENCE_KEY = "jobs.map"
UI_THEME_PREFERENCE_KEY = "ui.theme"
MAX_PREFERENCE_KEY_LENGTH = 120

ALLOWED_PREFERENCE_KEYS = {JOBS_MAP_PREFERENCE_KEY, UI_THEME_PREFERENCE_KEY}
ALLOWED_JOB_STATUSES = set(JobStatus.values)
ALLOWED_THEME_MODES = {"system", "light", "dark"}


def default_jobs_map_preference() -> dict[str, Any]:
    return {"visible_statuses": [JobStatus.UNASSIGNED, JobStatus.PLANNED]}


def default_theme_preference() -> dict[str, Any]:
    return {"mode": "system"}


def validate_preference(key: str, value: object) -> dict[str, Any]:
    if key not in ALLOWED_PREFERENCE_KEYS:
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

    if key == UI_THEME_PREFERENCE_KEY:
        mode = value.get("mode")
        if not isinstance(mode, str) or mode not in ALLOWED_THEME_MODES:
            raise ValidationError("mode must be system, light, or dark.")
        return {"mode": mode}

    raise ValidationError("Unknown preference key.")


def get_user_preference(
    user: User,
    key: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
