from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    SITES_MAP_PREFERENCE_KEY,
    get_user_preference,
    list_filter_preference_key,
    list_sort_preference_key,
    set_user_preference,
)
from access_atlas.core.list_filters import FILTER_STATE_PARAM, FILTER_STATE_UPDATE
from access_atlas.core.test_utils import parse_json_script
from access_atlas.sites.access_records import (
    AccessRecordGeoJSONError,
    parse_access_record_geojson,
)
from access_atlas.sites.access_warnings import (
    build_access_record_warnings,
    build_site_warnings,
)
from access_atlas.sites.feed import (
    SiteFeedError,
    sync_configured_site_feed,
    sync_sites_from_payload,
)
from access_atlas.sites.forms import AccessRecordUploadForm, SitePhotoUploadForm
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordStatus,
    AccessRecordUploadDraft,
    AccessRecordVersion,
    ArrivalMethod,
    Site,
    SitePhoto,
    SiteSyncStatus,
)
from access_atlas.sites.photo_services import extract_taken_date


def test_site_display_helpers_use_missing_code_labels():
    site = Site(code="", name="NIC House Test Facility")

    assert site.display_code == "code not set"
    assert site.compact_display_code == "null"
    assert site.display_label == "code not set - NIC House Test Facility"
    assert str(site) == "code not set - NIC House Test Facility"


@pytest.mark.django_db
def test_site_list_renders_missing_code_as_clickable_compact_null(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="blank",
        code="",
        name="Blank Code Site",
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert site.get_absolute_url() in content
    assert '<span class="fst-italic">null</span>' in content
    assert 'text-secondary fst-italic">null' not in content


@pytest.mark.django_db
def test_site_map_payload_uses_missing_code_label(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="blank",
        code="",
        name="Blank Code Site",
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.get(reverse("site_map"))

    assert response.status_code == 200
    payload = parse_json_script(response.content.decode(), "site-list-map-data")
    assert payload[0]["code"] == "code not set"


@pytest.mark.django_db
def test_access_map_payload_uses_missing_site_code_label(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="blank",
        code="",
        name="Blank Code Site",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.25, -41.25]},
                    "properties": {"access_atlas:type": "access_start"},
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("access_record_global_map"))

    assert response.status_code == 200
    payload = parse_json_script(response.content.decode(), "site-access-map-data")
    assert payload["points"][0]["siteCode"] == "code not set"


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
                "description": "Original site notes",
                "tags": [
                    {"label": "Remote", "color": "orange"},
                    {"label": "No colour", "color": "invalid"},
                    {"label": ""},
                    "Legacy string tag",
                ],
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
    assert site.description == "Original site notes"
    assert site.tags == [
        {"label": "Remote", "color": "orange"},
        {"label": "No colour", "color": ""},
        {"label": "Legacy string tag", "color": ""},
    ]
    assert site.sync_status == SiteSyncStatus.ACTIVE
    assert site.history.first().history_change_reason == "Created from site feed"

    payload["sites"][0]["name"] = "Updated"
    payload["sites"][0]["description"] = "Updated site notes"
    payload["sites"][0]["tags"] = [{"label": "Road access", "color": "blue"}]
    result = sync_sites_from_payload(payload)

    assert result.updated == 1
    site.refresh_from_db()
    assert site.name == "Updated"
    assert site.description == "Updated site notes"
    assert site.tags == [{"label": "Road access", "color": "blue"}]
    assert site.sync_status == SiteSyncStatus.ACTIVE
    assert site.history.first().history_change_reason == "Updated from site feed"


@pytest.mark.django_db
def test_sync_sites_accepts_missing_description_for_schema_1():
    payload = {
        "schema_version": "1.0",
        "source_name": "dummy",
        "generated_at": "2026-04-21T00:00:00Z",
        "sites": [
            {
                "external_id": "001",
                "code": "AA-001",
                "name": "No Description",
                "latitude": -41.1,
                "longitude": 174.1,
            }
        ],
    }

    result = sync_sites_from_payload(payload)

    assert result.created == 1
    assert Site.objects.get().description == ""


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


@override_settings(SITE_FEED_URL="", SITE_FEED_TOKEN="secret")
def test_sync_configured_site_feed_requires_url():
    with pytest.raises(SiteFeedError, match="SITE_FEED_URL is not configured."):
        sync_configured_site_feed()


@override_settings(SITE_FEED_URL="https://example.com/sites.json", SITE_FEED_TOKEN="")
def test_sync_configured_site_feed_requires_token():
    with pytest.raises(SiteFeedError, match="SITE_FEED_TOKEN is not configured."):
        sync_configured_site_feed()


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
def test_site_list_renders_synced_tags(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Tagged Site",
        tags=[
            {"label": "Remote", "color": "orange"},
            {"label": "No colour", "color": ""},
        ],
        latitude=-44.1,
        longitude=169.3,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Remote" in content
    assert "No colour" in content
    assert "bg-orange-lt" in content
    assert "bg-secondary-lt" in content


@pytest.mark.django_db
def test_site_list_shows_warning_indicator_for_sites_with_access_warnings(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    warning_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Warning Site",
        latitude=-41.1,
        longitude=174.1,
    )
    ok_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="OK Site",
        latitude=-42.1,
        longitude=175.1,
    )
    warning_record = AccessRecord.objects.create(site=warning_site, name="Road access")
    AccessRecord.objects.create(site=ok_site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=warning_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.25, -41.25]},
                    "properties": {
                        "access_atlas:type": "site",
                        "label": "Warning Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'title="There are warnings for this site."' in content
    assert "warning-indicator" in content


@pytest.mark.django_db
def test_site_list_defaults_to_25_per_page(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    for index in range(30):
        Site.objects.create(
            source_name="dummy",
            external_id=f"{index:03d}",
            code=f"AA-{index:03d}",
            name=f"Site {index}",
            latitude=-41.1,
            longitude=174.1,
        )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    assert len(response.context["object_list"]) == 25
    assert response.context["paginator"].num_pages == 2
    assert response.context["per_page"] == 25


@pytest.mark.django_db
def test_site_list_invalid_per_page_falls_back_to_25(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    for index in range(30):
        Site.objects.create(
            source_name="dummy",
            external_id=f"{index:03d}",
            code=f"AA-{index:03d}",
            name=f"Site {index}",
            latitude=-41.1,
            longitude=174.1,
        )

    response = client.get(reverse("site_list"), {"per_page": "banana"})

    assert response.status_code == 200
    assert len(response.context["object_list"]) == 25
    assert response.context["per_page"] == 25


@pytest.mark.django_db
def test_site_list_search_filters_results(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="North Ridge",
        description="Only reachable from the ridge track.",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="South Valley",
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("site_list"), {"q": "track"})

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert len(object_list) == 1
    assert object_list[0].name == "North Ridge"


@pytest.mark.django_db
def test_site_list_hides_stale_sites_by_default(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="active",
        code="AA-001",
        name="Active",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="stale",
        code="AA-002",
        name="Stale",
        sync_status=SiteSyncStatus.STALE,
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [site.name for site in object_list] == ["Active"]
    chips = response.context["active_filter_chips"]
    assert any(chip["label"] == "Status is Active" for chip in chips)
    assert "sync_status=active" in response.context["filter_clear_all_url"]
    assert "sync_status=stale" in response.context["filter_clear_all_url"]


@pytest.mark.django_db
def test_site_list_can_explicitly_include_stale_sites(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="active",
        code="AA-001",
        name="Active",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="stale",
        code="AA-002",
        name="Stale",
        sync_status=SiteSyncStatus.STALE,
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(
        reverse("site_list"),
        {"sync_status": [SiteSyncStatus.ACTIVE, SiteSyncStatus.STALE]},
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [site.name for site in object_list] == ["Active", "Stale"]
    assert [chip["label"] for chip in response.context["active_filter_chips"]] == [
        "Status is all statuses"
    ]
    content = response.content.decode()
    assert 'data-filter-item-color="var(--tblr-blue)"' in content
    assert 'data-filter-item-color="var(--tblr-secondary)"' in content


@pytest.mark.django_db
def test_site_clear_all_saves_all_sync_statuses_as_filter_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(
        reverse("site_list"),
        {
            FILTER_STATE_PARAM: FILTER_STATE_UPDATE,
            "sync_status": [SiteSyncStatus.ACTIVE, SiteSyncStatus.STALE],
        },
    )

    assert response.status_code == 302
    assert response.url == (
        f"{reverse('site_list')}?sync_status=active&sync_status=stale"
    )
    assert get_user_preference(user, list_filter_preference_key("sites")) == {
        "params": {"sync_status": [SiteSyncStatus.ACTIVE, SiteSyncStatus.STALE]}
    }

    response = client.get(reverse("site_list"))

    assert response.status_code == 302
    assert response.url == (
        f"{reverse('site_list')}?sync_status=active&sync_status=stale"
    )


@pytest.mark.django_db
def test_site_list_filters_by_any_tag(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="remote",
        code="AA-001",
        name="Remote",
        tags=[{"label": "Remote", "color": "orange"}],
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="coastal",
        code="AA-002",
        name="Coastal",
        tags=[{"label": "Coastal", "color": "blue"}],
        latitude=-42.1,
        longitude=175.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="plain",
        code="AA-003",
        name="Plain",
        latitude=-43.1,
        longitude=176.1,
    )

    response = client.get(
        reverse("site_list"),
        {"tags": ["Remote", "Coastal"]},
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [site.name for site in object_list] == ["Remote", "Coastal"]


@pytest.mark.django_db
def test_site_list_sorts_by_name_and_saves_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-002",
        name="Zulu",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-001",
        name="Alpha",
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("site_list"), {"sort": "name"})

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [site.name for site in object_list] == ["Alpha", "Zulu"]
    assert get_user_preference(
        user,
        list_sort_preference_key("sites"),
    ) == {"value": "name"}


@pytest.mark.django_db
def test_site_list_links_to_map_view(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("site_list"))

    assert response.status_code == 200
    assert reverse("site_map") in response.content.decode()


@pytest.mark.django_db
def test_site_map_applies_shared_filters_and_preserves_table_link(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="active",
        code="AA-001",
        name="Active",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="stale",
        code="AA-002",
        name="Stale",
        sync_status=SiteSyncStatus.STALE,
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("site_map"), {"sync_status": SiteSyncStatus.STALE})

    assert response.status_code == 200
    site_map_sites = parse_json_script(response.content.decode(), "site-list-map-data")
    assert [site["name"] for site in site_map_sites] == ["Stale"]
    content = response.content.decode()
    assert 'id="list-filter-offcanvas"' in content
    assert "list-controls-card" not in content
    assert 'id="list-search-input"' not in content
    table_view = next(
        view for view in response.context["site_list_views"] if view["label"] == "Table"
    )
    assert table_view["url"] == f"{reverse('site_list')}?sync_status=stale"


@pytest.mark.django_db
def test_site_map_includes_sites_and_warning_state(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    warning_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Warning Site",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="OK Site",
        latitude=-42.1,
        longitude=175.1,
        sync_status=SiteSyncStatus.STALE,
    )
    warning_record = AccessRecord.objects.create(site=warning_site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=warning_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.25, -41.25]},
                    "properties": {
                        "access_atlas:type": "site",
                        "label": "Warning Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(
        reverse("site_map"),
        {"sync_status": [SiteSyncStatus.ACTIVE, SiteSyncStatus.STALE]},
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Warning Site" in content
    assert "OK Site" in content
    sites_payload = parse_json_script(content, "site-list-map-data")
    warning_payload = next(site for site in sites_payload if site["code"] == "AA-001")
    stale_payload = next(site for site in sites_payload if site["code"] == "AA-002")
    assert warning_payload["hasWarnings"] is True
    assert stale_payload["syncStatus"] == "stale"


@pytest.mark.django_db
def test_site_map_uses_saved_viewport_preference(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        description="Site description from the source system.",
        latitude=-41.1,
        longitude=174.1,
    )
    set_user_preference(
        user,
        SITES_MAP_PREFERENCE_KEY,
        {"viewport": {"lat": -40.5, "lng": 175.1, "zoom": 7}},
    )

    response = client.get(reverse("site_map"))

    assert response.status_code == 200
    preference_payload = parse_json_script(
        response.content.decode(), "site-list-map-preference"
    )
    basemap_config = parse_json_script(response.content.decode(), "map-basemap-config")
    basemap_preference = parse_json_script(
        response.content.decode(), "map-basemap-preference"
    )
    assert preference_payload["value"]["viewport"] == {
        "lat": -40.5,
        "lng": 175.1,
        "zoom": 7,
    }
    assert basemap_config["defaults"] == {
        "light": "carto-voyager",
        "dark": "carto-dark",
    }
    assert basemap_preference["value"] == {
        "light": "carto-voyager",
        "dark": "carto-dark",
    }


@pytest.mark.django_db
def test_access_record_list_shows_records_and_links_to_map_view(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        description="Site description from the source system.",
        latitude=-41.1,
        longitude=174.1,
    )
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=2,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Second revision",
        uploaded_by=user,
    )

    response = client.get(reverse("access_record_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Road access" in content
    assert "AA-001" in content
    assert "v2" in content
    assert reverse("access_record_global_map") in content


@pytest.mark.django_db
def test_access_record_list_search_filters_by_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    first_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Ridge Site",
        latitude=-41.1,
        longitude=174.1,
    )
    second_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Valley Site",
        latitude=-42.1,
        longitude=175.1,
    )
    AccessRecord.objects.create(site=first_site, name="Ridge access")
    AccessRecord.objects.create(site=second_site, name="Valley access")

    response = client.get(reverse("access_record_list"), {"q": "AA-002"})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Valley access" in content
    assert "Ridge access" not in content


@pytest.mark.django_db
def test_access_record_list_filters_by_status_arrival_and_site_tags(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    remote_site = Site.objects.create(
        source_name="dummy",
        external_id="remote",
        code="AA-001",
        name="Remote",
        tags=[{"label": "Remote", "color": "orange"}],
        latitude=-41.1,
        longitude=174.1,
    )
    plain_site = Site.objects.create(
        source_name="dummy",
        external_id="plain",
        code="AA-002",
        name="Plain",
        latitude=-42.1,
        longitude=175.1,
    )
    AccessRecord.objects.create(
        site=remote_site,
        name="Retired helicopter access",
        arrival_method=ArrivalMethod.HELI,
        status=AccessRecordStatus.RETIRED,
    )
    AccessRecord.objects.create(
        site=plain_site,
        name="Active road access",
        arrival_method=ArrivalMethod.ROAD,
        status=AccessRecordStatus.ACTIVE,
    )

    response = client.get(
        reverse("access_record_list"),
        {
            "status": AccessRecordStatus.RETIRED,
            "arrival_method": ArrivalMethod.HELI,
            "site_tags": "Remote",
        },
    )

    assert response.status_code == 200
    object_list = list(response.context["object_list"])
    assert [record.name for record in object_list] == ["Retired helicopter access"]
    content = response.content.decode()
    assert 'data-filter-item-color="var(--tblr-blue)"' in content
    assert 'data-filter-item-color="var(--tblr-yellow)"' in content


@pytest.mark.django_db
def test_access_record_global_map_includes_access_features(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.25, -41.25]},
                    "properties": {
                        "access_atlas:type": "access_start",
                        "label": "Gate",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("access_record_global_map"))

    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("access_record_list") in content
    assert reverse("access_record_create_global") in content
    assert "New access record" in content
    assert 'id="site-access-map"' in content
    payload = parse_json_script(content, "site-access-map-data")
    basemap_config = parse_json_script(content, "map-basemap-config")
    assert payload["points"][0]["recordId"] == access_record.pk
    assert payload["points"][0]["siteCode"] == "AA-001"
    assert payload["points"][0]["recordName"] == "Road access"
    assert "carto-voyager" in {layer["id"] for layer in basemap_config["layers"]}


@pytest.mark.django_db
def test_access_record_global_map_applies_filters_and_preserves_table_link(client):
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
    active_record = AccessRecord.objects.create(site=site, name="Active road access")
    retired_record = AccessRecord.objects.create(
        site=site,
        name="Retired access",
        status=AccessRecordStatus.RETIRED,
    )
    for access_record in [active_record, retired_record]:
        AccessRecordVersion.objects.create(
            access_record=access_record,
            version_number=1,
            geojson={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [174.25, -41.25],
                        },
                        "properties": {"access_atlas:type": "access_start"},
                    }
                ],
            },
            change_note="Initial upload",
            uploaded_by=user,
        )

    response = client.get(
        reverse("access_record_global_map"),
        {"status": AccessRecordStatus.RETIRED},
    )

    assert response.status_code == 200
    content = response.content.decode()
    payload = parse_json_script(content, "site-access-map-data")
    assert [point["recordName"] for point in payload["points"]] == ["Retired access"]
    assert 'id="list-filter-offcanvas"' in content
    assert 'data-filter-count="1"' in content
    table_view = next(
        view
        for view in response.context["access_record_views"]
        if view["label"] == "Table"
    )
    assert table_view["url"] == f"{reverse('access_record_list')}?status=retired"


@pytest.mark.django_db
def test_site_detail_renders_site_google_maps_button(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        description="Site description from the source system.",
        tags=[{"label": "Remote", "color": "orange"}],
        latitude=-41.1,
        longitude=174.1,
    )

    response = client.get(reverse("site_detail", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Open site coordinates in Google Maps" in content
    assert "Sync Status" in content
    assert "Site description from the source system." in content
    assert "Remote" in content
    assert "bg-orange-lt" in content
    assert "badge bg-blue-lt" in content
    assert (
        "https://www.google.com/maps/search/?api=1&amp;query=-41.100000%2C174.100000"
        in content
    )


@pytest.mark.django_db
def test_site_history_renders_site_google_maps_button(client):
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

    response = client.get(reverse("site_history", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Open site coordinates in Google Maps" in content
    assert (
        "https://www.google.com/maps/search/?api=1&amp;query=-41.100000%2C174.100000"
        in content
    )


@pytest.mark.django_db
def test_access_record_history_accepts_custom_per_page(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    for index in range(12):
        access_record.name = f"Road access {index}"
        access_record.save()

    response = client.get(
        reverse("access_record_history", kwargs={"pk": access_record.pk}),
        {"per_page": 10},
    )

    assert response.status_code == 200
    assert len(response.context["history_records"]) == 10
    assert response.context["per_page"] == 10
    assert response.context["paginator"].num_pages == 2


@pytest.mark.django_db
def test_site_access_records_links_to_filtered_global_map(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.7, -41.2]},
                    "properties": {
                        "access_atlas:type": "gate",
                        "label": "North gate",
                        "code": "#1234",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("site_access_records", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Road access" in content
    assert f"{reverse('access_record_global_map')}?site={site.pk}" in content
    assert 'id="site-access-map"' not in content
    assert 'data-map-toggle="access-record"' not in content
    assert "site-access-map-data" not in content


@pytest.mark.django_db
def test_site_access_records_table_sorts_records(client):
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
    AccessRecord.objects.create(site=site, name="Alpha access")
    AccessRecord.objects.create(site=site, name="Zulu access")

    response = client.get(
        f"{reverse('site_access_records', kwargs={'pk': site.pk})}?sort=-name",
    )

    assert response.status_code == 200
    assert [record.name for record in response.context["site_access_records"]] == [
        "Zulu access",
        "Alpha access",
    ]
    content = response.content.decode()
    assert "?sort=name" in content
    assert "?sort=arrival-method" in content


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

    response = client.get(reverse("site_access_records", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("access_record_create", kwargs={"site_pk": site.pk}) in content
    assert "Boat access" in content
    assert "Boat" in content
    assert access_record.get_absolute_url() in content
    assert reverse("access_record_update", kwargs={"pk": access_record.pk}) in content
    assert (
        reverse("access_record_geojson_download", kwargs={"pk": access_record.pk})
        in content
    )
    assert (
        reverse("access_record_kml_download", kwargs={"pk": access_record.pk})
        in content
    )
    assert "No access start point in latest revision." in content
    assert "ti ti-pencil" in content
    assert "Upload revision" in content
    assert (
        reverse("access_record_version_create", kwargs={"pk": access_record.pk})
        in content
    )


@pytest.mark.django_db
def test_access_record_list_shows_global_create_actions(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("access_record_list"))

    assert response.status_code == 200
    content = response.content.decode()
    create_url = reverse("access_record_create_global")
    assert create_url in content
    assert "New access record" in content
    assert 'class="nav-create-link"' in content
    assert "ti ti-plus" in content


@pytest.mark.django_db
def test_access_record_upload_prefills_site_from_site_route(client):
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

    response = client.get(reverse("access_record_create", kwargs={"site_pk": site.pk}))

    assert response.status_code == 200
    form = response.context["form"]
    assert form.initial["site"] == site.pk


@pytest.mark.django_db
def test_access_record_upload_site_field_uses_tomselect():
    form = AccessRecordUploadForm(user=User(email="user@example.com"))
    widget = form.fields["site"].widget

    assert widget.url == "autocomplete_sites"
    assert widget.label_field == "label"


@pytest.mark.django_db
def test_access_record_upload_page_includes_tomselect_media(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.get(reverse("access_record_create_global"))

    assert response.status_code == 200
    assert b"django_tomselect/js/django-tomselect" in response.content


@pytest.mark.django_db
def test_global_access_record_upload_requires_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)

    response = client.post(
        reverse("access_record_create_global"),
        {
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "geojson_file": geojson_file(),
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Site: This field is required." in content
    assert AccessRecord.objects.count() == 0
    assert AccessRecordUploadDraft.objects.count() == 0


@pytest.mark.django_db
def test_access_record_upload_rejects_staged_geojson_for_different_site(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    first_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="First site",
        latitude=-41.1,
        longitude=174.1,
    )
    second_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Second site",
        latitude=-42.1,
        longitude=175.1,
    )
    draft = AccessRecordUploadDraft.objects.create(
        user=user,
        site=first_site,
        geojson={"type": "FeatureCollection", "features": []},
        file_name="first-site.geojson",
    )

    response = client.post(
        reverse("access_record_create_global"),
        {
            "site": str(second_site.pk),
            "name": "Road access",
            "arrival_method": ArrivalMethod.ROAD,
            "change_note": "Initial upload",
            "staged_upload_id": str(draft.pk),
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "The retained GeoJSON file is no longer available." in content
    assert AccessRecord.objects.count() == 0
    assert AccessRecordUploadDraft.objects.filter(pk=draft.pk).exists()


@pytest.mark.django_db
def test_site_detail_shows_access_start_actions_per_access_record(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.2, -41.2]},
                    "properties": {"access_atlas:type": "access_start"},
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("site_access_records", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert (
        "https://www.google.com/maps/dir/?api=1&amp;destination=-41.200000%2C174.200000"
        in content
    )
    assert (
        "https://www.google.com/maps/search/?api=1&amp;query=-41.200000%2C174.200000"
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
            "site": str(site.pk),
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
def test_global_access_record_upload_creates_record_for_selected_site(client):
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
        reverse("access_record_create_global"),
        {
            "site": str(site.pk),
            "name": "Road access",
            "arrival_method": ArrivalMethod.ROAD,
            "change_note": "Initial upload",
            "geojson_file": geojson_file(),
        },
    )

    assert response.status_code == 302
    access_record = AccessRecord.objects.get(site=site)
    assert access_record.name == "Road access"
    assert access_record.arrival_method == ArrivalMethod.ROAD
    assert access_record.current_version is not None


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
            "site": str(site.pk),
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
def test_access_record_upload_rejects_oversized_geojson(client):
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
            "site": str(site.pk),
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "geojson_file": SimpleUploadedFile(
                "access.geojson",
                b"x" * (5 * 1024 * 1024 + 1),
                content_type="application/geo+json",
            ),
        },
    )

    assert response.status_code == 200
    assert "GeoJSON file must be 5 MB or smaller." in response.content.decode()
    assert AccessRecord.objects.count() == 0


@pytest.mark.django_db
def test_access_record_upload_rejects_non_geojson_extension(client):
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
            "site": str(site.pk),
            "name": "Boat access",
            "arrival_method": ArrivalMethod.BOAT,
            "change_note": "Initial upload",
            "geojson_file": SimpleUploadedFile(
                "access.txt",
                b'{"type": "FeatureCollection", "features": []}',
                content_type="application/json",
            ),
        },
    )

    assert response.status_code == 200
    assert "GeoJSON file must use .geojson or .json." in response.content.decode()
    assert AccessRecord.objects.count() == 0


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
            "site": str(site.pk),
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
            "site": str(site.pk),
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
    assert "Latest Version" in content
    assert "Arrival Method" in content
    assert "Boat" in content
    assert "v1" in content
    assert "Revisions" in content
    assert content.count(site.get_absolute_url()) == 1
    assert (
        reverse("access_record_geojson_download", kwargs={"pk": access_record.pk})
        in content
    )
    assert (
        reverse("access_record_kml_download", kwargs={"pk": access_record.pk})
        in content
    )
    assert (
        reverse("access_record_revisions", kwargs={"pk": access_record.pk}) in content
    )


@pytest.mark.django_db
def test_access_record_revisions_show_version_downloads(client):
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
    version = AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(
        reverse("access_record_revisions", kwargs={"pk": access_record.pk})
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Revisions" in content
    assert "Initial upload" in content
    assert (
        reverse(
            "access_record_version_geojson_download",
            kwargs={"record_pk": access_record.pk, "version_pk": version.pk},
        )
        in content
    )
    assert (
        reverse(
            "access_record_version_kml_download",
            kwargs={"record_pk": access_record.pk, "version_pk": version.pk},
        )
        in content
    )


@pytest.mark.django_db
def test_access_record_map_shows_single_record_map(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.7, -41.2]},
                    "properties": {
                        "access_atlas:type": "gate",
                        "label": "North gate",
                        "code": "#1234",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(reverse("access_record_map", kwargs={"pk": access_record.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="site-access-map"' in content
    assert reverse("access_record_map", kwargs={"pk": access_record.pk}) in content
    payload = parse_json_script(content, "site-access-map-data")
    assert payload["tracks"] == []
    assert len(payload["points"]) == 1
    point = payload["points"][0]
    assert point["recordId"] == access_record.pk
    assert point["recordName"] == "Road access"
    preference_payload = parse_json_script(content, "site-access-map-preference")
    assert preference_payload["value"]["visible_record_ids"] == [access_record.pk]
    assert preference_payload["value"]["animate_tracks"] is True


@pytest.mark.django_db
def test_access_record_detail_shows_warning_for_multiple_access_start_points(client):
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
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.25, -41.25]},
                    "properties": {
                        "access_atlas:type": "access_start",
                        "name": "Access start",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.26, -41.26]},
                    "properties": {
                        "access_atlas:type": "access_start",
                        "name": "Backup access start",
                    },
                },
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(access_record.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Access warnings" in content
    assert "Multiple access-start points found in the latest revision." in content


@pytest.mark.django_db
def test_access_record_detail_shows_parsed_feature_summary(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.7, -41.2]},
                    "properties": {
                        "access_atlas:type": "gate",
                        "label": "North gate",
                        "code": "#1234",
                    },
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[174.7, -41.2], [174.71, -41.21]],
                    },
                    "properties": {
                        "access_atlas:type": "track",
                        "label": "Main track",
                        "suitability": "4wd",
                    },
                },
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = client.get(access_record.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Feature Summary" in content
    assert "North gate" in content
    assert "Code: #1234" in content
    assert "Main track" in content
    assert "Suitability: 4WD" in content


@pytest.mark.django_db
def test_access_record_detail_shows_parse_error_for_invalid_latest_revision(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "Feature", "features": []},
        change_note="Broken upload",
        uploaded_by=user,
    )

    response = client.get(access_record.get_absolute_url())

    assert response.status_code == 200
    assert (
        "Latest revision could not be parsed for feature summary."
        in response.content.decode()
    )


@pytest.mark.django_db
def test_access_warning_helpers_include_site_point_mismatch():
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
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.4, -41.4]},
                    "properties": {
                        "access_atlas:type": "site",
                        "name": "Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    record_warnings = build_access_record_warnings(access_record)
    site_warnings = build_site_warnings(site)

    assert any(
        warning.message == "Site coordinates differ from source-of-truth values."
        for warning in record_warnings
    )
    assert any(
        warning.message
        == "Road access: Site coordinates differ from source-of-truth values."
        for warning in site_warnings
    )


@pytest.mark.django_db
def test_retired_access_records_do_not_contribute_site_warnings():
    user = User.objects.create_user(email="user@example.com")
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
        name="Road access",
        status=AccessRecordStatus.RETIRED,
    )
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.4, -41.4]},
                    "properties": {
                        "access_atlas:type": "site",
                        "name": "Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    record_warnings = build_access_record_warnings(access_record)
    site_warnings = build_site_warnings(site)

    assert record_warnings
    assert site_warnings == []


@pytest.mark.django_db
def test_site_warnings_ignore_retired_records_when_active_record_is_clean():
    user = User.objects.create_user(email="user@example.com")
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    retired_record = AccessRecord.objects.create(
        site=site,
        name="Old road access",
        status=AccessRecordStatus.RETIRED,
    )
    active_record = AccessRecord.objects.create(site=site, name="Current road access")
    AccessRecordVersion.objects.create(
        access_record=retired_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.4, -41.4]},
                    "properties": {
                        "access_atlas:type": "site",
                        "name": "Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )
    AccessRecordVersion.objects.create(
        access_record=active_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.1, -41.1]},
                    "properties": {
                        "access_atlas:type": "site",
                        "name": "Site",
                    },
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )

    site_warnings = build_site_warnings(site)

    assert site_warnings == []


@pytest.mark.django_db
def test_access_record_downloads_return_current_version_data(client):
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
        change_note="v1",
        uploaded_by=user,
    )
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=2,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.7603, -41.2969]},
                    "properties": {
                        "access_atlas:type": "access_start",
                        "name": "Access start",
                    },
                }
            ],
        },
        change_note="v2",
        uploaded_by=user,
    )

    geojson_response = client.get(
        reverse("access_record_geojson_download", kwargs={"pk": access_record.pk})
    )
    assert geojson_response.status_code == 200
    assert (
        geojson_response.json()["features"][0]["properties"]["name"] == "Access start"
    )
    assert "aa-001-boat-access-v2.geojson" in geojson_response["Content-Disposition"]

    kml_response = client.get(
        reverse("access_record_kml_download", kwargs={"pk": access_record.pk})
    )
    assert kml_response.status_code == 200
    assert kml_response["Content-Type"] == "application/vnd.google-earth.kml+xml"
    assert "aa-001-boat-access-v2.kml" in kml_response["Content-Disposition"]
    assert b"<kml" in kml_response.content


@pytest.mark.django_db
def test_access_record_version_downloads_return_requested_revision(client):
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
    access_record = AccessRecord.objects.create(site=site, name="Road access")
    version = AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [174.7, -41.2]},
                    "properties": {
                        "access_atlas:type": "access_start",
                        "name": "Start",
                    },
                }
            ],
        },
        change_note="Initial",
        uploaded_by=user,
    )

    geojson_response = client.get(
        reverse(
            "access_record_version_geojson_download",
            kwargs={"record_pk": access_record.pk, "version_pk": version.pk},
        )
    )
    assert geojson_response.status_code == 200
    assert geojson_response.json()["features"][0]["properties"]["name"] == "Start"
    assert "aa-001-road-access-v1.geojson" in geojson_response["Content-Disposition"]

    kml_response = client.get(
        reverse(
            "access_record_version_kml_download",
            kwargs={"record_pk": access_record.pk, "version_pk": version.pk},
        )
    )
    assert kml_response.status_code == 200
    assert "aa-001-road-access-v1.kml" in kml_response["Content-Disposition"]
    assert b"<Placemark" in kml_response.content


@pytest.mark.django_db
def test_access_record_version_download_returns_404_for_mismatched_version(client):
    user = User.objects.create_user(email="user@example.com")
    client.force_login(user)
    first_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )
    second_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Site B",
        latitude=-42.1,
        longitude=175.1,
    )
    first_record = AccessRecord.objects.create(site=first_site, name="Road access")
    second_record = AccessRecord.objects.create(site=second_site, name="Boat access")
    version = AccessRecordVersion.objects.create(
        access_record=second_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial",
        uploaded_by=user,
    )

    response = client.get(
        reverse(
            "access_record_version_geojson_download",
            kwargs={"record_pk": first_record.pk, "version_pk": version.pk},
        )
    )
    assert response.status_code == 404


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


def test_extract_taken_date_reads_exif_datetime_original():
    photo_file = image_file("dated.jpg", exif_taken_at="2026:05:01 12:30:00")

    assert extract_taken_date(photo_file).isoformat() == "2026-05-01"


def test_extract_taken_date_returns_none_without_metadata():
    assert extract_taken_date(image_file("unknown.jpg")) is None


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photo_viewer_dimensions_fall_back_to_image_file():
    user = User.objects.create_user(email="user@example.com")
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site",
        latitude=-41.1,
        longitude=174.1,
    )
    photo = SitePhoto.objects.create(
        site=site,
        image=image_file("fallback.jpg", size=(31, 19)),
        uploaded_by=user,
    )

    assert photo.viewer_width == 31
    assert photo.viewer_height == 19


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photos_upload_creates_photos_and_thumbnails(client):
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
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                image_file("dated.jpg", exif_taken_at="2026:05:01 12:30:00"),
                image_file("unknown.jpg"),
            ]
        },
    )

    assert response.status_code == 302
    photos = list(SitePhoto.objects.filter(site=site).order_by("image"))
    assert len(photos) == 2
    assert {photo.taken_date.isoformat() for photo in photos if photo.taken_date} == {
        "2026-05-01"
    }
    assert all(photo.thumbnail for photo in photos)
    assert all(photo.image_width == 24 for photo in photos)
    assert all(photo.image_height == 24 for photo in photos)
    assert all(photo.uploaded_by == user for photo in photos)
    assert photos[0].history.first().history_change_reason == "Uploaded site photo"


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photos_upload_skips_duplicates_already_on_site(client):
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
    photo_url = reverse("site_photos", kwargs={"pk": site.pk})
    client.post(photo_url, {"photos": [image_file("original.jpg")]})
    photo = SitePhoto.objects.get(site=site)
    photo.hidden = True
    photo.save(update_fields=["hidden"])

    response = client.post(
        photo_url,
        {"photos": [image_file("duplicate.jpg")]},
        follow=True,
    )

    assert response.status_code == 200
    assert SitePhoto.objects.filter(site=site).count() == 1
    photo.refresh_from_db()
    assert photo.image_sha256
    assert (
        "Skipped 1 duplicate photo already on this site." in response.content.decode()
    )


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photos_upload_hashes_legacy_photos_before_duplicate_check(client):
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
    legacy_photo = SitePhoto.objects.create(
        site=site,
        image=image_file("legacy.jpg"),
        hidden=True,
        uploaded_by=user,
    )

    response = client.post(
        reverse("site_photos", kwargs={"pk": site.pk}),
        {"photos": [image_file("duplicate.jpg")]},
        follow=True,
    )

    assert response.status_code == 200
    assert SitePhoto.objects.filter(site=site).count() == 1
    legacy_photo.refresh_from_db()
    assert legacy_photo.image_sha256
    assert (
        "Skipped 1 duplicate photo already on this site." in response.content.decode()
    )


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photos_gallery_groups_unknown_dates_after_dated_photos(client):
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
    client.post(
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                image_file("dated.jpg", exif_taken_at="2026:05:01 12:30:00"),
                image_file("unknown.jpg"),
            ]
        },
    )

    response = client.get(reverse("site_photos", kwargs={"pk": site.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    assert content.index("01 May 2026") < content.index("Unknown date")
    assert "Missing date taken metadata" in content
    assert "site-photo-grid" in content
    assert "site-photo-card-meta" not in content
    assert "data-site-photo-selection-action" in content
    assert "data-site-photo-toggle" in content
    assert "data-site-photo-group-select" in content
    assert "data-site-photo-group=" in content
    assert "data-site-photo-selection-summary" in content
    assert "data-site-photo-selection-clear" in content
    assert "data-site-photo-view" in content
    assert 'data-pswp-width="24"' in content
    assert 'data-pswp-height="24"' in content
    assert 'data-site-photo-date="01 May 2026"' in content
    assert 'data-site-photo-date="Unknown date"' in content
    assert "vendor/photoswipe/photoswipe.css" in content
    assert 'type="module" src="/static/js/site_photos.js"' in content


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photo_bulk_hide_hides_selected_photos_only(client):
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
    client.post(
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                image_file("first.jpg"),
                image_file("second.jpg", color="#2fb344"),
            ]
        },
    )
    first_photo, second_photo = SitePhoto.objects.filter(site=site).order_by("id")

    response = client.post(
        reverse("site_photo_bulk_hide", kwargs={"pk": site.pk}),
        {"photo_ids": [str(first_photo.pk)]},
    )

    assert response.status_code == 302
    first_photo.refresh_from_db()
    second_photo.refresh_from_db()
    assert first_photo.hidden is True
    assert first_photo.hidden_by == user
    assert first_photo.history.first().history_change_reason == "Hidden site photo"
    assert second_photo.hidden is False
    response = client.get(reverse("site_photos", kwargs={"pk": site.pk}))
    content = response.content.decode()
    assert f'value="{first_photo.pk}"' not in content
    assert f'value="{second_photo.pk}"' in content


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photo_bulk_download_streams_selected_originals(client):
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
    client.post(
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                image_file("first.jpg"),
                image_file("second.jpg", color="#2fb344"),
            ]
        },
    )
    first_photo, second_photo = SitePhoto.objects.filter(site=site).order_by("id")

    response = client.post(
        reverse("site_photo_bulk_download", kwargs={"pk": site.pk}),
        {"photo_ids": [str(first_photo.pk), str(second_photo.pk)]},
    )

    assert response.status_code == 200
    assert response["Content-Type"] == "application/zip"
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert len(names) == 2
    assert any(name.startswith(f"{first_photo.pk}-first") for name in names)
    assert any(name.startswith(f"{second_photo.pk}-second") for name in names)
    assert all(name.endswith(".jpg") for name in names)


@pytest.mark.django_db
@override_settings(MEDIA_ROOT="/tmp/access-atlas-test-media")
def test_site_photo_bulk_download_ignores_hidden_selected_photos(client):
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
    client.post(
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                image_file("hidden.jpg"),
                image_file("visible.jpg", color="#2fb344"),
            ]
        },
    )
    hidden_photo, visible_photo = SitePhoto.objects.filter(site=site).order_by("id")
    hidden_photo.hidden = True
    hidden_photo.hidden_by = user
    hidden_photo.save(update_fields=["hidden", "hidden_by"])

    response = client.post(
        reverse("site_photo_bulk_download", kwargs={"pk": site.pk}),
        {"photo_ids": [str(hidden_photo.pk), str(visible_photo.pk)]},
    )

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        names = archive.namelist()
    assert len(names) == 1
    assert names[0].startswith(f"{visible_photo.pk}-visible")


@pytest.mark.django_db
def test_site_photo_upload_rejects_non_image_file(client):
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
        reverse("site_photos", kwargs={"pk": site.pk}),
        {
            "photos": [
                SimpleUploadedFile(
                    "not-a-photo.txt",
                    b"not image data",
                    content_type="text/plain",
                )
            ]
        },
    )

    assert response.status_code == 200
    assert SitePhoto.objects.count() == 0
    assert "Upload a valid image" in response.content.decode()


def test_site_photo_upload_rejects_too_many_files():
    files = [
        SimpleUploadedFile(f"photo-{index}.jpg", b"image", content_type="image/jpeg")
        for index in range(51)
    ]

    form = SitePhotoUploadForm(files={"photos": files})

    assert not form.is_valid()
    assert "Upload no more than 50 photos at once." in form.errors["photos"]


def test_site_photo_upload_rejects_oversized_file():
    form = SitePhotoUploadForm(
        files={
            "photos": [
                SimpleUploadedFile(
                    "large.jpg",
                    b"x" * (20 * 1024 * 1024 + 1),
                    content_type="image/jpeg",
                )
            ]
        },
    )

    assert not form.is_valid()
    assert "large.jpg must be 20 MB or smaller." in form.errors["photos"]


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


def image_file(
    name="photo.jpg",
    *,
    exif_taken_at: str | None = None,
    size: tuple[int, int] = (24, 24),
    color: str = "#206bc4",
):
    buffer = BytesIO()
    image = Image.new("RGB", size, color=color)
    if exif_taken_at:
        exif = Image.Exif()
        exif[36867] = exif_taken_at
        image.save(buffer, format="JPEG", exif=exif)
    else:
        image.save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")
