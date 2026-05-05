import re
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils.html import escape

from access_atlas.accounts.models import User
from access_atlas.accounts.preferences import (
    get_user_preference,
    list_sort_preference_key,
)
from access_atlas.core.context_processors import active_nav_item
from access_atlas.core.templatetags.status_badges import status_badge_class
from access_atlas.jobs.models import Job, JobTemplate
from access_atlas.sites.models import (
    AccessRecord,
    AccessRecordVersion,
    Site,
    SiteSyncStatus,
)
from access_atlas.trips.models import SiteVisit, Trip, TripStatus


@pytest.fixture
def user(db):
    return User.objects.create_user(email="user@example.com", display_name="User")


@pytest.fixture
def logged_in_client(client, user):
    client.force_login(user)
    return client


def test_trip_approval_statuses_use_distinct_badge_colors():
    assert status_badge_class(TripStatus.SUBMITTED) == "bg-orange-lt"
    assert status_badge_class(TripStatus.APPROVED) == "bg-blue-lt"
    assert status_badge_class(TripStatus.COMPLETED) == "bg-green-lt"


def test_site_and_access_statuses_use_consistent_badge_colors():
    assert status_badge_class("active") == "bg-blue-lt"
    assert status_badge_class("stale") == "bg-secondary-lt"
    assert status_badge_class("retired") == "bg-yellow-lt"


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
) -> Site:
    return Site.objects.create(
        source_name="dummy",
        external_id=external_id,
        code=code,
        name=name,
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


def test_active_nav_item_maps_url_names_to_sidebar_sections():
    cases = {
        "dashboard": "dashboard",
        "trip_detail": "trips",
        "site_visit_update": "trips",
        "job_list": "jobs",
        "requirement_create": "jobs",
        "job_template_detail": "job_templates",
        "template_requirement_update": "job_templates",
        "site_detail": "sites",
        "access_record_revisions": "sites",
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
def test_global_search_shows_total_counts_and_new_object_groups(logged_in_client, user):
    site = _site(external_id="001", code="AA-001", name="Ridge Site")
    Job.objects.create(site=site, title="Ridge Inspection")
    JobTemplate.objects.create(title="Ridge Template")
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
    assert response.context["total_results"] == 6
    assert response.context["lookup_type"] == "istartswith"
    row_types = {row.object_type for row in _global_search_rows(response)}
    assert row_types == {
        "Site",
        "Job",
        "Job Template",
        "Trip",
        "Site Visit",
        "Access Record",
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
    stale_site = Site.objects.create(
        source_name="dummy",
        external_id="002",
        code="AA-002",
        name="Stale Site",
        latitude=-41.2,
        longitude=174.2,
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
                    "geometry": {"type": "Point", "coordinates": [174.11, -41.11]},
                    "properties": {"access_atlas:type": "site", "name": "Warning"},
                }
            ],
        },
        change_note="Initial upload",
        uploaded_by=user,
    )
    active_trip = Trip.objects.create(
        name="Upcoming Trip",
        start_date="2026-05-10",
        end_date="2026-05-12",
        trip_leader=user,
        status=TripStatus.APPROVED,
    )
    Trip.objects.create(
        name="Cancelled Trip",
        start_date="2026-05-11",
        end_date="2026-05-12",
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
    assert stale_site.code in content
    assert 'href="/jobs/?status=unassigned"' in content
    assert 'href="/jobs/?status=assigned"' in content
    assert f'href="{active_trip.get_absolute_url()}"' in content
    assert f'href="{warning_site.get_access_records_url()}"' in content
    assert f'href="{stale_site.get_absolute_url()}"' in content


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
def test_dummy_feed_requires_bearer_token(client, settings):
    settings.SITE_FEED_TOKEN = "secret"

    response = client.get(reverse("dummy_site_feed"))
    assert response.status_code == 403

    response = client.get(
        reverse("dummy_site_feed"),
        headers={"Authorization": "Bearer secret"},
    )
    assert response.status_code == 200
    assert response.json()["schema_version"] == "1.0"


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
