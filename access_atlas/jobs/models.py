from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.urls import reverse
from simple_history.models import HistoricalRecords

from access_atlas.sites.models import Site


class Priority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class JobStatus(models.TextChoices):
    UNASSIGNED = "unassigned", "Unassigned"
    ASSIGNED = "assigned", "Assigned"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class RequirementType(models.TextChoices):
    TOOL = "tool", "Tool"
    PART = "part", "Part"
    CABLE = "cable", "Cable"
    CONSUMABLE = "consumable", "Consumable"
    PERMISSION = "permission", "Permission"
    NOTE = "note", "Note"
    ON_SITE_ITEM = "on_site_item", "Item already at site"


class JobTemplate(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                Lower("title"),
                name="unique_job_template_title_case_insensitive",
            )
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("job_template_detail", kwargs={"pk": self.pk})

    def get_history_url(self) -> str:
        return reverse("job_template_history", kwargs={"pk": self.pk})

    def clean(self) -> None:
        duplicate_titles = JobTemplate.objects.filter(title__iexact=self.title)
        if self.pk:
            duplicate_titles = duplicate_titles.exclude(pk=self.pk)
        if duplicate_titles.exists():
            raise ValidationError(
                {"title": "A job template with this title already exists."}
            )


class TemplateRequirement(models.Model):
    job_template = models.ForeignKey(
        JobTemplate,
        related_name="template_requirements",
        on_delete=models.CASCADE,
    )
    requirement_type = models.CharField(
        max_length=30,
        choices=RequirementType.choices,
        default=RequirementType.NOTE,
    )
    name = models.CharField(max_length=255)
    quantity = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Job(models.Model):
    site = models.ForeignKey(Site, related_name="jobs", on_delete=models.PROTECT)
    template = models.ForeignKey(
        JobTemplate,
        related_name="created_jobs",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=20,
        choices=JobStatus.choices,
        default=JobStatus.UNASSIGNED,
    )
    closeout_note = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["site__code", "title"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        skip_validation = kwargs.pop("skip_validation", False)
        if not skip_validation:
            self.full_clean()
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("job_detail", kwargs={"pk": self.pk})

    def get_history_url(self) -> str:
        return reverse("job_history", kwargs={"pk": self.pk})

    def clean(self) -> None:
        if self.status == JobStatus.ASSIGNED and (not self.pk or not self.is_assigned):
            raise ValidationError(
                {"status": "A job can only be assigned when linked to a site visit."}
            )
        if (
            self.status in {JobStatus.COMPLETED, JobStatus.CANCELLED}
            and not self.closeout_note.strip()
        ):
            raise ValidationError(
                {
                    "closeout_note": (
                        "A closeout note is required for completed or cancelled jobs."
                    )
                }
            )

    @property
    def is_assigned(self) -> bool:
        return hasattr(self, "site_visit_assignment")


class Requirement(models.Model):
    job = models.ForeignKey(Job, related_name="requirements", on_delete=models.CASCADE)
    requirement_type = models.CharField(
        max_length=30,
        choices=RequirementType.choices,
        default=RequirementType.NOTE,
    )
    name = models.CharField(max_length=255)
    quantity = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_required = models.BooleanField(default=True)
    is_checked = models.BooleanField(default=False)
    history = HistoricalRecords()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
