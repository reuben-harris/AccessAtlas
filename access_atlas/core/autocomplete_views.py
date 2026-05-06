from __future__ import annotations

from django_tomselect.autocompletes import AutocompleteModelView

from access_atlas.accounts.models import User
from access_atlas.jobs.models import Job, JobStatus, JobTemplate, WorkProgramme
from access_atlas.sites.models import Site


class AccessAtlasAutocompleteView(AutocompleteModelView):
    """Autocomplete base view that respects declared virtual display fields."""

    def _validate_value_fields(self) -> None:
        # django-tomselect appends label_field to value_fields during widget
        # rendering. Declared virtual fields are intentionally populated by
        # hook_prepare_results(), so they must not be logged as invalid columns.
        virtual_fields = set(getattr(self, "virtual_fields", []))
        original_value_fields = self.value_fields
        self.value_fields = [
            field for field in original_value_fields if field not in virtual_fields
        ]
        try:
            super()._validate_value_fields()
        finally:
            self.value_fields = original_value_fields


class SiteAutocompleteView(AccessAtlasAutocompleteView):
    """Autocomplete sites using the same code + name label shown across the app."""

    model = Site
    permission_required = None
    search_lookups = ["code__icontains", "name__icontains"]
    ordering = ["code"]
    value_fields = ["id", "code", "name", "label"]
    virtual_fields = ["label"]

    def hook_prepare_results(
        self,
        results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for item in results:
            item["label"] = f"{item['code']} - {item['name']}"
        return results


class TeamMemberAutocompleteView(AccessAtlasAutocompleteView):
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


class JobTemplateAutocompleteView(AccessAtlasAutocompleteView):
    """Autocomplete only active job templates, preserving current form behavior."""

    model = JobTemplate
    permission_required = None
    search_lookups = ["title__icontains", "description__icontains", "notes__icontains"]
    ordering = ["title"]
    value_fields = ["id", "title"]

    def hook_queryset(self, queryset):
        return queryset.filter(is_active=True)


class WorkProgrammeAutocompleteView(AccessAtlasAutocompleteView):
    """Autocomplete work programmes by name for job assignment."""

    model = WorkProgramme
    permission_required = None
    search_lookups = ["name__icontains", "description__icontains"]
    ordering = ["start_date", "name"]
    value_fields = ["id", "name", "start_date", "end_date", "label"]
    virtual_fields = ["label"]

    def hook_prepare_results(
        self,
        results: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        for item in results:
            item["label"] = (
                f"{item['name']} ({item['start_date']} to {item['end_date']})"
            )
        return results


class UnassignedJobAutocompleteView(AccessAtlasAutocompleteView):
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
