from __future__ import annotations

from django.db import models
from django.urls import reverse
from simple_history.models import HistoricalRecords


class Site(models.Model):
    source_name = models.CharField(max_length=100)
    external_id = models.CharField(max_length=255)
    code = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    access_start_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    access_start_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
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


class AccessRecord(models.Model):
    site = models.OneToOneField(
        Site,
        related_name="access_record",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["site__code"]

    def __str__(self) -> str:
        return f"Access Record for {self.site}"

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
