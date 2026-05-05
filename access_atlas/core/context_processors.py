from __future__ import annotations

from django.http import HttpRequest

EXACT_NAV_ITEMS = {
    "dashboard": "dashboard",
    "global_history": "history",
}

PREFIX_NAV_ITEMS = (
    ("trip_", "trips"),
    ("site_visit_", "trips"),
    ("assign_job", "trips"),
    ("unassign_job", "trips"),
    ("job_template_", "job_templates"),
    ("template_requirement_", "job_templates"),
    ("job_", "jobs"),
    ("requirement_", "jobs"),
    ("access_record_", "access_records"),
    ("site_", "sites"),
    ("sync_sites", "sites"),
)


def active_nav_item(request: HttpRequest) -> dict[str, str]:
    """Resolve the current URL name to the sidebar section it belongs to."""
    resolver_match = getattr(request, "resolver_match", None)
    url_name = getattr(resolver_match, "url_name", None)
    if not url_name:
        return {"active_nav_item": ""}

    if url_name in EXACT_NAV_ITEMS:
        return {"active_nav_item": EXACT_NAV_ITEMS[url_name]}

    for prefix, nav_item in PREFIX_NAV_ITEMS:
        if url_name.startswith(prefix):
            return {"active_nav_item": nav_item}

    return {"active_nav_item": ""}
