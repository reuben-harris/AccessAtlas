from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Site


@admin.register(Site)
class SiteAdmin(SimpleHistoryAdmin):
    list_display = [
        "code",
        "name",
        "source_name",
        "external_id",
        "heli_only",
        "last_seen_at",
    ]
    list_filter = ["heli_only", "source_name"]
    search_fields = ["code", "name", "external_id", "source_name"]
    readonly_fields = [
        "source_name",
        "external_id",
        "code",
        "name",
        "latitude",
        "longitude",
        "road_end_latitude",
        "road_end_longitude",
        "heli_only",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]
