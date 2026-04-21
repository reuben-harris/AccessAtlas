from django import template

register = template.Library()

STATUS_BADGE_CLASSES = {
    "blocked": "bg-red-lt",
    "cancelled": "bg-red-lt",
    "completed": "bg-green-lt",
    "draft": "bg-secondary-lt",
    "planned": "bg-blue-lt",
    "skipped": "bg-yellow-lt",
    "unassigned": "bg-secondary-lt",
}


@register.filter
def status_badge_class(value: object) -> str:
    return STATUS_BADGE_CLASSES.get(str(value), "bg-secondary-lt")
