from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from django.db.models import OuterRef, Subquery

from .access_records import (
    AccessRecordGeoJSONError,
    ParsedAccessRecord,
    parse_access_record_geojson,
)
from .models import AccessRecord, AccessRecordVersion


@dataclass(frozen=True)
class AccessRecordSnapshot:
    access_record: AccessRecord
    current_version: AccessRecordVersion | None
    parsed: ParsedAccessRecord | None
    parse_error: str | None


def fetch_latest_versions_by_record_id(
    access_records: Iterable[AccessRecord],
) -> dict[int, AccessRecordVersion]:
    records = list(access_records)
    record_ids = [record.pk for record in records if record.pk is not None]
    if not record_ids:
        return {}

    latest_version_subquery = (
        AccessRecordVersion.objects.filter(access_record_id=OuterRef("pk"))
        .order_by("-version_number")
        .values("pk")[:1]
    )
    latest_version_rows = AccessRecord.objects.filter(pk__in=record_ids).annotate(
        latest_version_pk=Subquery(latest_version_subquery)
    )
    latest_version_pks = [
        latest_version_pk
        for latest_version_pk in latest_version_rows.values_list(
            "latest_version_pk", flat=True
        )
        if latest_version_pk is not None
    ]
    if not latest_version_pks:
        return {}

    versions = AccessRecordVersion.objects.filter(pk__in=latest_version_pks)
    return {version.access_record_id: version for version in versions}


def build_access_record_snapshots(
    access_records: Iterable[AccessRecord],
) -> dict[int, AccessRecordSnapshot]:
    records = [record for record in access_records if record.pk is not None]
    latest_versions_by_record_id: dict[int, AccessRecordVersion | None] = {}
    records_missing_prefetched_versions = []
    for access_record in records:
        prefetched = getattr(access_record, "_prefetched_objects_cache", {})
        if "versions" not in prefetched:
            records_missing_prefetched_versions.append(access_record)
            continue

        versions = prefetched["versions"]
        if not versions:
            latest_versions_by_record_id[access_record.pk] = None
            continue
        latest_versions_by_record_id[access_record.pk] = max(
            versions,
            key=lambda version: version.version_number,
        )

    latest_versions_by_record_id.update(
        fetch_latest_versions_by_record_id(records_missing_prefetched_versions)
    )

    snapshots = {}
    for access_record in records:
        current_version = latest_versions_by_record_id.get(access_record.pk)
        parsed: ParsedAccessRecord | None = None
        parse_error: str | None = None
        if current_version is not None:
            try:
                parsed = parse_access_record_geojson(current_version.geojson)
            except AccessRecordGeoJSONError:
                parse_error = (
                    "Latest access record revision is invalid and could not be parsed."
                )

        snapshots[access_record.pk] = AccessRecordSnapshot(
            access_record=access_record,
            current_version=current_version,
            parsed=parsed,
            parse_error=parse_error,
        )
    return snapshots
