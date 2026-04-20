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
