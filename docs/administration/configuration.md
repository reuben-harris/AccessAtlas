# Configuration

Runtime configuration is supplied through environment variables. Local
development usually starts from `.env.example`.

## Core Settings

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL`

Access Atlas uses PostgreSQL for normal development and deployment. SQLite is
available through Django defaults for narrow local checks, but PostgreSQL is the
primary database target.

## Application Settings

- `SITE_FEED_URL`
- `SITE_FEED_TOKEN`
- `BUG_REPORT_URL`
- `MAP_ARCGIS_API_KEY`
- `MAP_TRACESTRACK_API_KEY`

See [Map Layers](map-layers.md) for optional map provider setup and
[Site Feed](../integrations/site-feed.md) for feed details.

## Uploaded Media

Uploaded media can use local filesystem storage or S3-compatible storage.

- `MEDIA_STORAGE_BACKEND=local` uses `MEDIA_ROOT` and `MEDIA_URL`.
- `MEDIA_STORAGE_BACKEND=s3` requires `AWS_STORAGE_BUCKET_NAME`.
