from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from simple_history.models import HistoricalRecords


class SiteSyncStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    STALE = "stale", "Stale"


class Site(models.Model):
    source_name = models.CharField(max_length=100)
    external_id = models.CharField(max_length=255)
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    sync_status = models.CharField(
        max_length=20,
        choices=SiteSyncStatus.choices,
        default=SiteSyncStatus.ACTIVE,
    )
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["source_name", "external_id"],
                name="unique_site_external_reference",
            )
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("site_detail", kwargs={"pk": self.pk})

    def get_access_records_url(self) -> str:
        return reverse("site_access_records", kwargs={"pk": self.pk})

    def get_history_url(self) -> str:
        return reverse("site_history", kwargs={"pk": self.pk})


class ArrivalMethod(models.TextChoices):
    ROAD = "road", "Road"
    BOAT = "boat", "Boat"
    HELI = "heli", "Helicopter"
    OTHER = "other", "Other"


class AccessRecordStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    RETIRED = "retired", "Retired"


class AccessRecord(models.Model):
    site = models.ForeignKey(
        Site,
        related_name="access_records",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=255)
    arrival_method = models.CharField(
        max_length=20,
        choices=ArrivalMethod.choices,
        default=ArrivalMethod.ROAD,
    )
    status = models.CharField(
        max_length=20,
        choices=AccessRecordStatus.choices,
        default=AccessRecordStatus.ACTIVE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["site__code", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "name"],
                name="unique_access_record_name_per_site",
            )
        ]

    def __str__(self) -> str:
        return f"{self.site} - {self.name}"

    def get_absolute_url(self) -> str:
        return reverse("access_record_detail", kwargs={"pk": self.pk})

    @property
    def current_version(self) -> AccessRecordVersion | None:
        return self.versions.order_by("-version_number").first()


class AccessRecordVersion(models.Model):
    access_record = models.ForeignKey(
        AccessRecord,
        related_name="versions",
        on_delete=models.CASCADE,
    )
    version_number = models.PositiveIntegerField()
    geojson = models.JSONField()
    change_note = models.TextField()
    uploaded_by = models.ForeignKey(
        "accounts.User",
        related_name="access_record_versions",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["access_record", "version_number"],
                name="unique_access_record_version_number",
            )
        ]
        indexes = [
            models.Index(
                fields=["access_record", "-version_number"],
                name="access_rec_ver_current_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.access_record} v{self.version_number}"


class AccessRecordUploadDraft(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="access_record_upload_drafts",
        on_delete=models.CASCADE,
    )
    site = models.ForeignKey(
        Site,
        related_name="access_record_upload_drafts",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    access_record = models.ForeignKey(
        AccessRecord,
        related_name="upload_drafts",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    file_name = models.CharField(max_length=255)
    geojson = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.file_name
