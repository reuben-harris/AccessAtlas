from io import BytesIO
from zipfile import ZipFile

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import DetailView, ListView, View

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

from .forms import SitePhotoUploadForm
from .models import Site, SitePhoto
from .services import create_site_photo, group_visible_site_photos, hide_site_photo
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


class SitePhotosView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_photos.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return site_detail_sections(self.object, "photos")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = SitePhotoUploadForm(request.POST, request.FILES)
        if form.is_valid():
            for photo_file in form.cleaned_data["photos"]:
                create_site_photo(
                    site=self.object,
                    user=request.user,
                    image_file=photo_file,
                )
            messages.success(request, "Photos uploaded.")
            return redirect(self.object.get_photos_url())
        return self.render_to_response(self.get_context_data(form=form))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        visible_photos = list(
            self.object.photos.filter(hidden=False).select_related("uploaded_by")
        )
        context["form"] = kwargs.get("form") or SitePhotoUploadForm()
        context["photo_groups"] = group_visible_site_photos(visible_photos)
        context["photo_count"] = len(visible_photos)
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


class SitePhotoBulkHideView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        site = get_object_or_404(Site, pk=kwargs["pk"])
        photo_ids = request.POST.getlist("photo_ids")
        photos = SitePhoto.objects.filter(site=site, hidden=False, pk__in=photo_ids)
        hidden_count = 0
        for photo in photos:
            hide_site_photo(photo=photo, user=request.user)
            hidden_count += 1
        if hidden_count:
            noun = "photo" if hidden_count == 1 else "photos"
            messages.success(request, f"{hidden_count} {noun} hidden.")
        else:
            messages.info(request, "No photos were selected.")
        return redirect(site.get_photos_url())


class SitePhotoBulkDownloadView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        site = get_object_or_404(Site, pk=kwargs["pk"])
        photo_ids = request.POST.getlist("photo_ids")
        photos = SitePhoto.objects.filter(site=site, hidden=False, pk__in=photo_ids)
        if not photos:
            messages.info(request, "No photos were selected.")
            return redirect(site.get_photos_url())

        archive = BytesIO()
        with ZipFile(archive, "w") as zip_file:
            for photo in photos:
                with photo.image.open("rb") as image_file:
                    filename = f"{photo.pk}-{photo.image.name.split('/')[-1]}"
                    zip_file.writestr(filename, image_file.read())
        archive.seek(0)
        response = HttpResponse(archive.getvalue(), content_type="application/zip")
        response["Content-Disposition"] = (
            f'attachment; filename="{site.code}-photos.zip"'
        )
        return response
