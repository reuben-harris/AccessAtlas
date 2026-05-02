from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .access_record_snapshots import AccessRecordSnapshot
from .access_records import AccessRecordGeoJSONError, parse_access_record_geojson
from .models import AccessRecord, AccessRecordStatus, Site
from .presentation import select_primary_access_start

COORDINATE_TOLERANCE = 1e-5


@dataclass(frozen=True)
class AccessWarning:
    message: str


def build_site_warnings(
    site: Site,
    *,
    snapshots_by_record_id: dict[int, AccessRecordSnapshot] | None = None,
) -> list[AccessWarning]:
    warnings: list[AccessWarning] = []
    for access_record in site.access_records.all():
        if access_record.status != AccessRecordStatus.ACTIVE:
            continue
        warnings.extend(
            build_access_record_warnings(
                access_record,
                include_prefix=True,
                snapshot=(
                    snapshots_by_record_id.get(access_record.pk)
                    if snapshots_by_record_id and access_record.pk is not None
                    else None
                ),
            )
        )
    return warnings


def build_access_record_warnings(
    access_record: AccessRecord,
    *,
    include_prefix: bool = False,
    snapshot: AccessRecordSnapshot | None = None,
) -> list[AccessWarning]:
    warnings: list[AccessWarning] = []
    site = access_record.site
    prefix = f"{access_record.name}: " if include_prefix else ""
    current_version = (
        snapshot.current_version if snapshot else access_record.current_version
    )
    if current_version is None:
        return warnings

    if snapshot and snapshot.parse_error:
        warnings.append(
            AccessWarning(
                f"{prefix}Latest access record revision is invalid and "
                "could not be parsed."
            )
        )
        return warnings
    if snapshot and snapshot.parsed is not None:
        parsed = snapshot.parsed
    else:
        try:
            parsed = parse_access_record_geojson(current_version.geojson)
        except AccessRecordGeoJSONError:
            warnings.append(
                AccessWarning(
                    f"{prefix}Latest access record revision is invalid and "
                    "could not be parsed."
                )
            )
            return warnings

    access_start = select_primary_access_start(parsed.points)
    site_points = [point for point in parsed.points if point.feature_type == "site"]

    if access_start.has_multiple:
        warnings.append(
            AccessWarning(
                f"{prefix}Multiple access-start points found in the latest revision. "
                "Navigation uses the first point."
            )
        )

    if site_points:
        site_point = site_points[0]
        if _is_missing_coordinate(site.latitude, site.longitude):
            warnings.append(
                AccessWarning(
                    f"{prefix}Access record contains a site point, but "
                    "source-of-truth site coordinates are missing."
                )
            )
        elif not _coordinates_match(
            site.latitude,
            site.longitude,
            site_point.latitude,
            site_point.longitude,
        ):
            warnings.append(
                AccessWarning(
                    f"{prefix}Site coordinates differ from source-of-truth values."
                )
            )

    return warnings


def _coordinates_match(
    left_latitude: Decimal | float | None,
    left_longitude: Decimal | float | None,
    right_latitude: float | None,
    right_longitude: float | None,
) -> bool:
    if _is_missing_coordinate(
        left_latitude,
        left_longitude,
    ) or _is_missing_coordinate(right_latitude, right_longitude):
        return False

    return (
        abs(float(left_latitude) - float(right_latitude)) <= COORDINATE_TOLERANCE
        and abs(float(left_longitude) - float(right_longitude)) <= COORDINATE_TOLERANCE
    )


def _is_missing_coordinate(latitude, longitude) -> bool:
    return latitude is None or longitude is None
