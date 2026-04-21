from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import SiteVisit, SiteVisitJob, Trip


class SiteVisitInline(admin.TabularInline):
    model = SiteVisit
    extra = 0


class SiteVisitJobInline(admin.TabularInline):
    model = SiteVisitJob
    extra = 0


@admin.register(Trip)
class TripAdmin(SimpleHistoryAdmin):
    list_display = ["name", "start_date", "end_date", "trip_leader", "status"]
    list_filter = ["status"]
    search_fields = ["name", "notes"]
    inlines = [SiteVisitInline]


@admin.register(SiteVisit)
class SiteVisitAdmin(SimpleHistoryAdmin):
    list_display = [
        "trip",
        "site",
        "planned_start",
        "planned_end",
        "planned_order",
        "status",
    ]
    list_filter = ["status"]
    search_fields = ["trip__name", "site__code", "site__name", "notes"]
    inlines = [SiteVisitJobInline]


@admin.register(SiteVisitJob)
class SiteVisitJobAdmin(SimpleHistoryAdmin):
    list_display = ["site_visit", "job", "assigned_at"]
    search_fields = ["site_visit__trip__name", "job__title"]
