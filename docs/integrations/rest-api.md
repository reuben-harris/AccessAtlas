# REST API

Access Atlas exposes a documented REST API under `/api/` for core planning
objects and workflow actions. API docs are available in the app header and at
`/api/schema/swagger-ui/`.

## Authentication

Users can create personal API tokens from the user menu. Tokens are shown once
at creation time, are stored hashed, can be revoked, and can be limited to
read-only access.

API requests authenticate with:

```http
Authorization: Token aat_<prefix>_<secret>
```

The API also supports session authentication so signed-in users can use the
interactive Swagger docs in a browser.
