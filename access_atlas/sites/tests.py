from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse

from access_atlas.accounts.models import User
from access_atlas.sites.access_records import (
    AccessRecordGeoJSONError,
    parse_access_record_geojson,
)
from access_atlas.sites.feed import SiteFeedError, sync_sites_from_payload
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordStatus,
    AccessRecordUploadDraft,
    AccessRecordVersion,
    ArrivalMethod,
    Site,
    SiteSyncStatus,
)


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
                "access_start_latitude": -41.2,
                "access_start_longitude": 174.2,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.created == 1
    site = Site.objects.get(source_name="dummy", external_id="001")
    assert site.code == "AA-001"
    assert site.name == "Original"
    assert site.access_start_latitude == Decimal("-41.2")
    assert site.access_start_longitude == Decimal("174.2")
    assert site.sync_status == SiteSyncStatus.ACTIVE
    assert site.history.first().history_change_reason == "Created from site feed"

    payload["sites"][0]["name"] = "Updated"
    result = sync_sites_from_payload(payload)

    assert result.updated == 1
    site.refresh_from_db()
    assert site.name == "Updated"
    assert site.sync_status == SiteSyncStatus.ACTIVE
    assert site.history.first().history_change_reason == "Updated from site feed"


@pytest.mark.django_db
def test_sync_sites_marks_missing_sites_stale():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "Active",
                "latitude": -41.1,
                "longitude": 174.1,
            },
            {
                "external_id": "002",
                "code": "AA-002",
                "name": "Will become stale",
                "latitude": -42.1,
                "longitude": 175.1,
            },
        ],
    }
    sync_sites_from_payload(payload)

    payload["sites"] = [payload["sites"][0]]
    result = sync_sites_from_payload(payload)

    assert result.updated == 1
    assert Site.objects.get(external_id="001").sync_status == SiteSyncStatus.ACTIVE
    stale_site = Site.objects.get(external_id="002")
    assert stale_site.sync_status == SiteSyncStatus.STALE


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
def test_site_access_start_coordinates_are_stored_as_decimals():
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
                "access_start_latitude": "-41.123456",
                "access_start_longitude": "174.123456",
            }
        ],
    }

    sync_sites_from_payload(payload)

    site = Site.objects.get()
    assert site.access_start_latitude == Decimal("-41.123456")
    assert site.access_start_longitude == Decimal("174.123456")


@pytest.mark.django_db
def test_site_list_renders_coordinates(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Site",
        latitude=-44.1,
        longitude=169.3,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="003",
        code="AA-003",
        name="Stale Site",
        latitude=-43.1,
        longitude=168.3,
        sync_status=SiteSyncStatus.STALE,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "-44.100000, 169.300000" in content
    assert "Active" in content
    assert "Stale" in content


@pytest.mark.django_db
def test_site_detail_renders_access_start_metadata(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
        access_start_latitude=-41.2,
        access_start_longitude=174.2,
    )

    response = client.get(reverse("site_detail", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Access Start Latitude" in content
    assert "-41.2" in content
    assert "Sync Status" in content
    assert "badge bg-green-lt" in content


@pytest.mark.django_db
def test_site_can_have_multiple_access_records():
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    AccessRecord.objects.create(
        site=site,
        name="Boat access",
        arrival_method=ArrivalMethod.BOAT,
    )
    AccessRecord.objects.create(
        site=site,
        name="Heli access",
        arrival_method=ArrivalMethod.HELI,
    )

    assert site.access_records.count() == 2


@pytest.mark.django_db
def test_access_record_names_are_unique_per_site():
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
    AccessRecord.objects.create(site=first_site, name="Boat access")
    AccessRecord.objects.create(site=second_site, name="Boat access")

    with pytest.raises(IntegrityError):
        AccessRecord.objects.create(site=first_site, name="Boat access")


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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
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
    first_record = AccessRecord.objects.create(site=first_site, name="Road access")
    second_record = AccessRecord.objects.create(site=second_site, name="Road access")
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


@pytest.mark.django_db
def test_site_detail_shows_access_record_actions(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(
        site=site,
        name="Boat access",
        arrival_method=ArrivalMethod.BOAT,
    )

    response = client.get(reverse("site_detail", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("access_record_create", kwargs={"site_pk": site.pk}) in content
    assert "Boat access" in content
    assert "Boat" in content
    assert access_record.get_absolute_url() in content
    assert reverse("access_record_update", kwargs={"pk": access_record.pk}) in content
    assert "ti ti-pencil" in content
    assert "Upload revision" in content
    assert (
        reverse("access_record_version_create", kwargs={"pk": access_record.pk})
        in content
    )


@pytest.mark.django_db
def test_access_record_upload_creates_record_and_first_version(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.post(
        reverse("access_record_create", kwargs={"site_pk": site.pk}),
        {
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "geojson_file": geojson_file(),
        },
    )

    assert response.status_code == 302
    access_record = AccessRecord.objects.get(site=site)
    assert access_record.name == "Boat access"
    assert access_record.arrival_method == ArrivalMethod.BOAT
    assert access_record.status == AccessRecordStatus.ACTIVE
    version = access_record.current_version
    assert version is not None
    assert version.version_number == 1
    assert version.change_note == "Initial upload"
    assert version.uploaded_by == user


@pytest.mark.django_db
def test_access_record_upload_rejects_invalid_geojson(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.post(
        reverse("access_record_create", kwargs={"site_pk": site.pk}),
        {
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "geojson_file": SimpleUploadedFile(
                "access.geojson",
                b'{"type": "Feature"}',
                content_type="application/geo+json",
            ),
        },
    )

    assert response.status_code == 200
    assert "GeoJSON must be a FeatureCollection." in response.content.decode()
    assert AccessRecord.objects.count() == 0
    assert AccessRecordUploadDraft.objects.count() == 0


@pytest.mark.django_db
def test_access_record_upload_retains_valid_geojson_when_metadata_is_invalid(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.post(
        reverse("access_record_create", kwargs={"site_pk": site.pk}),
        {
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "",
            "geojson_file": geojson_file("retained.geojson"),
        },
    )

    assert response.status_code == 200
    draft = AccessRecordUploadDraft.objects.get(site=site, user=user)
    content = response.content.decode()
    assert "GeoJSON file retained" in content
    assert "retained.geojson" in content
    assert f'name="staged_upload_id" value="{draft.pk}"' in content

    response = client.post(
        reverse("access_record_create", kwargs={"site_pk": site.pk}),
        {
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "staged_upload_id": str(draft.pk),
        },
    )

    assert response.status_code == 302
    access_record = AccessRecord.objects.get(site=site)
    assert access_record.current_version is not None
    assert access_record.current_version.change_note == "Initial upload"
    assert AccessRecordUploadDraft.objects.count() == 0


@pytest.mark.django_db
def test_access_record_version_upload_creates_next_version(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site, name="Boat access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.post(
        reverse("access_record_version_create", kwargs={"pk": access_record.pk}),
        {
            "change_note": "Updated gate",
            "geojson_file": geojson_file(),
        },
    )

    assert response.status_code == 302
    version = access_record.current_version
    assert version is not None
    assert version.version_number == 2
    assert version.change_note == "Updated gate"


@pytest.mark.django_db
def test_access_record_version_upload_retains_geojson_without_note(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site, name="Boat access")

    response = client.post(
        reverse("access_record_version_create", kwargs={"pk": access_record.pk}),
        {
            "change_note": "",
            "geojson_file": geojson_file("revision.geojson"),
        },
    )

    assert response.status_code == 200
    draft = AccessRecordUploadDraft.objects.get(access_record=access_record, user=user)
    assert "GeoJSON file retained" in response.content.decode()

    response = client.post(
        reverse("access_record_version_create", kwargs={"pk": access_record.pk}),
        {
            "change_note": "Updated gate",
            "staged_upload_id": str(draft.pk),
        },
    )

    assert response.status_code == 302
    version = access_record.current_version
    assert version is not None
    assert version.version_number == 1
    assert version.change_note == "Updated gate"
    assert AccessRecordUploadDraft.objects.count() == 0


@pytest.mark.django_db
def test_access_record_version_upload_page_uses_revision_language(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site, name="Boat access")

    response = client.get(
        reverse("access_record_version_create", kwargs={"pk": access_record.pk})
    )

    assert response.status_code == 200
    assert "Upload Revision &gt; Boat access" in response.content.decode()


@pytest.mark.django_db
def test_access_record_detail_shows_metadata_and_versions(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(
        site=site,
        name="Boat access",
        arrival_method=ArrivalMethod.BOAT,
    )
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(access_record.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Boat access" in content
    assert "Arrival Method" in content
    assert "Boat" in content
    assert "v1" in content
    assert "Initial upload" in content
    assert content.count(site.get_absolute_url()) == 1


@pytest.mark.django_db
def test_access_record_metadata_can_be_updated(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(
        site=site,
        name="Boat access",
        arrival_method=ArrivalMethod.BOAT,
    )

    response = client.post(
        reverse("access_record_update", kwargs={"pk": access_record.pk}),
        {
            "name": "Heli access",
            "arrival_method": ArrivalMethod.HELI,
            "status": AccessRecordStatus.RETIRED,
        },
    )

    assert response.status_code == 302
    access_record.refresh_from_db()
    assert access_record.name == "Heli access"
    assert access_record.arrival_method == ArrivalMethod.HELI
    assert access_record.status == AccessRecordStatus.RETIRED


def test_parse_access_record_geojson_extracts_points_and_tracks():
    parsed = parse_access_record_geojson(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [174.7603, -41.2969],
                    },
                    "properties": {
                        "access_atlas:type": "access_start",
                        "label": "Access start",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [174.7588, -41.2961],
                    },
                    "properties": {
                        "access_atlas:type": "gate",
                        "label": "Farm gate",
                        "code": "#1923",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [
                            [174.7603, -41.2969],
                            [174.7588, -41.2961],
                        ],
                    },
                    "properties": {
                        "access_atlas:type": "track",
                        "label": "Walking track",
                        "suitability": "walking",
                    },
                },
            ],
        }
    )

    assert len(parsed.points) == 2
    assert parsed.points[0].feature_type == "access_start"
    assert parsed.points[0].longitude == 174.7603
    assert parsed.points[0].latitude == -41.2969
    assert parsed.points[1].properties["code"] == "#1923"
    assert len(parsed.tracks) == 1
    assert parsed.tracks[0].coordinates == [
        (174.7603, -41.2969),
        (174.7588, -41.2961),
    ]
    assert parsed.tracks[0].suitability == "walking"


@pytest.mark.parametrize(
    ("geojson", "message"),
    [
        (
            {"type": "Feature", "features": []},
            "GeoJSON must be a FeatureCollection.",
        ),
        (
            {"type": "FeatureCollection", "features": {}},
            "FeatureCollection features must be a list.",
        ),
        (
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [1, 2]},
                        "properties": {},
                    }
                ],
            },
            "Feature 1 must define access_atlas:type.",
        ),
        (
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [1, 2]},
                        "properties": {"access_atlas:type": "unknown"},
                    }
                ],
            },
            "Feature 1 has unsupported access_atlas:type 'unknown'.",
        ),
        (
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[1, 2], [3, 4]],
                        },
                        "properties": {"access_atlas:type": "gate"},
                    }
                ],
            },
            "Feature 1 with type 'gate' must use Point geometry.",
        ),
        (
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [181, 2]},
                        "properties": {"access_atlas:type": "access_start"},
                    }
                ],
            },
            "Feature 1 longitude is outside the valid range.",
        ),
        (
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [[1, 2], [3, 4]],
                        },
                        "properties": {
                            "access_atlas:type": "track",
                            "suitability": "tractor",
                        },
                    }
                ],
            },
            "Feature 1 has unsupported suitability 'tractor'.",
        ),
    ],
)
def test_parse_access_record_geojson_rejects_invalid_data(geojson, message):
    with pytest.raises(AccessRecordGeoJSONError, match=message):
        parse_access_record_geojson(geojson)


def geojson_file(name="access.geojson"):
    return SimpleUploadedFile(
        name,
        b"""
        {
          "type": "FeatureCollection",
          "features": [
            {
              "type": "Feature",
              "geometry": {
                "type": "Point",
                "coordinates": [174.7603, -41.2969]
              },
              "properties": {
                "access_atlas:type": "access_start",
                "label": "Access start"
              }
            }
          ]
        }
        """,
        content_type="application/geo+json",
    )
