from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Job, JobTemplate, Requirement, TemplateRequirement, WorkProgramme


class TemplateRequirementInline(admin.TabularInline):
    model = TemplateRequirement
    extra = 0


class RequirementInline(admin.TabularInline):
    model = Requirement
    extra = 0


@admin.register(JobTemplate)
class JobTemplateAdmin(SimpleHistoryAdmin):
    list_display = ["title", "priority", "estimated_duration_minutes", "is_active"]
    search_fields = ["title", "description", "notes"]
    inlines = [TemplateRequirementInline]


@admin.register(WorkProgramme)
class WorkProgrammeAdmin(SimpleHistoryAdmin):
    list_display = ["name", "start_date", "end_date"]
    search_fields = ["name", "description"]


@admin.register(Job)
class JobAdmin(SimpleHistoryAdmin):
    list_display = [
        "title",
        "site",
        "work_programme",
        "priority",
        "status",
        "estimated_duration_minutes",
    ]
    list_filter = ["status", "priority", "work_programme"]
    search_fields = [
        "title",
        "description",
        "notes",
        "site__code",
        "site__name",
        "work_programme__name",
    ]
    inlines = [RequirementInline]


@admin.register(TemplateRequirement)
class TemplateRequirementAdmin(SimpleHistoryAdmin):
    list_display = ["name", "job_template", "requirement_type", "quantity"]
    search_fields = ["name", "notes", "job_template__title"]


@admin.register(Requirement)
class RequirementAdmin(SimpleHistoryAdmin):
    list_display = ["name", "job", "requirement_type", "quantity", "is_checked"]
    search_fields = ["name", "notes", "job__title"]
