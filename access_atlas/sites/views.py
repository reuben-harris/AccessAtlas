from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, ListView

from .feed import SiteFeedError, sync_configured_site_feed
from .models import Site


class SiteListView(LoginRequiredMixin, ListView):
    model = Site
    paginate_by = 50
    template_name = "sites/site_list.html"


class SiteDetailView(LoginRequiredMixin, DetailView):
    model = Site
    template_name = "sites/site_detail.html"


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


@require_GET
def dummy_site_feed(request):
    expected = f"Bearer {settings.SITE_FEED_TOKEN}"
    if not settings.SITE_FEED_TOKEN or request.headers.get("Authorization") != expected:
        return HttpResponseForbidden("Invalid bearer token.")
    return JsonResponse(
        {
            "schema_version": "1.0",
            "source_name": "dummy-sites",
            "generated_at": "2026-04-21T00:00:00Z",
            "sites": [
                {
                    "external_id": "site-001",
                    "code": "AA-001",
                    "name": "Example Ridge Station",
                    "latitude": -41.286500,
                    "longitude": 174.776200,
                    "road_end_latitude": -41.284900,
                    "road_end_longitude": 174.771900,
                    "heli_only": False,
                },
                {
                    "external_id": "site-002",
                    "code": "AA-002",
                    "name": "Example Valley Repeater",
                    "latitude": -43.532100,
                    "longitude": 172.636200,
                    "road_end_latitude": None,
                    "road_end_longitude": None,
                    "heli_only": False,
                },
                {
                    "external_id": "site-003",
                    "code": "AA-003",
                    "name": "Example Coastal Sensor",
                    "latitude": -45.878800,
                    "longitude": 170.502800,
                    "road_end_latitude": -45.881000,
                    "road_end_longitude": 170.499500,
                    "heli_only": False,
                },
                {
                    "external_id": "site-004",
                    "code": "AA-004",
                    "name": "Example Alpine Heli Site",
                    "latitude": -44.125400,
                    "longitude": 169.352100,
                    "road_end_latitude": None,
                    "road_end_longitude": None,
                    "heli_only": True,
                },
                {
                    "external_id": "site-005",
                    "code": "AA-005",
                    "name": "Example Pending Coordinates",
                    "latitude": -40.912200,
                    "longitude": 175.006700,
                    "road_end_latitude": None,
                    "road_end_longitude": None,
                    "heli_only": False,
                },
            ],
        }
    )


def readonly_site_response(*args, **kwargs):
    return HttpResponse(status=405)
