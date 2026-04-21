from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from simple_history.models import HistoricalRecords

from access_atlas.jobs.models import Job, JobStatus
from access_atlas.sites.models import Site


class TripStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PLANNED = "planned", "Planned"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class SiteVisitStatus(models.TextChoices):
    PLANNED = "planned", "Planned"
    SKIPPED = "skipped", "Skipped"
    COMPLETED = "completed", "Completed"


class Trip(models.Model):
    name = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField()
    trip_leader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="led_trips",
        on_delete=models.PROTECT,
    )
    team_members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="trips",
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=TripStatus.choices,
        default=TripStatus.DRAFT,
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-start_date", "name"]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("trip_detail", kwargs={"pk": self.pk})

    def clean(self) -> None:
        if self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})


class SiteVisit(models.Model):
    trip = models.ForeignKey(
        Trip,
        related_name="site_visits",
        on_delete=models.CASCADE,
    )
    site = models.ForeignKey(
        Site,
        related_name="site_visits",
        on_delete=models.PROTECT,
    )
    planned_order = models.PositiveIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=SiteVisitStatus.choices,
        default=SiteVisitStatus.PLANNED,
    )
    notes = models.TextField(blank=True)
    jobs = models.ManyToManyField(
        Job,
        through="SiteVisitJob",
        related_name="site_visits",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["trip", "planned_order", "site__code"]

    def __str__(self) -> str:
        return f"{self.trip} - {self.site}"

    def get_absolute_url(self) -> str:
        return reverse("site_visit_detail", kwargs={"pk": self.pk})


class SiteVisitJob(models.Model):
    site_visit = models.ForeignKey(SiteVisit, on_delete=models.CASCADE)
    job = models.OneToOneField(
        Job,
        related_name="site_visit_assignment",
        on_delete=models.CASCADE,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["assigned_at"]

    def __str__(self) -> str:
        return f"{self.job} assigned to {self.site_visit}"

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        if self.job.status == JobStatus.UNASSIGNED:
            self.job.status = JobStatus.PLANNED
            self.job.save(update_fields=["status", "updated_at"], skip_validation=True)
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.job.site_id != self.site_visit.site_id:
            raise ValidationError("Job site must match the site visit site.")
