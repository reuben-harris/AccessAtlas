# Authentication

Access Atlas supports three authentication modes:

- `local`
- `oidc`
- `local-oidc`

Local login is passwordless and email-based. This is intentional for local
development and production-release smoke testing.

## Local Login

Users enter an email address and optional display name. Email is the stable
identity key. If a display name is absent, the UI falls back to email.

## OIDC Login

OIDC is configured with environment variables:

- `OIDC_PROVIDER_ID`
- `OIDC_PROVIDER_NAME`
- `OIDC_SERVER_URL`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_FETCH_USERINFO`
- `OIDC_PKCE_ENABLED`
- `OIDC_TOKEN_AUTH_METHOD`

Avoid custom auth adapters unless real provider testing proves the defaults are
insufficient.
