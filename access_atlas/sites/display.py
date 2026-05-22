from __future__ import annotations

from django.utils.text import slugify

SITE_CODE_PLACEHOLDER = "code not set"


def normalize_site_code(value: object) -> str | None:
    """Normalize externally owned site-code values before storing them."""

    if value is None:
        return None
    code = str(value).strip()
    return code or None


def display_site_code(code: str | None) -> str:
    if code is None:
        return SITE_CODE_PLACEHOLDER
    return code


def display_site_label(code: str | None, name: str) -> str:
    return f"{display_site_code(code)} - {name}"


def site_code_filename_slug(code: str | None, fallback: str) -> str:
    slug = slugify(code or "")
    return slug or fallback
