from django import template

from access_atlas.core.status_display import status_badge_class_for_value

register = template.Library()

SITE_TAG_BADGE_COLORS = {
    "azure",
    "blue",
    "cyan",
    "green",
    "indigo",
    "lime",
    "orange",
    "pink",
    "purple",
    "red",
    "secondary",
    "teal",
    "yellow",
}


@register.filter
def status_badge_class(value: object) -> str:
    return status_badge_class_for_value(value)


@register.filter
def site_tag_badge_class(value: object) -> str:
    color = str(value or "secondary")
    if color not in SITE_TAG_BADGE_COLORS:
        color = "secondary"
    return f"bg-{color}-lt"
