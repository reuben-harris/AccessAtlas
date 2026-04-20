from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Site


@admin.register(Site)
class SiteAdmin(SimpleHistoryAdmin):
    list_display = ["code", "name", "source_name", "external_id", "last_seen_at"]
    search_fields = ["code", "name", "external_id", "source_name"]
    readonly_fields = [
        "source_name",
        "external_id",
        "code",
        "name",
        "latitude",
        "longitude",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
