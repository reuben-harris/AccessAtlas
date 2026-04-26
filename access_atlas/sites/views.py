from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import DetailView, FormView, ListView, UpdateView

from .access_warnings import build_access_record_warnings, build_site_warnings
from .feed import SiteFeedError, sync_configured_site_feed
from .forms import (
    AccessRecordForm,
    AccessRecordUploadForm,
    AccessRecordVersionUploadForm,
)
from .kml import convert_geojson_to_kml_bytes
from .models import AccessRecord, AccessRecordVersion, Site
from .services import (
    create_access_record_from_upload,
    create_access_record_upload_draft,
    create_access_record_version_from_upload,
)


class SiteListView(LoginRequiredMixin, ListView):
    model = Site
    paginate_by = 50
    template_name = "sites/site_list.html"

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records__versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warning_site_ids = {
            site.pk
            for site in context["object_list"]
            if build_site_warnings(site)
        }
        context["warning_site_ids"] = warning_site_ids
        return context


class SiteDetailView(LoginRequiredMixin, DetailView):
    model = Site
    template_name = "sites/site_detail.html"

    def get_queryset(self):
        return Site.objects.prefetch_related("access_records")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["access_warnings"] = build_site_warnings(self.object)
        return context


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
        return redirect(self.site.get_absolute_url())

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
        context["cancel_url"] = self.site.get_absolute_url()
        return context


class AccessRecordDetailView(LoginRequiredMixin, DetailView):
    model = AccessRecord
    template_name = "sites/access_record_detail.html"

    def get_queryset(self):
        return AccessRecord.objects.select_related("site").prefetch_related("versions")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["access_warnings"] = build_access_record_warnings(self.object)
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
                    "access_start_latitude": -41.284900,
                    "access_start_longitude": 174.771900,
                },
                {
                    "external_id": "site-002",
                    "code": "AA-002",
                    "name": "Example Valley Repeater",
                    "latitude": -43.532100,
                    "longitude": 172.636200,
                    "access_start_latitude": None,
                    "access_start_longitude": None,
                },
                {
                    "external_id": "site-003",
                    "code": "AA-003",
                    "name": "Example Coastal Sensor",
                    "latitude": -45.878800,
                    "longitude": 170.502800,
                    "access_start_latitude": -45.881000,
                    "access_start_longitude": 170.499500,
                },
                {
                    "external_id": "site-004",
                    "code": "AA-004",
                    "name": "Example Alpine Landing Site",
                    "latitude": -44.125400,
                    "longitude": 169.352100,
                    "access_start_latitude": -44.127800,
                    "access_start_longitude": 169.349900,
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
