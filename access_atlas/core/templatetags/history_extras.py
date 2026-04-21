from django import template

from access_atlas.core.history import history_reason

register = template.Library()


@register.filter
def change_reason(record) -> str:
    return history_reason(record)
