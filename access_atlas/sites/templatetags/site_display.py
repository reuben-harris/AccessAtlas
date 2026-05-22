from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, format_html
from django.utils.safestring import mark_safe

from access_atlas.sites.display import SITE_CODE_PLACEHOLDER

register = template.Library()


def site_code_html(code: str | None):
    if code is None:
        return format_html('<span class="fst-italic">{}</span>', SITE_CODE_PLACEHOLDER)
    return conditional_escape(code)


@register.simple_tag
def site_code(code: str | None):
    """Render a standalone site code with the shared missing-code treatment."""

    return site_code_html(code)


@register.simple_tag
def site_label(site):
    """Render the shared site identity label as code plus name."""

    return format_html("{} - {}", site_code_html(site.code), site.name)


@register.filter
def style_missing_site_code(value):
    escaped_value = str(conditional_escape(value))
    escaped_placeholder = str(conditional_escape(SITE_CODE_PLACEHOLDER))
    styled_placeholder = f'<span class="fst-italic">{escaped_placeholder}</span>'
    return mark_safe(escaped_value.replace(escaped_placeholder, styled_placeholder))
