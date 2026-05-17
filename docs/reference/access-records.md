# Access Records

Access Records describe routes or methods for reaching a Site.

## Access Record

An Access Record belongs to one Site and has a name, arrival method, status, and
versioned GeoJSON revisions.

Arrival methods are road, boat, helicopter, or other.

Statuses are active and retired.

## Access Record Revisions

Each revision stores GeoJSON, a change note, the uploading user, and a version
number. The newest revision is the current access route for display and maps.

Access-start coordinates are owned by Access Record revision GeoJSON, not by the
Site feed.

## Upload Drafts

Upload drafts temporarily hold GeoJSON during the review workflow. They are
owned by the uploading user and are not part of Object History.
