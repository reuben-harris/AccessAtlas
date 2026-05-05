from __future__ import annotations

from django.db import transaction
from django.db.models import Max

from .models import AccessRecord, AccessRecordUploadDraft, AccessRecordVersion


@transaction.atomic
def create_access_record_from_upload(
    *,
    site,
    user,
    name: str,
    arrival_method: str,
    geojson: dict,
    change_note: str,
) -> AccessRecord:
    access_record = AccessRecord.objects.create(
        site=site,
        name=name,
        arrival_method=arrival_method,
    )
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson=geojson,
        change_note=change_note,
        uploaded_by=user,
    )
    return access_record


@transaction.atomic
def create_access_record_version_from_upload(
    *,
    access_record: AccessRecord,
    user,
    geojson: dict,
    change_note: str,
) -> AccessRecordVersion:
    access_record = AccessRecord.objects.select_for_update().get(pk=access_record.pk)
    current_version_number = AccessRecordVersion.objects.filter(
        access_record=access_record
    ).aggregate(max_version=Max("version_number"))["max_version"]
    next_version_number = (current_version_number or 0) + 1
    return AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=next_version_number,
        geojson=geojson,
        change_note=change_note,
        uploaded_by=user,
    )


def create_access_record_upload_draft(
    *,
    user,
    geojson: dict,
    file_name: str,
    site=None,
    access_record: AccessRecord | None = None,
) -> AccessRecordUploadDraft:
    return AccessRecordUploadDraft.objects.create(
        user=user,
        site=site,
        access_record=access_record,
        geojson=geojson,
        file_name=file_name,
    )
