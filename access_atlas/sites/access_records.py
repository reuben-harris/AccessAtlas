from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class AccessRecordGeoJSONError(ValueError):
    pass


ACCESS_RECORD_FEATURE_TYPES = {
    "access_start",
    "site",
    "gate",
    "note",
    "track",
}
ACCESS_RECORD_POINT_TYPES = {
    "access_start",
    "site",
    "gate",
    "note",
}
TRACK_SUITABILITY_VALUES = {
    "4wd",
    "luv",
    "walking",
}


@dataclass(frozen=True)
class AccessRecordPoint:
    feature_type: str
    longitude: float
    latitude: float
    label: str
    properties: dict[str, Any]


@dataclass(frozen=True)
class AccessRecordTrack:
    coordinates: list[tuple[float, float]]
    label: str
    suitability: str | None
    properties: dict[str, Any]


@dataclass(frozen=True)
class ParsedAccessRecord:
    geojson: dict[str, Any]
    points: list[AccessRecordPoint]
    tracks: list[AccessRecordTrack]


def parse_access_record_geojson(value: object) -> ParsedAccessRecord:
    if not isinstance(value, dict):
        raise AccessRecordGeoJSONError("GeoJSON must be a JSON object.")
    if value.get("type") != "FeatureCollection":
        raise AccessRecordGeoJSONError("GeoJSON must be a FeatureCollection.")
    features = value.get("features")
    if not isinstance(features, list):
        raise AccessRecordGeoJSONError("FeatureCollection features must be a list.")

    points: list[AccessRecordPoint] = []
    tracks: list[AccessRecordTrack] = []
    for index, feature in enumerate(features, start=1):
        if not isinstance(feature, dict):
            raise AccessRecordGeoJSONError(f"Feature {index} must be an object.")
        if feature.get("type") != "Feature":
            raise AccessRecordGeoJSONError(f"Feature {index} must have type Feature.")
        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise AccessRecordGeoJSONError(
                f"Feature {index} properties must be an object."
            )
        feature_type = properties.get("access_atlas:type")
        if not isinstance(feature_type, str) or not feature_type:
            raise AccessRecordGeoJSONError(
                f"Feature {index} must define access_atlas:type."
            )
        if feature_type not in ACCESS_RECORD_FEATURE_TYPES:
            raise AccessRecordGeoJSONError(
                f"Feature {index} has unsupported access_atlas:type {feature_type!r}."
            )

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise AccessRecordGeoJSONError(
                f"Feature {index} geometry must be an object."
            )
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if feature_type in ACCESS_RECORD_POINT_TYPES:
            if geometry_type != "Point":
                raise AccessRecordGeoJSONError(
                    f"Feature {index} with type {feature_type!r} "
                    "must use Point geometry."
                )
            longitude, latitude = validate_position(coordinates, f"Feature {index}")
            points.append(
                AccessRecordPoint(
                    feature_type=feature_type,
                    longitude=longitude,
                    latitude=latitude,
                    label=get_label(properties),
                    properties=properties,
                )
            )
            continue

        if feature_type == "track":
            if geometry_type != "LineString":
                raise AccessRecordGeoJSONError(
                    f"Feature {index} with type 'track' must use LineString geometry."
                )
            track_coordinates = validate_line_string(coordinates, f"Feature {index}")
            suitability = properties.get("suitability")
            if suitability is not None:
                if (
                    not isinstance(suitability, str)
                    or suitability not in TRACK_SUITABILITY_VALUES
                ):
                    raise AccessRecordGeoJSONError(
                        f"Feature {index} has unsupported suitability {suitability!r}."
                    )
            tracks.append(
                AccessRecordTrack(
                    coordinates=track_coordinates,
                    label=get_label(properties),
                    suitability=suitability,
                    properties=properties,
                )
            )

    return ParsedAccessRecord(geojson=value, points=points, tracks=tracks)


def validate_position(value: object, context: str) -> tuple[float, float]:
    if not isinstance(value, list | tuple) or len(value) < 2:
        raise AccessRecordGeoJSONError(
            f"{context} coordinates must be [longitude, latitude]."
        )
    longitude = validate_number(value[0], f"{context} longitude")
    latitude = validate_number(value[1], f"{context} latitude")
    if not -180 <= longitude <= 180:
        raise AccessRecordGeoJSONError(
            f"{context} longitude is outside the valid range."
        )
    if not -90 <= latitude <= 90:
        raise AccessRecordGeoJSONError(
            f"{context} latitude is outside the valid range."
        )
    return longitude, latitude


def validate_line_string(value: object, context: str) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise AccessRecordGeoJSONError(
            f"{context} LineString must contain at least two positions."
        )
    return [
        validate_position(position, f"{context} position {position_index}")
        for position_index, position in enumerate(value, start=1)
    ]


def validate_number(value: object, context: str) -> float:
    if isinstance(value, bool):
        raise AccessRecordGeoJSONError(f"{context} must be a number.")
    if not isinstance(value, int | float):
        raise AccessRecordGeoJSONError(f"{context} must be a number.")
    return float(value)


def get_label(properties: dict[str, Any]) -> str:
    label = properties.get("label") or properties.get("name") or ""
    return str(label)
