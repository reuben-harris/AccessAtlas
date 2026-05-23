from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AccessRecord, AccessRecordVersion


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
    list_display = [
        "site",
        "name",
        "arrival_method",
        "status",
        "created_at",
        "updated_at",
    ]
    list_filter = ["arrival_method", "status"]
    search_fields = ["site__code", "site__name", "name"]
    readonly_fields = ["created_at", "updated_at"]
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
