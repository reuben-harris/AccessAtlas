from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .display import display_site_code
from .models import Site, SitePhoto


@admin.register(Site)
class SiteAdmin(SimpleHistoryAdmin):
    list_display = [
        "display_code",
        "name",
        "source_name",
        "external_id",
        "sync_status",
        "last_seen_at",
    ]
    list_filter = ["sync_status", "source_name"]
    search_fields = ["code", "name", "description", "external_id", "source_name"]
    readonly_fields = [
        "source_name",
        "external_id",
        "display_code",
        "name",
        "description",
        "tags",
        "latitude",
        "longitude",
        "sync_status",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]

    @admin.display(ordering="code", description="Code")
    def display_code(self, obj: Site) -> str:
        return display_site_code(obj.code)


@admin.register(SitePhoto)
class SitePhotoAdmin(SimpleHistoryAdmin):
    list_display = [
        "site",
        "taken_date",
        "uploaded_by",
        "uploaded_at",
        "hidden",
    ]
    list_filter = ["hidden", "taken_date", "uploaded_at"]
    search_fields = ["site__code", "site__name", "uploaded_by__email"]
    readonly_fields = [
        "site",
        "image",
        "thumbnail",
        "taken_date",
        "uploaded_by",
        "uploaded_at",
        "hidden_at",
        "hidden_by",
    ]
