from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone
from simple_history.models import HistoricalRecords

from access_atlas.jobs.models import Job
from access_atlas.sites.models import Site


class TripStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
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
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="submitted_trips",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    approval_round = models.PositiveIntegerField(default=0)
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

    def get_history_url(self) -> str:
        return reverse("trip_history", kwargs={"pk": self.pk})

    @property
    def is_terminal(self) -> bool:
        return self.status in {TripStatus.COMPLETED, TripStatus.CANCELLED}

    @property
    def can_submit_for_approval(self) -> bool:
        return self.status == TripStatus.DRAFT

    def current_approvals(self):
        return self.trip_approvals.filter(approval_round=self.approval_round)

    def clean(self) -> None:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError(
                {"end_date": "End date must be on or after the start date."}
            )


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
    planned_day = models.DateField(blank=True, null=True)
    planned_start = models.DateTimeField(blank=True, null=True)
    planned_end = models.DateTimeField(blank=True, null=True)
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
        ordering = ["trip", "planned_day", "planned_start", "site__code", "id"]

    def __str__(self) -> str:
        return f"{self.trip} - {self.site}"

    def get_absolute_url(self) -> str:
        return reverse("site_visit_detail", kwargs={"pk": self.pk})

    def get_history_url(self) -> str:
        return reverse("site_visit_history", kwargs={"pk": self.pk})

    @staticmethod
    def planned_date(value):
        if timezone.is_aware(value):
            return timezone.localtime(value).date()
        return value.date()

    def clean(self) -> None:
        errors = {}
        if not self.planned_day:
            errors["planned_day"] = "Choose a trip day."
        if self.planned_end and not self.planned_start:
            errors["planned_start"] = "A planned end requires a planned start."
        if (
            self.planned_start
            and self.planned_end
            and self.planned_end <= self.planned_start
        ):
            errors["planned_end"] = "Planned end must be after planned start."
        if errors or not self.trip_id:
            if errors:
                raise ValidationError(errors)
            return

        trip_start = self.trip.start_date
        trip_end = self.trip.end_date
        trip_date_message = f"Must be between {trip_start} and {trip_end}."
        if self.planned_day:
            if self.planned_day < trip_start or self.planned_day > trip_end:
                errors["planned_day"] = trip_date_message
        if self.planned_start:
            planned_start_date = self.planned_date(self.planned_start)
            if self.planned_day and planned_start_date != self.planned_day:
                errors["planned_start"] = "Start time must be on the selected trip day."
            elif planned_start_date < trip_start or planned_start_date > trip_end:
                errors["planned_start"] = trip_date_message
        if self.planned_end:
            planned_end_date = self.planned_date(self.planned_end)
            if self.planned_day and planned_end_date != self.planned_day:
                errors["planned_end"] = "End time must be on the selected trip day."
            elif planned_end_date < trip_start or planned_end_date > trip_end:
                errors["planned_end"] = trip_date_message
        if errors:
            raise ValidationError(errors)


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
        super().save(*args, **kwargs)

    def clean(self) -> None:
        if self.job.site_id != self.site_visit.site_id:
            raise ValidationError("Job site must match the site visit site.")


class TripApproval(models.Model):
    trip = models.ForeignKey(
        Trip,
        related_name="trip_approvals",
        on_delete=models.CASCADE,
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="trip_approvals",
        on_delete=models.PROTECT,
    )
    approval_round = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "approver", "approval_round"],
                name="unique_trip_approval_per_round",
            )
        ]

    def __str__(self) -> str:
        return f"{self.approver} approved {self.trip} (round {self.approval_round})"
