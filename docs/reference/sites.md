# Sites

Sites are synced references to real-world sites from an external source of
truth.

## Ownership

External systems own site identity, site code, site name, coordinates, address,
and canonical location details. Access Atlas stores synced copies for planning
context and keeps them read-only in the app.

Access Atlas owns planning relationships, Access Records, photos, Jobs, Site
Visits, and history that refer to a Site.

## Key Fields

- Source name and external ID identify the upstream record.
- Code and name are display fields from the source feed.
- Latitude and longitude place the Site on maps.
- Sync status records whether the Site is active or stale.
- Tags are source-provided display badges.

## Related Objects

Sites can have Access Records, Site Photos, Jobs, and Site Visits.

Object History records synced field changes so users can see when source data
changed inside Access Atlas.
