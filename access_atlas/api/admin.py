from django.contrib import admin

from .models import ApiToken


@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "user",
        "key_prefix",
        "can_write",
        "expires_at",
        "last_used_at",
        "revoked_at",
    ]
    list_filter = ["can_write", "revoked_at", "expires_at"]
    search_fields = ["name", "key_prefix", "user__email", "user__display_name"]
    readonly_fields = [
        "key_prefix",
        "key_hash",
        "last_used_at",
        "created_at",
        "updated_at",
    ]
