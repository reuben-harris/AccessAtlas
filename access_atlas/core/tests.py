import re
from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from access_atlas.accounts.models import User, UserPreference
from access_atlas.accounts.preferences import (
    ALLOWED_BASEMAP_LAYER_IDS,
    BASEMAP_LAYER_ESRI_IMAGERY_STREETS,
    MAP_BASEMAP_PREFERENCE_KEY,
    get_user_preference,
    list_filter_preference_key,
    list_sort_preference_key,
    set_user_preference,
)
from access_atlas.core.context_processors import active_nav_item
from access_atlas.core.history_diff import build_history_diff
from access_atlas.core.list_filters import FILTER_STATE_PARAM, FILTER_STATE_UPDATE
from access_atlas.core.maps import map_basemap_config, map_basemap_preference
from access_atlas.core.templatetags.form_extras import required_marker
from access_atlas.core.templatetags.status_badges import status_badge_class
from access_atlas.jobs.models import Job, JobTemplate, WorkProgramme
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordVersion,
    Site,
)
from access_atlas.trips.models import SiteVisit, SiteVisitJob, Trip, TripStatus


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", display_name="User")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


@override_settings(
    MAP_ARCGIS_API_KEY="",
    MAP_TRACESTRACK_API_KEY="",
)
def test_map_basemap_config_includes_builtin_keyless_layers():
    config = map_basemap_config()
    layers = {layer["id"]: layer for layer in config["layers"]}

    assert config["defaults"] == {"light": "carto-voyager", "dark": "carto-dark"}
    assert layers["carto-voyager"]["available"] is True
    assert layers["carto-dark"]["available"] is True
    assert layers["osm-standard"]["available"] is True
    assert layers["esri-world-imagery"]["available"] is False
    assert layers["esri-imagery-streets"]["available"] is False
    assert layers["tracestrack-topo"]["available"] is False
    assert "tile.openstreetmap.org/{z}/{x}/{y}.png" in layers["osm-standard"]["url"]
    assert "disabledReason" in layers["esri-world-imagery"]
    assert "disabledReason" in layers["esri-imagery-streets"]
    assert "disabledReason" in layers["tracestrack-topo"]


@override_settings(
    MAP_ARCGIS_API_KEY="",
    MAP_TRACESTRACK_API_KEY="",
)
def test_map_basemap_layer_ids_match_allowed_preferences():
    config = map_basemap_config()
    layer_ids = {layer["id"] for layer in config["layers"]}

    assert layer_ids == ALLOWED_BASEMAP_LAYER_IDS


@override_settings(
    MAP_ARCGIS_API_KEY="arcgis test/key",
    MAP_TRACESTRACK_API_KEY="tracestrack test/key",
)
def test_map_basemap_config_includes_keyed_provider_layers():
    config = map_basemap_config()
    layers = {layer["id"]: layer for layer in config["layers"]}

    assert "esri-world-imagery-streets" not in layers
    assert "esri-open-hybrid-detail" not in layers
    assert layers["esri-world-imagery"]["available"] is True
    assert layers["esri-world-imagery"]["url"] == (
        "https://ibasemaps-api.arcgis.com/arcgis/rest/services/"
        "World_Imagery/MapServer/tile/{z}/{y}/{x}?token=arcgis%20test%2Fkey"
    )
    assert layers["esri-world-imagery"]["maxZoom"] == 19
    assert "Esri" in layers["esri-world-imagery"]["attribution"]
    assert layers["esri-imagery-streets"]["available"] is True
    assert layers["esri-imagery-streets"]["label"] == "Esri Imagery + Streets"
    assert layers["esri-imagery-streets"]["tiles"][0] == {
        "url": (
            "https://ibasemaps-api.arcgis.com/arcgis/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}?token=arcgis%20test%2Fkey"
        ),
        "attribution": layers["esri-world-imagery"]["attribution"],
        "maxZoom": 19,
    }
    assert layers["esri-imagery-streets"]["tiles"][1]["url"] == (
        "https://static-map-tiles-api.arcgis.com/arcgis/rest/services/"
        "static-basemap-tiles-service/v1/open/hybrid/detail/static/"
        "tile/{z}/{y}/{x}?token=arcgis%20test%2Fkey"
    )
    assert layers["esri-imagery-streets"]["tiles"][1]["tileSize"] == 512
    assert layers["esri-imagery-streets"]["tiles"][1]["zoomOffset"] == -1
    assert layers["esri-imagery-streets"]["tiles"][1]["minZoom"] == 1
    assert layers["esri-imagery-streets"]["maxZoom"] == 23
    assert "Esri" in layers["esri-imagery-streets"]["tiles"][1]["attribution"]
    assert layers["tracestrack-topo"]["url"] == (
        "https://tile.tracestrack.com/topo_en/{z}/{x}/{y}.webp"
        "?key=tracestrack%20test%2Fkey"
    )
    assert layers["tracestrack-topo"]["available"] is True
    assert "Tracestrack" in layers["tracestrack-topo"]["attribution"]


@pytest.mark.parametrize(
    "stale_layer_id",
    ["esri-open-hybrid-detail", "esri-world-imagery-streets"],
)
@override_settings(
    MAP_ARCGIS_API_KEY="",
    MAP_TRACESTRACK_API_KEY="",
)
def test_map_basemap_preference_clears_removed_saved_layer(user, stale_layer_id):
    UserPreference.objects.create(
        user=user,
        key=MAP_BASEMAP_PREFERENCE_KEY,
        value={"light": stale_layer_id, "dark": "carto-dark"},
    )

    preference = map_basemap_preference(user)

    assert preference["value"] == {"light": "carto-voyager", "dark": "carto-dark"}
    assert not user.preferences.filter(key=MAP_BASEMAP_PREFERENCE_KEY).exists()


@override_settings(
    MAP_ARCGIS_API_KEY="",
    MAP_TRACESTRACK_API_KEY="",
)
def test_map_basemap_preference_clears_unavailable_saved_layer(user):
    set_user_preference(
        user,
        MAP_BASEMAP_PREFERENCE_KEY,
        {"light": BASEMAP_LAYER_ESRI_IMAGERY_STREETS, "dark": "carto-dark"},
    )

    preference = map_basemap_preference(user)

    assert preference["value"] == {"light": "carto-voyager", "dark": "carto-dark"}
    assert not user.preferences.filter(key=MAP_BASEMAP_PREFERENCE_KEY).exists()


def test_trip_approval_statuses_use_distinct_badge_colors():
    assert status_badge_class(TripStatus.SUBMITTED) == "bg-orange-lt"
    assert status_badge_class(TripStatus.APPROVED) == "bg-blue-lt"
    assert status_badge_class(TripStatus.COMPLETED) == "bg-green-lt"


def test_site_and_access_statuses_use_consistent_badge_colors():
    assert status_badge_class("active") == "bg-blue-lt"
    assert status_badge_class("stale") == "bg-secondary-lt"
    assert status_badge_class("retired") == "bg-yellow-lt"


def test_required_marker_only_renders_for_required_fields():
    required_field = SimpleNamespace(field=SimpleNamespace(required=True))
    optional_field = SimpleNamespace(field=SimpleNamespace(required=False))

    assert 'class="form-required-marker"' in str(required_marker(required_field))
    assert required_marker(optional_field) == ""


@pytest.fixture
def site(db):
    return Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Site A",
        latitude=-41.1,
        longitude=174.1,
    )


def _site(
    *,
    external_id: str,
    code: str,
    name: str,
    description: str = "",
) -> Site:
    return Site.objects.create(
        source_name="dummy",
        external_id=external_id,
        code=code,
        name=name,
        description=description,
        latitude=-41.1,
        longitude=174.1,
    )


def _global_search_rows(response):
    return list(response.context["result_rows"])


def _input_value(content: str, input_id: str) -> str:
    match = re.search(
        rf'<input\b[^>]*id="{re.escape(input_id)}"[^>]*>',
        content,
        re.DOTALL,
    )
    assert match is not None
    value_match = re.search(r'\bvalue="([^"]*)"', match.group(0))
    return value_match.group(1) if value_match else ""


def _request_for_url_name(url_name: str):
    return SimpleNamespace(resolver_match=SimpleNamespace(url_name=url_name))


def _assert_active_nav_link(content: str, href: str) -> None:
    pattern = (
        r'<li class="nav-item[^"]*\bactive\b[^"]*">\s*'
        rf'<a class="nav-link" href="{re.escape(href)}" aria-current="page">'
    )
    assert re.search(pattern, content, re.DOTALL)


@pytest.mark.django_db
def test_dashboard_renders(logged_in_client):
    response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"Dashboard" in response.content
    assert b"Work Overview" in response.content
    assert b"Upcoming Field Work" in response.content
    assert b"Data Attention" in response.content
    assert b'href="/static/css/app.css"' in response.content
    assert b'src="/static/js/theme.js"' in response.content


@pytest.mark.django_db
def test_bug_report_button_uses_configured_url(logged_in_client):
    with override_settings(
        BUG_REPORT_URL="https://github.com/example/access-atlas/issues/new"
    ):
        response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"data-bug-report-link" in response.content
    expected_href = b'href="https://github.com/example/access-atlas/issues/new"'
    assert expected_href in response.content


@pytest.mark.django_db
def test_bug_report_button_uses_default_url(logged_in_client):
    response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"data-bug-report-link" in response.content
    expected_href = b'href="https://github.com/reuben-harris/AccessAtlas/issues/new"'
    assert expected_href in response.content


@pytest.mark.django_db
def test_bug_report_button_is_hidden_when_unconfigured(logged_in_client):
    with override_settings(BUG_REPORT_URL=""):
        response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    assert b"data-bug-report-link" not in response.content


def test_active_nav_item_maps_url_names_to_sidebar_sections():
    cases = {
        "dashboard": "dashboard",
        "trip_detail": "trips",
        "site_visit_update": "trips",
        "job_list": "jobs",
        "requirement_create": "jobs",
        "work_programme_detail": "work_programmes",
        "job_template_detail": "job_templates",
        "template_requirement_update": "job_templates",
        "site_detail": "sites",
        "access_record_revisions": "access_records",
        "global_history": "history",
        "search": "",
    }

    for url_name, expected_nav_item in cases.items():
        assert active_nav_item(_request_for_url_name(url_name)) == {
            "active_nav_item": expected_nav_item
        }


@pytest.mark.django_db
def test_sidebar_highlights_current_top_level_page(logged_in_client):
    cases = [
        ("dashboard", reverse("dashboard")),
        ("trips", reverse("trip_list")),
        ("jobs", reverse("job_list")),
        ("work_programmes", reverse("work_programme_list")),
        ("job_templates", reverse("job_template_list")),
        ("sites", reverse("site_list")),
        ("history", reverse("global_history")),
    ]

    for expected_nav_item, url in cases:
        response = logged_in_client.get(url)

        assert response.status_code == 200
        assert response.context["active_nav_item"] == expected_nav_item
        _assert_active_nav_link(response.content.decode(), url)


@pytest.mark.django_db
def test_jobs_sidebar_exposes_all_compact_actions(logged_in_client):
    response = logged_in_client.get(reverse("job_list"))

    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("job_import") in content
    assert 'aria-label="Import jobs"' in content
    assert reverse("job_create_from_template") in content
    assert 'aria-label="New job from template"' in content
    assert reverse("job_create") in content
    assert 'aria-label="New job"' in content
    assert "nav-create-link-template" in content
    assert "ti ti-upload" in content
    assert "ti ti-template" in content
    assert "ti ti-plus" in content


@pytest.mark.django_db
def test_global_search_shows_total_counts_and_new_object_groups(logged_in_client, user):
    site = _site(external_id="001", code="AA-001", name="Ridge Site")
    Job.objects.create(site=site, title="Ridge Inspection")
    JobTemplate.objects.create(title="Ridge Template")
    WorkProgramme.objects.create(
        name="Ridge Work Programme",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    trip = Trip.objects.create(
        name="Ridge Trip",
        start_date="2026-05-10",
        end_date="2026-05-12",
        trip_leader=user,
    )
    SiteVisit.objects.create(trip=trip, site=site)
    access_record = AccessRecord.objects.create(site=site, name="Ridge access")
    AccessRecordVersion.objects.create(
        access_record=access_record,
        version_number=1,
        geojson={"type": "FeatureCollection", "features": []},
        change_note="Initial upload",
        uploaded_by=user,
    )

    response = logged_in_client.get(reverse("search"), {"q": "ridge"})

    assert response.status_code == 200
    assert response.context["total_results"] == 7
    assert response.context["lookup_type"] == "icontains"
    row_types = {row.object_type for row in _global_search_rows(response)}
    assert row_types == {
        "Site > Name",
        "Job > Title",
        "Job Template > Title",
        "Work Programme > Name",
        "Trip > Name",
        "Site Visit > Trip",
        "Access Record > Name",
    }
    content = response.content.decode()
    assert "Type" in content
    assert "Value" in content
    assert "Object" in content
    assert "Ridge Template" in content
    assert "Ridge access" in content
    assert "Ridge Trip - AA-001" in content
    assert '<mark class="search-match">Ridge</mark>' in content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("lookup_type", "query", "expected_names"),
    [
        ("icontains", "Ridge", ["Alpha Ridge", "Beta Ridge"]),
        ("iexact", "Alpha Field", ["Alpha Field"]),
        ("istartswith", "Alpha", ["Alpha Field", "Alpha Ridge"]),
        ("iendswith", "Ridge", ["Alpha Ridge", "Beta Ridge"]),
        ("iregex", "^(Alpha|Beta)", ["Alpha Field", "Alpha Ridge", "Beta Ridge"]),
    ],
)
def test_global_search_lookup_modes(
    logged_in_client,
    lookup_type,
    query,
    expected_names,
):
    _site(external_id="001", code="AA-001", name="Alpha Field")
    _site(external_id="002", code="AA-002", name="Alpha Ridge")
    _site(external_id="003", code="AA-003", name="Beta Ridge")
    _site(external_id="004", code="AA-004", name="Gamma Plain")

    response = logged_in_client.get(
        reverse("search"),
        {"q": query, "lookup": lookup_type, "sort": "value"},
    )

    assert response.status_code == 200
    assert [row.value for row in _global_search_rows(response)] == expected_names


@pytest.mark.django_db
def test_global_search_invalid_regex_shows_error(logged_in_client):
    _site(external_id="001", code="AA-001", name="Alpha Field")

    response = logged_in_client.get(
        reverse("search"),
        {"q": "[", "lookup": "iregex"},
    )

    assert response.status_code == 200
    assert response.context["total_results"] == 0
    assert response.context["search_error"] == "Invalid regular expression."
    assert "Invalid regular expression." in response.content.decode()


@pytest.mark.django_db
def test_global_search_matches_site_description(logged_in_client):
    _site(
        external_id="001",
        code="AA-001",
        name="Alpha Field",
        description="Generator hut beside the ridge track.",
    )

    response = logged_in_client.get(reverse("search"), {"q": "generator"})

    assert response.status_code == 200
    rows = _global_search_rows(response)
    assert len(rows) == 1
    assert rows[0].object_type == "Site > Description"
    assert rows[0].object_label == "AA-001 - Alpha Field"
    assert rows[0].value == "Generator hut beside the ridge track."


@pytest.mark.django_db
def test_global_search_sorts_rows(logged_in_client, user):
    site = _site(external_id="001", code="AA-001", name="Searchable Site")
    Job.objects.create(site=site, title="Searchable Job")
    JobTemplate.objects.create(title="Searchable Template")
    Trip.objects.create(
        name="Searchable Trip",
        start_date="2026-05-10",
        end_date="2026-05-12",
        trip_leader=user,
    )

    response = logged_in_client.get(
        reverse("search"),
        {"q": "Searchable", "sort": "object"},
    )
    assert [row.object_label for row in _global_search_rows(response)] == [
        "AA-001 - Searchable Site",
        "Searchable Job",
        "Searchable Template",
        "Searchable Trip",
    ]

    response = logged_in_client.get(
        reverse("search"),
        {"q": "Searchable", "sort": "-object"},
    )
    assert [row.object_label for row in _global_search_rows(response)] == [
        "Searchable Trip",
        "Searchable Template",
        "Searchable Job",
        "AA-001 - Searchable Site",
    ]


@pytest.mark.django_db
def test_global_search_pagination_preserves_state(logged_in_client):
    for index in range(30):
        _site(
            external_id=f"{index:03d}",
            code=f"AA-{index:03d}",
            name=f"Paginated Site {index:02d}",
        )

    response = logged_in_client.get(
        reverse("search"),
        {
            "q": "Paginated",
            "lookup": "istartswith",
            "sort": "value",
            "per_page": "10",
            "page": "2",
        },
    )

    assert response.status_code == 200
    assert response.context["page_obj"].number == 2
    assert response.context["per_page"] == 10
    content = response.content.decode()
    assert "q=Paginated" in content
    assert "lookup=istartswith" in content
    assert "sort=value" in content
    assert "per_page=10" in content


@pytest.mark.django_db
def test_global_search_accepts_custom_per_page_value(logged_in_client):
    _site(external_id="001", code="AA-001", name="Custom Page Size")

    response = logged_in_client.get(
        reverse("search"),
        {"q": "Custom", "per_page": "1000000"},
    )

    assert response.status_code == 200
    assert response.context["per_page"] == 1000000
    assert 1000000 in response.context["page_size_options"]
    assert "Per page" in response.content.decode()


@pytest.mark.django_db
def test_global_search_renders_table_without_query_or_results(logged_in_client):
    response = logged_in_client.get(reverse("search"))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Enter a search term above." not in content
    assert "Type" in content
    assert "Value" in content
    assert "Object" in content
    assert "No results found." in content

    response = logged_in_client.get(reverse("search"), {"q": "Missing"})
    content = response.content.decode()
    assert "Type" in content
    assert "Value" in content
    assert "Object" in content
    assert "No results found." in content


@pytest.mark.django_db
def test_navbar_search_stays_empty_after_local_searches(logged_in_client):
    response = logged_in_client.get(reverse("search"), {"q": "Ridge"})
    content = response.content.decode()

    assert _input_value(content, "navbar-global-search-input") == ""
    assert _input_value(content, "global-search-input") == escape("Ridge")

    response = logged_in_client.get(reverse("trip_list"), {"q": "Trip"})
    content = response.content.decode()
    assert _input_value(content, "navbar-global-search-input") == ""
    assert 'value="Trip"' in content


@pytest.mark.django_db
def test_dashboard_shows_actionable_sections(logged_in_client, user):
    warning_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Warning Site",
        latitude=-41.1,
        longitude=174.1,
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
                    "geometry": {"type": "Point", "coordinates": [174.11, -41.11]},
                    "properties": {"access_atlas:type": "site", "name": "Warning"},
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )
    today = timezone.localdate()
    active_trip = Trip.objects.create(
        name="Upcoming Trip",
        start_date=today,
        end_date=today + timezone.timedelta(days=2),
        trip_leader=user,
        status=TripStatus.APPROVED,
    )
    Trip.objects.create(
        name="Cancelled Trip",
        start_date=today + timezone.timedelta(days=1),
        end_date=today + timezone.timedelta(days=2),
        trip_leader=user,
        status=TripStatus.CANCELLED,
    )
    site = Site.objects.create(
        source_name="dummy",
        external_id="003",
        code="AA-003",
        name="Job Site",
        latitude=-41.3,
        longitude=174.3,
    )
    Job.objects.create(site=site, title="Unassigned Job")
    assigned_job = Job(site=site, title="Assigned Job", status="assigned")
    assigned_job.save(skip_validation=True)

    response = logged_in_client.get(reverse("dashboard"))

    assert response.status_code == 200
    content = response.content.decode()
    assert active_trip.name in content
    assert "Cancelled Trip" not in content
    assert warning_site.code in content
    assert 'href="/jobs/?status=unassigned"' in content
    assert 'href="/jobs/?status=assigned"' in content
    assert f'href="{active_trip.get_absolute_url()}"' in content
    assert f'href="{warning_site.get_access_records_url()}"' in content


@pytest.mark.django_db
def test_core_object_pages_render(logged_in_client, user, site):
    template = JobTemplate.objects.create(title="Inspect sensor")
    job = Job.objects.create(site=site, title="Inspect sensor", template=template)
    trip = Trip.objects.create(
        name="Trip",
        start_date="2026-04-21",
        end_date="2026-04-22",
        trip_leader=user,
    )
    visit = SiteVisit.objects.create(trip=trip, site=site)
    access_record = AccessRecord.objects.create(site=site, name="Road access")

    urls = [
        reverse("site_detail", kwargs={"pk": site.pk}),
        reverse("site_access_records", kwargs={"pk": site.pk}),
        reverse("site_history", kwargs={"pk": site.pk}),
        reverse("access_record_detail", kwargs={"pk": access_record.pk}),
        reverse("access_record_map", kwargs={"pk": access_record.pk}),
        reverse("access_record_revisions", kwargs={"pk": access_record.pk}),
        reverse("access_record_history", kwargs={"pk": access_record.pk}),
        reverse("job_template_detail", kwargs={"pk": template.pk}),
        reverse("job_template_history", kwargs={"pk": template.pk}),
        reverse("job_detail", kwargs={"pk": job.pk}),
        reverse("job_history", kwargs={"pk": job.pk}),
        reverse("trip_detail", kwargs={"pk": trip.pk}),
        reverse("trip_history", kwargs={"pk": trip.pk}),
        reverse("site_visit_detail", kwargs={"pk": visit.pk}),
        reverse("site_visit_history", kwargs={"pk": visit.pk}),
    ]

    for url in urls:
        response = logged_in_client.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
def test_global_history_renders_changes(logged_in_client, site):
    response = logged_in_client.get(reverse("global_history"))

    assert response.status_code == 200
    assert b"History" in response.content
    assert site.code.encode() in response.content


@pytest.mark.django_db
def test_global_history_supports_search_and_pagination(logged_in_client):
    for index in range(30):
        Site.objects.create(
            source_name="dummy",
            external_id=f"{index:03d}",
            code=f"AA-{index:03d}",
            name=f"History Site {index}",
            latitude=-41.1,
            longitude=174.1,
        )

    response = logged_in_client.get(reverse("global_history"), {"q": "AA-00"})

    assert response.status_code == 200
    assert response.context["per_page"] == 25
    assert response.context["paginator"].count == 10

    response = logged_in_client.get(reverse("global_history"), {"per_page": 10})

    assert response.status_code == 200
    assert len(response.context["entries"]) == 10
    assert response.context["paginator"].num_pages >= 3


@pytest.mark.django_db
def test_global_history_filters_by_object_type_action_and_user(client, user):
    client.force_login(user)
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="History Site",
        latitude=-41.1,
        longitude=174.1,
    )
    site.name = "Updated History Site"
    site._history_user = user
    site.save()
    JobTemplate.objects.create(title="History Template")

    response = client.get(
        reverse("global_history"),
        {
            "object_type": "site",
            "action": "Changed",
            "user": str(user.pk),
        },
    )

    assert response.status_code == 200
    entries = list(response.context["entries"])
    assert [entry.object_display for entry in entries] == [
        "AA-001 - Updated History Site"
    ]
    assert response.context["active_filter_chips"]


@pytest.mark.django_db
def test_global_history_filter_update_marker_saves_filter_preference(client, user):
    client.force_login(user)

    response = client.get(
        reverse("global_history"),
        {
            FILTER_STATE_PARAM: FILTER_STATE_UPDATE,
            "object_type": "site",
            "action": "Created",
        },
    )

    assert response.status_code == 302
    assert response.url == (
        f"{reverse('global_history')}?object_type=site&action=Created"
    )
    assert get_user_preference(user, list_filter_preference_key("history")) == {
        "params": {"object_type": ["site"], "action": ["Created"]}
    }


@pytest.mark.django_db
def test_global_history_filter_update_marker_clears_filter_preference(client, user):
    set_user_preference(
        user,
        list_filter_preference_key("history"),
        {"params": {"object_type": ["site"], "object_id": ["1"]}},
    )
    client.force_login(user)

    response = client.get(
        reverse("global_history"),
        {FILTER_STATE_PARAM: FILTER_STATE_UPDATE},
    )

    assert response.status_code == 302
    assert response.url == reverse("global_history")
    assert get_user_preference(user, list_filter_preference_key("history")) == {
        "params": {}
    }


@pytest.mark.django_db
def test_global_history_filters_by_specific_object(logged_in_client):
    selected_site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Selected Site",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Other Site",
        latitude=-42.1,
        longitude=175.1,
    )
    selected_site.name = "Selected Site Updated"
    selected_site.save()

    response = logged_in_client.get(
        reverse("global_history"),
        {
            "object_type": "site",
            "object_id": str(selected_site.pk),
        },
    )

    assert response.status_code == 200
    entries = list(response.context["entries"])
    assert entries
    assert {entry.object_type_slug for entry in entries} == {"site"}
    assert {entry.object_id for entry in entries} == {str(selected_site.pk)}
    assert all("Selected Site" in entry.object_display for entry in entries)


def _create_orphaned_site_visit_job_history(user):
    site = Site.objects.create(
        source_name="dummy",
        external_id="orphaned-assignment",
        code="AA-ORPHAN",
        name="Orphaned Assignment Site",
        latitude=-41.1,
        longitude=174.1,
    )
    trip = Trip.objects.create(
        name="Orphaned Assignment Trip",
        start_date=timezone.localdate(),
        end_date=timezone.localdate(),
        trip_leader=user,
    )
    site_visit = SiteVisit.objects.create(trip=trip, site=site)
    job = Job.objects.create(site=site, title="Orphaned assignment job")
    assignment = SiteVisitJob.objects.create(site_visit=site_visit, job=job)

    site_visit.delete()

    return assignment


@pytest.mark.django_db
def test_global_history_warns_for_deleted_related_object_history(client, user):
    client.force_login(user)
    assignment = _create_orphaned_site_visit_job_history(user)

    response = client.get(reverse("global_history"))

    assert response.status_code == 200
    entries = list(response.context["entries"])
    warning_entry = next(
        entry
        for entry in entries
        if entry.object_type_slug == "site-visit-job"
        and entry.object_id == str(assignment.pk)
    )
    assert warning_entry.object_display == f"Site Visit Job {assignment.pk}"
    assert warning_entry.object_display_warning is True
    assert warning_entry.object_url == ""
    expected_warning = (
        "This history row references an object or relationship that has since "
        "been deleted."
    )
    assert warning_entry.object_display_warning_message == expected_warning
    deleted_site_visit_entry = next(
        entry
        for entry in entries
        if entry.object_type_slug == "site-visit"
        and entry.object_id == str(assignment.site_visit_id)
        and entry.action == "Created"
    )
    assert deleted_site_visit_entry.object_display_warning is True
    assert deleted_site_visit_entry.object_url == ""

    content = response.content.decode()
    assert "warning-indicator" in content
    assert "ti-alert-triangle-filled" in content
    assert expected_warning in content


@pytest.mark.django_db
def test_global_history_reported_filter_url_tolerates_deleted_related_history(
    client,
    user,
):
    client.force_login(user)
    _create_orphaned_site_visit_job_history(user)

    response = client.get(
        reverse("global_history"),
        {
            "object_id": "1",
            "object_type": ["site", "site-photo"],
        },
    )

    assert response.status_code == 200


@pytest.mark.django_db
def test_global_history_detail_tolerates_deleted_related_object_history(client, user):
    client.force_login(user)
    assignment = _create_orphaned_site_visit_job_history(user)
    history_record = (
        SiteVisitJob.history.filter(id=assignment.pk)
        .order_by("-history_date", "-history_id")
        .first()
    )

    response = client.get(
        reverse(
            "global_history_detail",
            kwargs={
                "object_type": "site-visit-job",
                "history_id": history_record.history_id,
            },
        )
    )

    assert response.status_code == 200
    expected_warning = (
        "This history row references an object or relationship that has since "
        "been deleted."
    )
    assert response.context["history_object_display"] == (
        f"Site Visit Job {assignment.pk}"
    )
    assert response.context["history_object_display_warning"] is True
    assert (
        response.context["history_object_display_warning_message"] == expected_warning
    )
    site_visit_row = next(
        row
        for row in response.context["history_diff"].rows
        if row.label == "Site Visit"
    )
    assert site_visit_row.before_display == str(assignment.site_visit_id)


@pytest.mark.django_db
def test_global_history_date_links_use_canonical_detail_url_with_context(
    logged_in_client,
    site,
):
    job = Job.objects.create(site=site, title="History job")
    job.title = "History job updated"
    job.save()

    response = logged_in_client.get(
        reverse("global_history"),
        {
            "object_type": "job",
            "object_id": str(job.pk),
        },
    )

    assert response.status_code == 200
    entry = response.context["entries"][0]
    expected_url = f"{entry.history_detail_url}?object_type=job&amp;object_id={job.pk}"
    assert expected_url in response.content.decode()


@pytest.mark.django_db
def test_object_history_links_to_filtered_global_history(logged_in_client, site):
    job = Job.objects.create(site=site, title="History job")
    job.title = "History job updated"
    job.save()

    response = logged_in_client.get(reverse("job_history", kwargs={"pk": job.pk}))

    assert response.status_code == 200
    content = response.content.decode()
    global_history_url = reverse("global_history")
    assert f"{global_history_url}?object_type=job&amp;object_id={job.pk}" in content
    assert "View in global history" in content
    for record in response.context["history_records"]:
        detail_url = reverse(
            "global_history_detail",
            kwargs={"object_type": "job", "history_id": record.history_id},
        )
        expected_url = f"{detail_url}?object_type=job&object_id={job.pk}"
        assert record.history_detail_url == expected_url


@pytest.mark.django_db
def test_global_history_detail_preserves_object_context_for_adjacent_links(
    logged_in_client,
    site,
):
    job = Job.objects.create(site=site, title="History job")
    job.title = "History job updated"
    job.save()
    job.description = "Second update"
    job.save()
    records = list(job.history.order_by("history_date", "history_id"))
    middle_record = records[1]

    response = logged_in_client.get(
        reverse(
            "global_history_detail",
            kwargs={"object_type": "job", "history_id": middle_record.history_id},
        ),
        {
            "object_type": "job",
            "object_id": str(job.pk),
        },
    )

    assert response.status_code == 200
    query_string = f"?object_type=job&object_id={job.pk}"
    assert response.context["previous_history_url"].endswith(query_string)
    assert response.context["next_history_url"].endswith(query_string)


@pytest.mark.django_db
def test_global_history_detail_404s_for_unknown_slug(logged_in_client):
    response = logged_in_client.get(
        reverse(
            "global_history_detail",
            kwargs={"object_type": "missing", "history_id": 1},
        ),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_global_history_detail_does_not_resolve_history_id_under_wrong_slug(
    logged_in_client,
    site,
):
    site_history_id = site.history.first().history_id

    response = logged_in_client.get(
        reverse(
            "global_history_detail",
            kwargs={"object_type": "job", "history_id": site_history_id},
        ),
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_history_diff_marks_changed_raw_json_lines(site):
    site.name = "Updated raw history site"
    site.save()
    previous_record, current_record = list(
        site.history.order_by("history_date", "history_id")
    )

    diff = build_history_diff(current_record, previous_record)

    assert any(
        line.changed and line.text.strip().startswith('"name":')
        for line in diff.before_json_lines
    )
    assert any(
        line.changed and line.text.strip().startswith('"name":')
        for line in diff.after_json_lines
    )
    assert not any(
        line.changed and line.text.strip().startswith('"code":')
        for line in diff.after_json_lines
    )


@pytest.mark.django_db
def test_global_history_sorts_and_saves_user_preference(client, user):
    client.force_login(user)
    Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Zulu Site",
        latitude=-41.1,
        longitude=174.1,
    )
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Alpha Site",
        latitude=-42.1,
        longitude=175.1,
    )

    response = client.get(reverse("global_history"), {"sort": "object"})

    assert response.status_code == 200
    entries = list(response.context["entries"])
    assert entries[0].object_display == "AA-001 - Alpha Site"
    assert get_user_preference(
        user,
        list_sort_preference_key("history"),
    ) == {"value": "object"}


@pytest.mark.django_db
def test_history_records_get_default_reason(site):
    assert site.history.first().history_change_reason == "Created site"


@pytest.mark.django_db
def test_site_autocomplete_returns_code_and_name(logged_in_client):
    Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Example Ridge Station",
        latitude=-41.1,
        longitude=174.1,
    )

    response = logged_in_client.get(reverse("autocomplete_sites"), {"q": "Ridge"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "AA-001 - Example Ridge Station"


@pytest.mark.django_db
def test_site_autocomplete_returns_missing_code_label(logged_in_client):
    _site(
        external_id="blank",
        code="",
        name="NIC House Test Facility",
    )

    response = logged_in_client.get(reverse("autocomplete_sites"), {"q": "NIC"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == ("code not set - NIC House Test Facility")


@pytest.mark.django_db
def test_global_search_uses_missing_site_code_label(logged_in_client):
    _site(
        external_id="blank",
        code="",
        name="NIC House Test Facility",
    )

    response = logged_in_client.get(reverse("search"), {"q": "NIC"})

    assert response.status_code == 200
    site_row = next(
        row for row in _global_search_rows(response) if row.object_type == "Site > Name"
    )
    assert site_row.object_label == "code not set - NIC House Test Facility"


@pytest.mark.django_db
def test_team_member_autocomplete_prefers_display_name(logged_in_client):
    User.objects.create_user(email="alpha@example.com", display_name="Alpha User")
    User.objects.create_user(email="bravo@example.com")

    response = logged_in_client.get(
        reverse("autocomplete_team_members"),
        {"q": "alpha"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "Alpha User"


@pytest.mark.django_db
def test_team_member_autocomplete_falls_back_to_email(logged_in_client):
    User.objects.create_user(email="fallback@example.com")

    response = logged_in_client.get(
        reverse("autocomplete_team_members"),
        {"q": "fallback"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "fallback@example.com"


@pytest.mark.django_db
def test_job_template_autocomplete_only_returns_active_templates(logged_in_client):
    JobTemplate.objects.create(title="Active Template", is_active=True)
    JobTemplate.objects.create(title="Inactive Template", is_active=False)

    response = logged_in_client.get(
        reverse("autocomplete_job_templates"),
        {"q": "Template"},
    )

    assert response.status_code == 200
    payload = response.json()
    labels = [item["title"] for item in payload["results"]]
    assert "Active Template" in labels
    assert "Inactive Template" not in labels


@pytest.mark.django_db
def test_work_programme_autocomplete_returns_matching_programmes(logged_in_client):
    WorkProgramme.objects.create(
        name="Ridge Renewal Programme",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )
    WorkProgramme.objects.create(
        name="Coastal Programme",
        start_date="2026-01-01",
        end_date="2026-12-31",
    )

    response = logged_in_client.get(
        reverse("autocomplete_work_programmes"),
        {"q": "Ridge"},
    )

    assert response.status_code == 200
    payload = response.json()
    results = payload["results"]
    assert [item["name"] for item in results] == ["Ridge Renewal Programme"]
    assert results[0]["label"] == "Ridge Renewal Programme (2026-01-01 to 2026-12-31)"


@pytest.mark.django_db
def test_work_programme_autocomplete_labels_missing_dates(logged_in_client):
    WorkProgramme.objects.create(name="Draft Programme")

    response = logged_in_client.get(
        reverse("autocomplete_work_programmes"),
        {"q": "Draft"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["results"][0]["label"] == "Draft Programme (dates not set)"


@pytest.mark.django_db
def test_unprogrammed_job_autocomplete_excludes_jobs_with_work_programmes(
    logged_in_client,
):
    site = Site.objects.create(
        source_name="dummy",
        external_id="001",
        code="AA-001",
        name="Example Ridge Station",
        latitude=-41.1,
        longitude=174.1,
    )
    work_programme = WorkProgramme.objects.create(name="2026 Field Work")
    available_job = Job.objects.create(site=site, title="Available Job")
    programmed_job = Job.objects.create(
        site=site,
        title="Programmed Job",
        work_programme=work_programme,
    )

    response = logged_in_client.get(
        reverse("autocomplete_unprogrammed_jobs"),
        {"q": "Job"},
    )

    assert response.status_code == 200
    payload = response.json()
    labels = [item["label"] for item in payload["results"]]
    assert f"{available_job.title} - {site}" in labels
    assert programmed_job.title not in " ".join(labels)
