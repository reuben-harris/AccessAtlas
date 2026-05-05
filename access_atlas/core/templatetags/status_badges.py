from django import template

register = template.Library()

STATUS_BADGE_CLASSES = {
    "active": "bg-blue-lt",
    "cancelled": "bg-red-lt",
    "completed": "bg-green-lt",
    "draft": "bg-secondary-lt",
    "submitted": "bg-orange-lt",
    "approved": "bg-blue-lt",
    "assigned": "bg-blue-lt",
    "retired": "bg-yellow-lt",
    "skipped": "bg-yellow-lt",
    "stale": "bg-secondary-lt",
    "unassigned": "bg-secondary-lt",
}


@register.filter
def status_badge_class(value: object) -> str:
    return STATUS_BADGE_CLASSES.get(str(value), "bg-secondary-lt")
