from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from .feed import SiteFeedError, sync_configured_site_feed


@login_required
@require_POST
def sync_sites_view(request):
    try:
        result = sync_configured_site_feed()
    except SiteFeedError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request,
            "Site sync complete: "
            f"{result.created} created, "
            f"{result.updated} updated, "
            f"{result.rejected} rejected.",
        )
    return redirect("site_list")
