from __future__ import annotations

import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import ApiToken

TOKEN_MARKER = "aat"


def generate_api_token_value() -> tuple[str, str]:
    """Return a lookup prefix and one-time plaintext token value."""
    key_prefix = secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12]
    secret = secrets.token_urlsafe(32)
    return key_prefix, f"{TOKEN_MARKER}_{key_prefix}_{secret}"


def lookup_prefix_from_token(value: str) -> str:
    parts = value.strip().split("_", 2)
    if len(parts) != 3 or parts[0] != TOKEN_MARKER:
        return ""
    return parts[1]


@transaction.atomic
def create_api_token(
    *,
    user,
    name: str,
    can_write: bool = False,
    expires_at=None,
) -> tuple[ApiToken, str]:
    key_prefix, plaintext_token = generate_api_token_value()
    token = ApiToken.objects.create(
        user=user,
        name=name.strip(),
        key_prefix=key_prefix,
        key_hash=make_password(plaintext_token),
        can_write=can_write,
        expires_at=expires_at,
    )
    return token, plaintext_token


def token_matches(token: ApiToken, plaintext_token: str) -> bool:
    return check_password(plaintext_token, token.key_hash)


def record_token_use(token: ApiToken) -> None:
    ApiToken.objects.filter(pk=token.pk).update(last_used_at=timezone.now())


def revoke_api_token(token: ApiToken) -> ApiToken:
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at", "updated_at"])
    return token
