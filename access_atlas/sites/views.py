from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, FormView, ListView, UpdateView

from access_atlas.accounts.preferences import (
    get_user_preference,
    site_access_map_preference_key,
)

from .access_record_snapshots import build_access_record_snapshots
from .access_warnings import build_access_record_warnings, build_site_warnings
from .feed import SiteFeedError, sync_configured_site_feed
from .forms import (
    AccessRecordForm,
    AccessRecordUploadForm,
    AccessRecordVersionUploadForm,
)
from .kml import convert_geojson_to_kml_bytes
from .models import AccessRecord, AccessRecordVersion, Site
from .presentation import (
    POINT_TYPE_BADGE_CLASS,
    POINT_TYPE_DISPLAY,
    TRACK_SUITABILITY_COLOR,
    TRACK_SUITABILITY_DISPLAY,
    point_details,
    select_primary_access_start,
)
from .services import (
    create_access_record_from_upload,
    create_access_record_upload_draft,
    create_access_record_version_from_upload,
)


def _coordinates_value(latitude, longitude) -> str:
    return f"{float(latitude):.6f},{float(longitude):.6f}"


def _google_maps_search_url(latitude, longitude) -> str:
    query = urlencode({"api": 1, "query": _coordinates_value(latitude, longitude)})
    return f"https://www.google.com/maps/search/?{query}"


def _google_maps_nav_url(latitude, longitude) -> str:
    query = urlencode(
        {"api": 1, "destination": _coordinates_value(latitude, longitude)}
    )
    return f"https://www.google.com/maps/dir/?{query}"


def build_site_access_map_data(
    access_records: list[AccessRecord],
    snapshots_by_record_id,
) -> dict[str, list[dict]]:
    points = []
    tracks = []
    for access_record in access_records:
        snapshot = snapshots_by_record_id.get(access_record.pk)
        if snapshot is None or snapshot.current_version is None:
            continue
        if snapshot.parse_error or snapshot.parsed is None:
            continue
        for point in snapshot.parsed.points:
            points.append(
                {
                    "recordId": access_record.pk,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "type": point.feature_type,
                    "arrivalMethod": access_record.arrival_method,
                    "typeLabel": POINT_TYPE_DISPLAY.get(
                        point.feature_type, point.feature_type
                    ),
                    "recordName": access_record.name,
                    "label": point.label or POINT_TYPE_DISPLAY.get(point.feature_type),
                    "details": point_details(point),
                }
            )
        for track in snapshot.parsed.tracks:
            tracks.append(
                {
                    "recordId": access_record.pk,
                    "label": track.label or "Track",
                    "suitability": TRACK_SUITABILITY_DISPLAY.get(
                        track.suitability, track.suitability
                    )
                    if track.suitability
                    else None,
                    "color": TRACK_SUITABILITY_COLOR.get(track.suitability, "#667382"),
                    "path": [
                        {"latitude": latitude, "longitude": longitude}
                        for longitude, latitude in track.coordinates
                    ],
                }
            )
    return {"points": points, "tracks": tracks}


class SiteListView(LoginRequiredMixin, ListView):
    model = Site
    paginate_by = 50
    template_name = "sites/site_list.html"

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records__versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warning_site_ids = set()
        for site in context["object_list"]:
            access_records = list(site.access_records.all())
            snapshots_by_record_id = build_access_record_snapshots(access_records)
            if build_site_warnings(site, snapshots_by_record_id=snapshots_by_record_id):
                warning_site_ids.add(site.pk)
        context["warning_site_ids"] = warning_site_ids
        return context


def _site_detail_sections(
    site: Site, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": site.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "Access Records",
            "icon": "ti-route-2",
            "url": site.get_access_records_url(),
            "is_active": active_section == "access-records",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": site.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


class SiteDetailContextMixin:
    model = Site

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records__versions")

    def _site_detail_data(self) -> dict:
        if hasattr(self, "_cached_site_detail_data"):
            return self._cached_site_detail_data

        access_records = list(self.object.access_records.all())
        snapshots_by_record_id = build_access_record_snapshots(access_records)
        site_search_url = _google_maps_search_url(
            self.object.latitude, self.object.longitude
        )
        for access_record in access_records:
            snapshot = snapshots_by_record_id.get(access_record.pk)
            access_record.latest_version = (
                snapshot.current_version if snapshot is not None else None
            )
            if snapshot is not None and snapshot.parsed is not None:
                access_start = select_primary_access_start(snapshot.parsed.points)
            else:
                access_start = select_primary_access_start([])
            if access_start.primary is not None:
                primary_point = access_start.primary
                access_record.access_start_search_url = _google_maps_search_url(
                    primary_point.latitude,
                    primary_point.longitude,
                )
                access_record.access_start_nav_url = _google_maps_nav_url(
                    primary_point.latitude,
                    primary_point.longitude,
                )
                access_record.access_start_available = True
            else:
                access_record.access_start_search_url = None
                access_record.access_start_nav_url = None
                access_record.access_start_available = False
        self._cached_site_detail_data = {
            "site_access_records": access_records,
            "access_warnings": build_site_warnings(
                self.object,
                snapshots_by_record_id=snapshots_by_record_id,
            ),
            "site_search_url": site_search_url,
            "snapshots_by_record_id": snapshots_by_record_id,
        }
        return self._cached_site_detail_data

    def _site_access_records_context(self) -> dict:
        data = self._site_detail_data()
        access_records = data["site_access_records"]
        preference_key = site_access_map_preference_key(self.object.pk)
        default_record_ids = [record.pk for record in access_records]
        map_preference = get_user_preference(
            self.request.user,
            preference_key,
            {"visible_record_ids": default_record_ids, "animate_tracks": True},
        )
        if "animate_tracks" not in map_preference:
            map_preference["animate_tracks"] = True
        return {
            "site_access_map_data": build_site_access_map_data(
                access_records,
                data["snapshots_by_record_id"],
            ),
            "site_access_map_preference": {
                "key": preference_key,
                "value": map_preference,
            },
            "map_tile_layer": {
                "light": {
                    "url": settings.MAP_TILE_URL,
                    "attribution": settings.MAP_TILE_ATTRIBUTION,
                },
                "dark": {
                    "url": settings.MAP_TILE_DARK_URL,
                    "attribution": settings.MAP_TILE_DARK_ATTRIBUTION,
                },
                "maxZoom": settings.MAP_TILE_MAX_ZOOM,
            },
        }

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        raise NotImplementedError

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = self.get_detail_sections()
        context["detail_navigation_label"] = "Site sections"
        return context


class SiteDetailView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_detail.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return _site_detail_sections(self.object, "overview")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        return context


class SiteAccessRecordsView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_access_records.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return _site_detail_sections(self.object, "access-records")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self._site_detail_data())
        context.update(self._site_access_records_context())
        return context


class SiteHistoryView(SiteDetailContextMixin, LoginRequiredMixin, DetailView):
    template_name = "sites/site_history.html"

    def get_detail_sections(self) -> list[dict[str, str | bool]]:
        return _site_detail_sections(self.object, "history")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["history_records"] = self.object.history.all()
        return context


def _access_record_detail_sections(
    access_record: AccessRecord, active_section: str
) -> list[dict[str, str | bool]]:
    return [
        {
            "label": "Overview",
            "icon": "ti-layout-dashboard",
            "url": access_record.get_absolute_url(),
            "is_active": active_section == "overview",
        },
        {
            "label": "Revisions",
            "icon": "ti-versions",
            "url": access_record.get_revisions_url(),
            "is_active": active_section == "revisions",
        },
        {
            "label": "History",
            "icon": "ti-history",
            "url": access_record.get_history_url(),
            "is_active": active_section == "history",
        },
    ]


class AccessRecordCreateView(LoginRequiredMixin, FormView):
    form_class = AccessRecordUploadForm
    template_name = "sites/access_record_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.site = get_object_or_404(Site, pk=kwargs["site_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["site"] = self.site
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        create_access_record_from_upload(
            site=self.site,
            user=self.request.user,
            name=form.cleaned_data["name"],
            arrival_method=form.cleaned_data["arrival_method"],
            geojson=form.cleaned_data["geojson"],
            change_note=form.cleaned_data["change_note"],
        )
        if form.staged_upload is not None:
            form.staged_upload.delete()
        if form.replaced_staged_upload is not None:
            form.replaced_staged_upload.delete()
        messages.success(self.request, "Access record uploaded.")
        return redirect(self.site.get_access_records_url())

    def form_invalid(self, form):
        self._stage_uploaded_geojson(form)
        return super().form_invalid(form)

    def _stage_uploaded_geojson(self, form):
        if form.staged_upload is not None or "geojson" not in form.cleaned_data:
            return
        form.staged_upload = create_access_record_upload_draft(
            user=self.request.user,
            site=self.site,
            geojson=form.cleaned_data["geojson"],
            file_name=form.cleaned_data["geojson_file_name"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.site
        context["form_title"] = "New access record"
        context["cancel_url"] = self.site.get_access_records_url()
        return context


class AccessRecordDetailView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_detail.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        snapshot = build_access_record_snapshots([self.object]).get(self.object.pk)
        context["access_warnings"] = build_access_record_warnings(
            self.object,
            snapshot=snapshot,
        )
        context["access_feature_rows"] = []
        context["access_feature_count"] = 0
        context["access_parse_error"] = None
        context["current_version"] = snapshot.current_version if snapshot else None
        if snapshot and snapshot.current_version:
            if snapshot.parse_error:
                context["access_parse_error"] = (
                    "Latest revision could not be parsed for feature summary."
                )
            elif snapshot.parsed is not None:
                feature_rows = []
                for point in snapshot.parsed.points:
                    details = point_details(point) or "-"
                    feature_rows.append(
                        {
                            "type_display": POINT_TYPE_DISPLAY.get(
                                point.feature_type, point.feature_type
                            ),
                            "type_badge_class": POINT_TYPE_BADGE_CLASS.get(
                                point.feature_type, "bg-secondary-lt"
                            ),
                            "label": point.label or "-",
                            "coordinates": (
                                f"{point.latitude:.6f}, {point.longitude:.6f}"
                            ),
                            "details": details,
                        }
                    )
                for track in snapshot.parsed.tracks:
                    details = "-"
                    if track.suitability:
                        suitability_display = TRACK_SUITABILITY_DISPLAY.get(
                            track.suitability, track.suitability
                        )
                        details = f"Suitability: {suitability_display}"
                    feature_rows.append(
                        {
                            "type_display": "Track",
                            "type_badge_class": "bg-red-lt",
                            "label": track.label or "-",
                            "coordinates": f"{len(track.coordinates)} points",
                            "details": details,
                        }
                    )
                context["access_feature_rows"] = feature_rows
                context["access_feature_count"] = len(feature_rows)
        context["detail_sections"] = _access_record_detail_sections(
            self.object, "overview"
        )
        context["detail_navigation_label"] = "Access record sections"
        return context


class AccessRecordHistoryView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_history.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _access_record_detail_sections(
            self.object, "history"
        )
        context["detail_navigation_label"] = "Access record sections"
        context["history_records"] = self.object.history.all()
        return context


class AccessRecordRevisionsView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_revisions.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["detail_sections"] = _access_record_detail_sections(
            self.object, "revisions"
        )
        context["detail_navigation_label"] = "Access record sections"
        return context


class AccessRecordUpdateView(LoginRequiredMixin, UpdateView):
    model = AccessRecord
    form_class = AccessRecordForm
    template_name = "object_form.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site")

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_cancel_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Edit {self.object.name}"
        context["cancel_url"] = self.get_cancel_url()
        return context


class AccessRecordVersionCreateView(LoginRequiredMixin, FormView):
    form_class = AccessRecordVersionUploadForm
    template_name = "sites/access_record_upload.html"

    def dispatch(self, request, *args, **kwargs):
        self.access_record = get_object_or_404(
            AccessRecord.objects.select_related("site"),
            pk=kwargs["pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["access_record"] = self.access_record
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        create_access_record_version_from_upload(
            access_record=self.access_record,
            user=self.request.user,
            geojson=form.cleaned_data["geojson"],
            change_note=form.cleaned_data["change_note"],
        )
        if form.staged_upload is not None:
            form.staged_upload.delete()
        if form.replaced_staged_upload is not None:
            form.replaced_staged_upload.delete()
        messages.success(self.request, "Access record revision uploaded.")
        return redirect(self.access_record.site.get_absolute_url())

    def form_invalid(self, form):
        self._stage_uploaded_geojson(form)
        return super().form_invalid(form)

    def _stage_uploaded_geojson(self, form):
        if form.staged_upload is not None or "geojson" not in form.cleaned_data:
            return
        form.staged_upload = create_access_record_upload_draft(
            user=self.request.user,
            access_record=self.access_record,
            geojson=form.cleaned_data["geojson"],
            file_name=form.cleaned_data["geojson_file_name"],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["site"] = self.access_record.site
        context["access_record"] = self.access_record
        context["form_title"] = f"Upload Revision > {self.access_record.name}"
        context["cancel_url"] = self.access_record.site.get_absolute_url()
        return context


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
                },
                {
                    "external_id": "site-002",
                    "code": "AA-002",
                    "name": "Example Valley Repeater",
                    "latitude": -43.532100,
                    "longitude": 172.636200,
                },
                {
                    "external_id": "site-003",
                    "code": "AA-003",
                    "name": "Example Coastal Sensor",
                    "latitude": -45.878800,
                    "longitude": 170.502800,
                },
                {
                    "external_id": "site-004",
                    "code": "AA-004",
                    "name": "Example Alpine Landing Site",
                    "latitude": -44.125400,
                    "longitude": 169.352100,
                },
            ],
        }
    )


def readonly_site_response(*args, **kwargs):
    return HttpResponse(status=405)


def _build_access_record_download_filename(
    access_record: AccessRecord,
    version: AccessRecordVersion,
    extension: str,
) -> str:
    site_code = slugify(access_record.site.code) or f"site-{access_record.site_id}"
    record_name = slugify(access_record.name) or f"record-{access_record.pk}"
    return f"{site_code}-{record_name}-v{version.version_number}.{extension}"


@login_required
@require_GET
def access_record_geojson_download(request, pk):
    access_record = get_object_or_404(
        AccessRecord.objects.select_related("site").prefetch_related("versions"),
        pk=pk,
    )
    version = access_record.current_version
    if version is None:
        raise Http404("No access record versions available.")
    file_name = _build_access_record_download_filename(
        access_record, version, "geojson"
    )
    response = JsonResponse(version.geojson)
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@login_required
@require_GET
def access_record_version_geojson_download(request, record_pk, version_pk):
    version = get_object_or_404(
        AccessRecordVersion.objects.select_related("access_record__site"),
        pk=version_pk,
        access_record_id=record_pk,
    )
    file_name = _build_access_record_download_filename(
        version.access_record, version, "geojson"
    )
    response = JsonResponse(version.geojson)
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@login_required
@require_GET
def access_record_kml_download(request, pk):
    access_record = get_object_or_404(
        AccessRecord.objects.select_related("site").prefetch_related("versions"),
        pk=pk,
    )
    version = access_record.current_version
    if version is None:
        raise Http404("No access record versions available.")

    try:
        kml_bytes = convert_geojson_to_kml_bytes(version.geojson)
    except Exception:
        messages.error(request, "Unable to export KML from the current GeoJSON.")
        return redirect(access_record.get_absolute_url())

    file_name = _build_access_record_download_filename(access_record, version, "kml")
    response = HttpResponse(
        kml_bytes,
        content_type="application/vnd.google-earth.kml+xml",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response


@login_required
@require_GET
def access_record_version_kml_download(request, record_pk, version_pk):
    version = get_object_or_404(
        AccessRecordVersion.objects.select_related("access_record__site"),
        pk=version_pk,
        access_record_id=record_pk,
    )
    try:
        kml_bytes = convert_geojson_to_kml_bytes(version.geojson)
    except Exception:
        messages.error(request, "Unable to export KML from this GeoJSON revision.")
        return redirect(version.access_record.get_absolute_url())

    file_name = _build_access_record_download_filename(
        version.access_record, version, "kml"
    )
    response = HttpResponse(
        kml_bytes,
        content_type="application/vnd.google-earth.kml+xml",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response
