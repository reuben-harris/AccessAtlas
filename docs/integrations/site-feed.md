# Site Feed

Access Atlas consumes one configured HTTP JSON endpoint using bearer-token
authentication.

The feed is intentionally narrow. It upserts local Site references and keeps
synced site fields read-only in Access Atlas.

## Identity

The unique site identity is:

```text
source_name + external_id
```

Access Atlas does not write back to the upstream source of truth.

## Required Site Fields

- `external_id`
- `code`
- `name`
- `latitude`
- `longitude`

Optional fields include description and display tags.

## Sync Status

Sites present in the latest feed are active. Sites missing from the latest feed
are marked stale and remain visible for planning and history context.

> [!IMPORTANT]
> Do not make synced site identity, site code, site name, or coordinates editable
> locally. Those fields belong to the external source system.
