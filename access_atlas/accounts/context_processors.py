from __future__ import annotations

from .preferences import (
    UI_THEME_PREFERENCE_KEY,
    default_theme_preference,
    get_user_preference,
)


def theme_preference(request):
    preference = default_theme_preference()
    if request.user.is_authenticated:
        preference = get_user_preference(
            request.user,
            UI_THEME_PREFERENCE_KEY,
            preference,
        )
    return {
        "theme_preference_key": UI_THEME_PREFERENCE_KEY,
        "theme_preference": preference,
    }
