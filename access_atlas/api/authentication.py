from __future__ import annotations

from rest_framework import authentication, exceptions

from .models import ApiToken
from .token_services import lookup_prefix_from_token, record_token_use, token_matches


class ApiTokenAuthentication(authentication.BaseAuthentication):
    keyword = "Token"
    bearer_keyword = "Bearer"

    def authenticate(self, request):
        authorization = authentication.get_authorization_header(request).split()
        if not authorization:
            return None
        if authorization[0].decode().lower() not in {
            self.keyword.lower(),
            self.bearer_keyword.lower(),
        }:
            return None
        if len(authorization) != 2:
            raise exceptions.AuthenticationFailed("Invalid API token header.")

        plaintext_token = authorization[1].decode()
        key_prefix = lookup_prefix_from_token(plaintext_token)
        if not key_prefix:
            raise exceptions.AuthenticationFailed("Invalid API token.")

        try:
            token = ApiToken.objects.select_related("user").get(key_prefix=key_prefix)
        except ApiToken.DoesNotExist as exc:
            raise exceptions.AuthenticationFailed("Invalid API token.") from exc

        if not token_matches(token, plaintext_token):
            raise exceptions.AuthenticationFailed("Invalid API token.")
        if not token.is_usable:
            raise exceptions.AuthenticationFailed("API token is expired or revoked.")

        record_token_use(token)
        return token.user, token

    def authenticate_header(self, request):
        return self.keyword
