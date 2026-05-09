from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import ApiToken


class ApiTokenWritePermission(BasePermission):
    message = "This API token is read-only."

    def has_permission(self, request, view) -> bool:
        token = getattr(request, "auth", None)
        if not isinstance(token, ApiToken):
            return True
        return request.method in SAFE_METHODS or token.can_write
