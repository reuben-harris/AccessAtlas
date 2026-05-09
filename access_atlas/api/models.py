from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class ApiToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="api_tokens",
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=120)
    key_prefix = models.CharField(max_length=24, unique=True)
    key_hash = models.CharField(max_length=255)
    can_write = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        indexes = [
            models.Index(fields=["user", "revoked_at"], name="api_token_user_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.user})"

    @property
    def is_expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= timezone.now()

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    @property
    def is_usable(self) -> bool:
        return self.user.is_active and not self.is_expired and not self.is_revoked
