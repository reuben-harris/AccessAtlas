from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .access_records import AccessRecordGeoJSONError, parse_access_record_geojson
from .models import AccessRecord, Site

COORDINATE_TOLERANCE = 1e-5


@dataclass(frozen=True)
class AccessWarning:
    message: str


def build_site_warnings(site: Site) -> list[AccessWarning]:
    warnings: list[AccessWarning] = []
    if _is_missing_coordinate(site.access_start_latitude, site.access_start_longitude):
        warnings.append(
            AccessWarning(
                "Source-of-truth access start coordinates are missing for this site."
            )
        )

    for access_record in site.access_records.all():
        warnings.extend(
            build_access_record_warnings(access_record, include_prefix=True)
        )
    return warnings


def build_access_record_warnings(
    access_record: AccessRecord,
    *,
    include_prefix: bool = False,
) -> list[AccessWarning]:
    warnings: list[AccessWarning] = []
    site = access_record.site
    prefix = f"{access_record.name}: " if include_prefix else ""
    current_version = access_record.current_version
    if current_version is None:
        return warnings

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

    access_start_points = [
        point for point in parsed.points if point.feature_type == "access_start"
    ]
    site_points = [point for point in parsed.points if point.feature_type == "site"]

    if access_start_points:
        access_start_point = access_start_points[0]
        if _is_missing_coordinate(
            site.access_start_latitude,
            site.access_start_longitude,
        ):
            warnings.append(
                AccessWarning(
                    f"{prefix}Access record contains an access-start point, "
                    "but source-of-truth access start coordinates are missing."
                )
            )
        elif not _coordinates_match(
            site.access_start_latitude,
            site.access_start_longitude,
            access_start_point.latitude,
            access_start_point.longitude,
        ):
            warnings.append(
                AccessWarning(
                    f"{prefix}Access-start coordinates differ from "
                    "source-of-truth values."
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
