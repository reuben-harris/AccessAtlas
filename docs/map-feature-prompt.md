# Access Records

## Purpose

Access Atlas should become the source of truth for site access information that
does not belong in the external site source of truth.

The current real-world workflow this replaces is split across two weak systems:

- KML tracks are uploaded to shared storage, with one folder per site code. This
  gives people a usable field file, but there is no meaningful version control,
  ownership, review trail, or maintenance workflow.
- Access instructions are written into a free-text description field in the
  asset/source-of-truth system. This keeps the notes close to the canonical site
  coordinates, but the field is not change-controlled and is hard to structure,
  validate, export, or reuse.

Access Records should combine the useful parts of both workflows:

- structured access information lives next to the site in Access Atlas
- access information is versioned
- users can upload and download practical field formats
- users can view the access information on a map
- Access Atlas does not become a GeoJSON editor or generic GIS system

## Product Boundary

Access Atlas owns the Access Record attached to a site.

The external site source of truth still owns canonical site identity and
site coordinates.

Access-start coordinates are owned by Access Record GeoJSON revisions so each
record can define its own start point.

## Core Decisions

- Each site can have multiple named Access Records.
- Updating an Access Record replaces the whole record.
- Previous versions are kept and can be downloaded.
- Uploads use GeoJSON.
- Downloads support GeoJSON and KML.
- KML export should include the track and points of interest where practical.
- Existing versions are not restored directly in the first implementation. A
  user can download an old version and reupload it as a new version.
- A change note is required for every upload, including the first upload.
- The Access Record feature is site-only for now. Trip pages should not
  surface this data until the site workflow is working and proven useful.
- Track geometry should be supported in the GeoJSON convention from the start.
  The first UI does not have to render or otherwise use track geometry, but
  uploaded tracks should be accepted, stored, preserved, and included in export
  workflows where practical.
- KML export can be implemented last because it is an isolated data
  transformation. Until it exists, the UI can include a disabled grey KML export
  button with a tooltip such as "Not yet implemented" so the page layout can be
  designed around the eventual action.

## Data Model Direction

The database should allow multiple Access Records per site. Each Access Record
represents one practical way to access the site, such as road, boat, heli,
walking, or another access method.

Access Record versions should hang off that record. The current version should
be derived from the highest `version_number`, not stored as a separate pointer.
This keeps the version history as the single source of truth and avoids a
possible out-of-sync `current_version` relationship.

The version table should enforce unique version numbers per Access Record and be
indexed for efficient current-version lookups.

Expected model shape:

```text
AccessRecord
  site
  name
  access_type
  is_active
  created_at
  updated_at

AccessRecordVersion
  access_record
  version_number
  geojson
  change_note
  uploaded_by
  created_at
```

Access Record names should be unique per site so a site cannot have two records
with the same user-facing name.

Store the full uploaded GeoJSON for each version. Derived data such as map
points, warning messages, and future KML output can be calculated from the
current version.

Warnings should start as derived checks against `Site` plus the current Access
Record version rather than stored warning rows. If global warning views or
performance needs become real, warnings can be cached later.

## User Workflows

### Upload A New Access Record

A user opens a site and uploads a GeoJSON file.

If the Access Record does not already have a version, this creates version 1.
The user must provide a change note.

If the Access Record already has a version, the upload replaces the whole
current record and creates a new version. The user must provide a change note.

### Download The Current Version

A user can download the latest access record as:

- GeoJSON, intended for editing in an external GeoJSON tool and reuploading
- KML, intended for Garmin or similar field-device use

GeoJSON download should be normalized by Access Atlas. Users should not have to
maintain style fields by hand. If a user uploads valid access data without
colors, or with stale colors, the downloaded GeoJSON should include the current
Access Atlas default styling.

KML export is deferred. The first UI can show the intended action as disabled.

### Download An Older Version

A user can download older versions for recovery, comparison, or manual restore.

The UI should make it obvious when the user is downloading an older version. This
should not sit in the same visual position as the latest-version download action.
Accidentally editing and reuploading old data should be hard to do without
noticing.

### View Access Data On A Site

The site page should expose the access record through site-specific views.

Expected site views:

- a map view that renders supported access features
- clickable points of interest on the map
- a parsed list/table of points of interest
- access warnings, shown clearly on the site page

The first map implementation may render point features only. Track geometry
should still be accepted, stored, preserved, and exported so it can be rendered
later without changing the core data model.

Example parsed point of interest:

| Type | Data |
| --- | --- |
| Gate code | `#1923 "Enter"` |

### Open In Google Maps

The site page should eventually have buttons for simple navigation workflows:

- open the access-start coordinates in Google Maps and start navigation
- open the access-start coordinates in Google Maps without starting navigation
- open the site coordinates in Google Maps

These actions depend on the relevant coordinates being available. If coordinates
are missing, the action should be disabled or hidden with clear feedback.

## GeoJSON Convention

Access Atlas should define a supported GeoJSON convention so uploaded data is
consistent enough to parse, display, validate, and export.

The convention should support:

- one or more access track geometries
- points of interest
- access-start point
- gate codes
- access notes
- labels/names
- estimated duration if useful

Gate codes should be a first-class point type so they can be parsed,
displayed, sorted, and eventually filtered. Generic notes should remain
available as a catch-all point type.

Initial `access_atlas:type` values:

- `access_start`
- `site`
- `gate`
- `note`
- `track`

Track features should support access suitability. Initial values, ordered from
most capable to least capable:

- `4wd`
- `luv`
- `walking`

The initial implementation should validate the uploaded file as GeoJSON and then
validate the Access Atlas-specific properties needed for supported features.
Track geometry should be accepted even if the first map/list UI only uses point
features.

The schema should be defined early, but Access Atlas is still pre-release. It is
acceptable to make breaking schema changes while actively testing if they improve
the long-term model.

Access Atlas should not provide in-app geometry editing. Users should edit
GeoJSON in their preferred external tool, then upload the updated file.

### Validation Strictness

Upload validation should be strict for semantic data and forgiving for
presentation data.

Block upload when:

- the file is not valid JSON
- the file is not a valid GeoJSON `FeatureCollection`
- a feature is missing geometry
- a supported feature is missing `access_atlas:type`
- `access_atlas:type` is unsupported
- coordinates are invalid
- a track has an invalid `suitability` value when suitability is provided

Do not block upload because of missing, stale, or incorrect style properties.

## Styling Convention

Access Atlas should own default map styling.

Users may upload GeoJSON with or without style properties. The app should not
depend on users keeping those style values correct. On download, Access Atlas
should add or refresh style properties using the current default styling rules.

Use common geojson.io-compatible style property names where possible:

- Point features:
  - `marker-color`
  - `marker-size`
  - `marker-symbol`
- Line features:
  - `stroke`
  - `stroke-width`
  - `stroke-opacity`

Road-end and site points should have distinct default colors. Other Access Atlas
point types should also have default colors.

Point symbols should help group the type of dot on the map. The symbol should be
app-owned in the same way as color, so users do not have to maintain it by hand
in uploaded GeoJSON.

Initial point symbol direction:

- coordinate anchor points:
  - `access_start`: road/parking/start style symbol
  - `site`: site/destination style symbol
- operational access points:
  - `gate`: gate/lock style symbol
- information points:
  - `note`: info/note style symbol

Downloaded GeoJSON should include `marker-symbol` values where practical, using
geojson.io/simple-style-compatible values. If a target editor does not render a
symbol, the color should still carry enough meaning for the point to be useful.

Track line color should indicate suitability:

- `4wd`
- `luv`
- `walking`

The exact color palette can change during pre-release testing. Because styling
is app-owned and refreshed on download, changing default colors later should not
require users to manually edit existing GeoJSON files.

## Site Feed Schema Changes

The site sync schema should only carry canonical site identity and site
coordinates. Site coordinates remain required in the site feed.

The access start is the practical start of access to the site. It may be a road
end, parking spot, helicopter landing zone, boat landing, or another operational
start point. Access Atlas does not currently track sites that do not need an
Access Record.

The dummy feed should include examples for site coordinate coverage only.

Example site feed item:

```json
{
  "external_id": "site-001",
  "code": "WLG001",
  "name": "Wellington Hill Site",
  "latitude": -41.2928,
  "longitude": 174.7517
}
```

### Possible Starter Shape

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [[174.1, -41.2], [174.2, -41.3]]
      },
      "properties": {
        "access_atlas:type": "track",
        "name": "Main access track"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [174.15, -41.25]
      },
      "properties": {
        "access_atlas:type": "gate",
        "label": "Main gate",
        "notes": "Use code #1923 then press Enter"
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [174.12, -41.22]
      },
      "properties": {
        "access_atlas:type": "access_start",
        "label": "Road end"
      }
    }
  ]
}
```

## Generated Starter GeoJSON

If a site has no uploaded access track yet, Access Atlas could generate a
starter GeoJSON file from known site data.

For example, if the source site feed provides an access-start coordinate and site
coordinate, Access Atlas could generate a simple file containing:

- an access-start point
- a site point
- no real track geometry yet

This would let a user download the starter GeoJSON, open it in an external
editor, draw the track between the access start and the site, and upload the
completed access record.

This is not required for the first implementation, but the data model and schema
should not make it difficult later.

## Validation And Warnings

Uploads should be blocked for invalid GeoJSON or unsupported shapes that Access
Atlas cannot safely parse.

Uploads should not be blocked because the access data disagrees with the
external source of truth. Instead, the site page should show a warning banner.

Example warning:

> GPS coordinates between the site source of truth and the uploaded access
> record do not line up.

Possible warning cases:

- site coordinate exists in the Access Record but is missing from the source feed
- access track endpoint is unexpectedly far from the site coordinate
- access track endpoint is unexpectedly far from the access-start coordinate
- access record is missing data needed for a feature such as navigation
- site has no active Access Records

Coordinate comparisons should be numeric, not string-based. Source-of-truth
site coordinates compared against equivalent GeoJSON site points should allow a
tiny rounding tolerance only. Track endpoint checks are different: they should
use a spatial distance threshold because a track may reasonably start or end a
short distance away from the canonical point.

All of these should use the same warning system. Missing source data, mismatched
coordinates, missing Access Records, and feature-specific missing data are
different warning types, but they are not separate warning classes from the
user's point of view.

Warnings should be visible on the site page. A broader warnings summary may be
useful later if warnings become common enough that opening each site individually
is not practical.

Possible future list behavior:

- a warnings column on the sites list
- filtering or sorting sites by warning state
- a site access health/status such as Good, Warning, or Partial

## History

The access record history should show:

- version number
- uploader
- upload timestamp
- change note
- download actions for that version

The change note is required for updates. It should explain why the access record
changed.

A future restore workflow could track that a new version was created from an old
version instead of relying only on the user's change note. For now, this is
deferred because manual download and reupload is simpler and likely rare.

## Deferred Ideas

These are intentionally out of scope for the first implementation, but should
remain visible as future design options:

- in-app GeoJSON or track editing
- AI-generated change summaries
- automatic diff summaries between versions
- restoring an old version directly
- route calculation
- trip-page access summaries
- global access warning dashboard
- richer access health/status across all sites
- full KML export implementation and device-specific KML tuning
