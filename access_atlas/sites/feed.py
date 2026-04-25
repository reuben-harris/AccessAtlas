from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone
from simple_history.utils import update_change_reason

from .models import Site, SiteSyncStatus

SUPPORTED_SCHEMA_VERSION = "1.0"


class SiteFeedError(Exception):
    pass


@dataclass(frozen=True)
class SyncResult:
    created: int = 0
    updated: int = 0
    rejected: int = 0


def fetch_site_feed(url: str, token: str) -> dict[str, Any]:
    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        raise SiteFeedError(f"Site feed returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise SiteFeedError(f"Could not fetch site feed: {exc.reason}.") from exc
    except json.JSONDecodeError as exc:
        raise SiteFeedError("Site feed did not return valid JSON.") from exc


def validate_coordinate(value: object, lower: Decimal, upper: Decimal) -> Decimal:
    try:
        coordinate = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Coordinate is not a valid decimal.") from exc
    if coordinate < lower or coordinate > upper:
        raise ValueError("Coordinate is outside the valid range.")
    return coordinate


def validate_optional_coordinate(
    value: object, lower: Decimal, upper: Decimal
) -> Decimal | None:
    if value is None or value == "":
        return None
    return validate_coordinate(value, lower, upper)


def validate_feed(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    required = {"schema_version", "source_name", "generated_at", "sites"}
    missing = required - payload.keys()
    if missing:
        raise SiteFeedError(f"Site feed missing required fields: {sorted(missing)}.")
    if payload["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        raise SiteFeedError(
            f"Unsupported site feed schema version: {payload['schema_version']}."
        )
    if not isinstance(payload["source_name"], str) or not payload["source_name"]:
        raise SiteFeedError("Site feed source_name must be a non-empty string.")
    if not isinstance(payload["sites"], list):
        raise SiteFeedError("Site feed sites must be a list.")
    return payload["source_name"], payload["sites"]


def sync_sites_from_payload(payload: dict[str, Any]) -> SyncResult:
    source_name, records = validate_feed(payload)
    now = timezone.now()
    created = 0
    updated = 0
    rejected = 0
    Site.objects.filter(source_name=source_name).update(
        sync_status=SiteSyncStatus.STALE
    )

    for record in records:
        if not isinstance(record, dict):
            rejected += 1
            continue
        required = {"external_id", "code", "name", "latitude", "longitude"}
        if required - record.keys():
            rejected += 1
            continue
        try:
            latitude = validate_coordinate(
                record["latitude"], Decimal("-90"), Decimal("90")
            )
            longitude = validate_coordinate(
                record["longitude"], Decimal("-180"), Decimal("180")
            )
            access_start_latitude = validate_optional_coordinate(
                record.get("access_start_latitude"), Decimal("-90"), Decimal("90")
            )
            access_start_longitude = validate_optional_coordinate(
                record.get("access_start_longitude"), Decimal("-180"), Decimal("180")
            )
        except ValueError:
            rejected += 1
            continue

        site, was_created = Site.objects.update_or_create(
            source_name=source_name,
            external_id=str(record["external_id"]),
            defaults={
                "code": str(record["code"]),
                "name": str(record["name"]),
                "latitude": latitude,
                "longitude": longitude,
                "access_start_latitude": access_start_latitude,
                "access_start_longitude": access_start_longitude,
                "sync_status": SiteSyncStatus.ACTIVE,
                "last_seen_at": now,
            },
        )
        if was_created:
            created += 1
            update_change_reason(site, "Created from site feed")
        else:
            updated += 1
            update_change_reason(site, "Updated from site feed")

    return SyncResult(created=created, updated=updated, rejected=rejected)


def sync_configured_site_feed() -> SyncResult:
    if not settings.SITE_FEED_URL:
        raise SiteFeedError("SITE_FEED_URL is not configured.")
    if not settings.SITE_FEED_TOKEN:
        raise SiteFeedError("SITE_FEED_TOKEN is not configured.")
    payload = fetch_site_feed(settings.SITE_FEED_URL, settings.SITE_FEED_TOKEN)
    return sync_sites_from_payload(payload)
