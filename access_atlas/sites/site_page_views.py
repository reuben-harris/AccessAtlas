from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from access_atlas.accounts.preferences import (
    SITES_MAP_PREFERENCE_KEY,
    default_sites_map_preference,
    get_user_preference,
)
from access_atlas.core.mixins import (
    PaginatedObjectHistoryMixin,
    SearchablePaginatedListMixin,
    SortableListMixin,
)

from .models import Site
from .view_helpers import (
    SiteDetailContextMixin,
    build_site_list_map_data,
    map_tile_layer,
    site_detail_sections,
    site_list_views,
    site_warning_site_ids,
)


class SiteListView(
    SortableListMixin,
    SearchablePaginatedListMixin,
    LoginRequiredMixin,
    ListView,
):
    model = Site
    template_name = "sites/site_list.html"
    search_fields = ("code", "name", "description", "external_id", "source_name")
    search_placeholder = "Search sites"
    sort_preference_page_key = "sites"
    default_sort = "code"
    sort_field_map = {
        "code": "code",
        "name": "name",
        "source": "source_name",
        "sync-status": "sync_status",
    }

    def get_queryset(self):
        queryset = Site.objects.prefetch_related("access_records__versions")
        return self.apply_sort(self.apply_search(queryset))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warning_site_ids"] = site_warning_site_ids(
            list(context["object_list"])
        )
        context["site_list_views"] = site_list_views("table")
        return context


class SiteMapView(LoginRequiredMixin, ListView):
    model = Site
    template_name = "sites/site_map.html"

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records__versions").order_by(
            "code"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sites = list(context["object_list"])
        warning_site_ids = site_warning_site_ids(sites)
        map_preference = get_user_preference(
            self.request.user,
            SITES_MAP_PREFERENCE_KEY,
            default_sites_map_preference(),
        )
        context["site_list_views"] = site_list_views("map")
        context["site_map_sites"] = build_site_list_map_data(
            sites,
            warning_site_ids,
        )
        context["site_map_preference"] = {
            "key": SITES_MAP_PREFERENCE_KEY,
            "value": map_preference,
        }
        context["map_tile_layer"] = map_tile_layer()
        return context


class SiteDetailView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_detail.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return site_detail_sections(self.object, "overview")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        return context


class SiteAccessRecordsView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_access_records.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return site_detail_sections(self.object, "access-records")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        context.update(self._site_access_records_context())
        return context


class SiteHistoryView(
    PaginatedObjectHistoryMixin,
    SiteDetailContextMixin,
    LoginRequiredMixin,
    DetailView,
):
    template_name = "sites/site_history.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return site_detail_sections(self.object, "history")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        context.update(self.get_history_context())
        return context
