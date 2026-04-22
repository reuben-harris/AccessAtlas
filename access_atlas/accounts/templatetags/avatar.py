from __future__ import annotations

import hashlib

from django import template

register = template.Library()

AVATAR_COLORS = [
    "#206bc4",
    "#2fb344",
    "#d63939",
    "#f59f00",
    "#ae3ec9",
    "#0ca678",
    "#4263eb",
    "#e8590c",
]


def user_initials(user) -> str:
    name = (getattr(user, "display_name", "") or "").strip()
    if name:
        parts = name.split()
        if len(parts) == 1:
            return parts[0][:2].upper()
        return f"{parts[0][0]}{parts[-1][0]}".upper()

    email = (getattr(user, "email", "") or "").strip()
    if email:
        return email.split("@", 1)[0][:2].upper()

    return "?"


@register.simple_tag
def avatar_color(user) -> str:
    seed = str(getattr(user, "avatar_seed", "") or getattr(user, "email", ""))
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return AVATAR_COLORS[int(digest[:2], 16) % len(AVATAR_COLORS)]


@register.simple_tag
def avatar_initials(user) -> str:
    return user_initials(user)
