# Site Source Integration

This document defines the proof-of-concept integration contract for importing sites from an external source of truth.

The goal is to keep Access Atlas agnostic about where site data comes from. Access Atlas should consume a simple, versioned HTTP JSON feed. A separate adapter can read from a system such as NetBox and expose that data in the Access Atlas feed format.

## Design

Access Atlas does not integrate directly with NetBox or any other source-of-truth backend in the proof of concept.

Instead:

```text
External source of truth
  -> adapter controlled outside Access Atlas
  -> Access Atlas site feed endpoint
  -> Access Atlas sync
  -> local site references
```

Access Atlas only depends on the feed contract.

Synced site fields are read-only in Access Atlas. Canonical site identity, code, name, latitude, and longitude must be changed in the external source of truth or its adapter output, then synced into Access Atlas.

## Feed Endpoint

The proof of concept supports one HTTP endpoint. If `SITE_FEED_URL` is not set,
Access Atlas defaults to its own dummy site feed so a fresh deployment can be
used immediately with example site data.

```text
GET <configured-site-feed-url>
```

The endpoint must return JSON matching the schema below.

## Feed Schema

```json
{
  "schema_version": "1.0",
  "source_name": "netbox-production",
  "generated_at": "2026-04-20T10:30:00Z",
  "sites": [
    {
      "external_id": "12345",
      "code": "SITE-A",
      "name": "Site A",
      "latitude": -41.12345,
      "longitude": 174.12345
    }
  ]
}
```

## Required Fields

Top-level fields:

- `schema_version`
- `source_name`
- `generated_at`
- `sites`

Site fields:

- `external_id`
- `code`
- `name`
- `latitude`
- `longitude`

No optional fields are part of the proof-of-concept contract.

## Sync Behaviour

Access Atlas should fetch the configured feed and upsert local site references.

The unique identity of a site is:

```text
source_name + external_id
```

On sync, Access Atlas should update the local snapshot fields:

- Site code.
- Site name.
- Latitude.
- Longitude.
- Last seen timestamp.

If a site already exists, update the snapshot.

If a site is new, create it.

If a site is no longer present in the feed, do not delete it in the proof of concept. Existing jobs and site visits must remain readable.

Users must not edit synced site fields directly in Access Atlas.

## Validation

Access Atlas should reject a feed if required top-level fields are missing or if the schema version is unsupported.

Access Atlas should reject individual site records that are missing required fields or have invalid coordinates.

Coordinate validation:

- `latitude` must be between `-90` and `90`.
- `longitude` must be between `-180` and `180`.

## Authentication

Authentication is required for the feed.

The proof of concept should use a bearer token:

```text
Authorization: Bearer <token>
```

## Out Of Scope

The proof-of-concept integration does not include:

- Manual JSON upload.
- Optional metadata fields.
- Multiple feed endpoints.
- Pagination.
- Incremental sync.
- Webhooks.
- Plugin-based integrations.
- Writing data back to the source of truth.
- Deleting local site references when records disappear from the feed.
