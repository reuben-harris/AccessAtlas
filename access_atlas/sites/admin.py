from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AccessRecord, AccessRecordVersion, Site


@admin.register(Site)
class SiteAdmin(SimpleHistoryAdmin):
    list_display = [
        "code",
        "name",
        "source_name",
        "external_id",
        "last_seen_at",
    ]
    list_filter = ["source_name"]
    search_fields = ["code", "name", "external_id", "source_name"]
    readonly_fields = [
        "source_name",
        "external_id",
        "code",
        "name",
        "latitude",
        "longitude",
        "access_start_latitude",
        "access_start_longitude",
        "last_seen_at",
        "created_at",
        "updated_at",
    ]


class AccessRecordVersionInline(admin.TabularInline):
    model = AccessRecordVersion
    fields = ["version_number", "change_note", "uploaded_by", "created_at"]
    readonly_fields = ["version_number", "change_note", "uploaded_by", "created_at"]
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AccessRecord)
class AccessRecordAdmin(SimpleHistoryAdmin):
    list_display = ["site", "created_at", "updated_at"]
    search_fields = ["site__code", "site__name"]
    readonly_fields = ["site", "created_at", "updated_at"]
    inlines = [AccessRecordVersionInline]


@admin.register(AccessRecordVersion)
class AccessRecordVersionAdmin(SimpleHistoryAdmin):
    list_display = [
        "access_record",
        "version_number",
        "uploaded_by",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = [
        "access_record__site__code",
        "access_record__site__name",
        "change_note",
        "uploaded_by__email",
    ]
    readonly_fields = [
        "access_record",
        "version_number",
        "geojson",
        "change_note",
        "uploaded_by",
        "created_at",
    ]
