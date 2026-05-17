# API Tokens

API Tokens allow integrations to authenticate with the REST API.

Users create tokens from the user menu. Tokens are shown once at creation time
and are stored hashed.

## Key Fields

- Name
- Key prefix
- Write permission flag
- Expiry time
- Last used time
- Revoked time

Read-only tokens can call read endpoints. Tokens with write permission can call
write endpoints subject to normal API permissions and workflow validation.

Use the token header documented in [REST API](../integrations/rest-api.md).
