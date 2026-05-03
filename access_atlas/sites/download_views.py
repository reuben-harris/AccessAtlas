from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from .kml import convert_geojson_to_kml_bytes
from .models import AccessRecord, AccessRecordVersion


def build_access_record_download_filename(
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
    file_name = build_access_record_download_filename(access_record, version, "geojson")
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
    file_name = build_access_record_download_filename(
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

    file_name = build_access_record_download_filename(access_record, version, "kml")
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
        messages.error(request, "Unable to export KML from the selected GeoJSON.")
        return redirect(version.access_record.get_revisions_url())

    file_name = build_access_record_download_filename(
        version.access_record, version, "kml"
    )
    response = HttpResponse(
        kml_bytes,
        content_type="application/vnd.google-earth.kml+xml",
    )
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    return response
