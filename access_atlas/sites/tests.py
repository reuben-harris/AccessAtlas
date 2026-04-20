from decimal import Decimal

import pytest

from access_atlas.sites.feed import SiteFeedError, sync_sites_from_payload
from access_atlas.sites.models import Site


@pytest.mark.django_db
def test_sync_sites_from_payload_creates_and_updates_sites():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Original",
                "latitude": -41.1,
                "longitude": 174.1,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.created == 1
    site = Site.objects.get(source_name="dummy", external_id="001")
    assert site.code == "AA-001"
    assert site.name == "Original"

    payload["sites"][0]["name"] = "Updated"
    result = sync_sites_from_payload(payload)

    assert result.updated == 1
    site.refresh_from_db()
    assert site.name == "Updated"


@pytest.mark.django_db
def test_sync_sites_rejects_invalid_coordinates():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Invalid",
                "latitude": -100,
                "longitude": 174.1,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.rejected == 1
    assert Site.objects.count() == 0


def test_sync_sites_rejects_unsupported_schema():
    with pytest.raises(SiteFeedError):
        sync_sites_from_payload(
            {
                "schema_version": "2.0",
                "source_name": "dummy",
                "generated_at": "2026-04-21T00:00:00Z",
                "sites": [],
            }
        )


@pytest.mark.django_db
def test_site_coordinates_are_stored_as_decimals():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Site",
                "latitude": "-41.123456",
                "longitude": "174.123456",
            }
        ],
    }

    sync_sites_from_payload(payload)

    site = Site.objects.get()
    assert site.latitude == Decimal("-41.123456")
    assert site.longitude == Decimal("174.123456")
