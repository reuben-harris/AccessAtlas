from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.sites.feed import SiteFeedError, sync_sites_from_payload
from access_atlas.sites.models import AccessRecord, AccessRecordVersion, Site


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
                "road_end_latitude": -41.2,
                "road_end_longitude": 174.2,
                "heli_only": False,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.created == 1
    site = Site.objects.get(source_name="dummy", external_id="001")
    assert site.code == "AA-001"
    assert site.name == "Original"
    assert site.road_end_latitude == Decimal("-41.2")
    assert site.road_end_longitude == Decimal("174.2")
    assert site.heli_only is False
    assert site.history.first().history_change_reason == "Created from site feed"

    payload["sites"][0]["name"] = "Updated"
    result = sync_sites_from_payload(payload)

    assert result.updated == 1
    site.refresh_from_db()
    assert site.name == "Updated"
    assert site.history.first().history_change_reason == "Updated from site feed"


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


@pytest.mark.django_db
def test_sync_sites_rejects_missing_site_coordinates():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Missing coordinates",
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.rejected == 1
    assert Site.objects.count() == 0


@pytest.mark.django_db
def test_sync_sites_accepts_heli_only_sites():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Heli only",
                "latitude": -44.1,
                "longitude": 169.3,
                "heli_only": True,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.created == 1
    assert Site.objects.get().heli_only is True


@pytest.mark.django_db
def test_sync_sites_rejects_invalid_heli_only_value():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Invalid heli only",
                "heli_only": "false",
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


@pytest.mark.django_db
def test_site_road_end_coordinates_are_stored_as_decimals():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Site",
                "latitude": -41.1,
                "longitude": 174.1,
                "road_end_latitude": "-41.123456",
                "road_end_longitude": "174.123456",
            }
        ],
    }

    sync_sites_from_payload(payload)

    site = Site.objects.get()
    assert site.road_end_latitude == Decimal("-41.123456")
    assert site.road_end_longitude == Decimal("174.123456")


@pytest.mark.django_db
def test_site_list_renders_coordinates(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Heli Site",
        latitude=-44.1,
        longitude=169.3,
        heli_only=True,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "-44.100000, 169.300000" in content


@pytest.mark.django_db
def test_site_detail_renders_road_end_metadata(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
        road_end_latitude=-41.2,
        road_end_longitude=174.2,
    )

    response = client.get(reverse("site_detail", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Road End Latitude" in content
    assert "-41.2" in content
    assert "Heli Only" in content


@pytest.mark.django_db
def test_site_can_have_one_access_record():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    AccessRecord.objects.create(site=site)

    with pytest.raises(IntegrityError):
        AccessRecord.objects.create(site=site)


@pytest.mark.django_db
def test_access_record_current_version_is_highest_version_number():
    user = User.objects.create_user(email="user@example.com")
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site)
    first_version = AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial upload",
        uploaded_by=user,
    )
    second_version = AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=2,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Replace record",
        uploaded_by=user,
    )

    assert access_record.current_version == second_version
    assert access_record.current_version != first_version


@pytest.mark.django_db
def test_access_record_version_numbers_are_unique_per_record():
    user = User.objects.create_user(email="user@example.com")
    first_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    second_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Other Site",
        latitude=-42.1,
        longitude=175.1,
    )
    first_record = AccessRecord.objects.create(site=first_site)
    second_record = AccessRecord.objects.create(site=second_site)
    geojson = {"type": "FeatureCollection", "features": []}
    AccessRecordVersion.objects.create(
        access_record=first_record,
        version_number=1,
        geojson=geojson,
        change_note="Initial upload",
        uploaded_by=user,
    )
    AccessRecordVersion.objects.create(
        access_record=second_record,
        version_number=1,
        geojson=geojson,
        change_note="Initial upload",
        uploaded_by=user,
    )

    with pytest.raises(IntegrityError):
        AccessRecordVersion.objects.create(
            access_record=first_record,
            version_number=1,
            geojson=geojson,
            change_note="Duplicate version",
            uploaded_by=user,
        )
