from __future__ import annotations

from django_tomselect.autocompletes import AutocompleteModelView

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job, JobStatus, JobTemplate
from access_atlas.sites.models import Site


class SiteAutocompleteView(AutocompleteModelView):
    """Autocomplete sites using the same code + name label shown across the app."""

    model = Site
    permission_required = None
    search_lookups = ["code__icontains", "name__icontains"]
    ordering = ["code"]
    value_fields = ["id", "code", "name"]
    virtual_fields = ["label"]

    def hook_prepare_results(
        self,
        results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for item in results:
            item["label"] = f"{item['code']} - {item['name']}"
        return results


class TeamMemberAutocompleteView(AutocompleteModelView):
    """Autocomplete users by display name or email for trip team membership."""

    model = User
    permission_required = None
    search_lookups = ["display_name__icontains", "email__icontains"]
    ordering = ["display_name", "email"]
    value_fields = ["id", "display_name", "email"]
    virtual_fields = ["label"]

    def hook_prepare_results(
        self,
        results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for item in results:
            item["label"] = item["display_name"] or item["email"]
        return results


class JobTemplateAutocompleteView(AutocompleteModelView):
    """Autocomplete only active job templates, preserving current form behavior."""

    model = JobTemplate
    permission_required = None
    search_lookups = ["title__icontains", "description__icontains", "notes__icontains"]
    ordering = ["title"]
    value_fields = ["id", "title"]

    def hook_queryset(self, queryset):
        return queryset.filter(is_active=True)


class UnassignedJobAutocompleteView(AutocompleteModelView):
    """Autocomplete jobs that can still be assigned to a site visit."""

    model = Job
    permission_required = None
    search_lookups = [
        "title__icontains",
        "site__code__icontains",
        "site__name__icontains",
    ]
    ordering = ["title"]
    allowed_filter_fields = ["site_id"]
    value_fields = ["id", "title"]
    virtual_fields = ["label"]

    def hook_queryset(self, queryset):
        return queryset.filter(
            status=JobStatus.UNASSIGNED,
            site_visit_assignment__isnull=True,
        ).select_related("site")

    def hook_prepare_results(
        self,
        results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for item in results:
            item["label"] = str(item["title"])
        return results
