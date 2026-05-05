## Site Photos

Add photo storage and display to site pages.

Photos are planning-owned records attached to a site. Site visit and trip
context are deferred for now so the first implementation stays focused on site
photo storage and browsing.

### Initial Implementation

* Add a `Photos` tab to the site detail page.
* Allow authenticated users to upload multiple photos for a site in one form
  submission.
* Store the original image and a thumbnail so gallery pages do not load full
  originals by default.
* Generate thumbnails synchronously during upload.
* Use image metadata to infer the date taken when available.
* Keep taken date blank when metadata does not include a usable date.
* Group dated photos by taken date.
* Put photos without a usable taken date into an `Unknown date` group after the
  dated groups.
* Show a clear indicator or warning for photos missing date-taken metadata so
  users understand why they are in the `Unknown date` group.
* Provide a simple gallery/lightbox view for browsing photos.
* Do not add date filtering in this pass. Date filtering should be handled by
  the broader filters feature later.
* Do not support manual reordering in the first pass.
* Do not add cover/preview usage elsewhere in the site UI in the first pass.

### Site Visit Association

Site visit linking is deferred.

Photos are attached only to sites in the first implementation. Site visit and
trip context can be added later once the core photo workflow is proven.

### Hide Instead Of Delete

Photos should not be hard-deleted through the normal UI.

Instead, users can hide photos. Hidden photos should disappear from the normal
site photo gallery. A later filters pass can add a way to review or restore
hidden photos if needed.

### History

Photo uploads and hide actions should create object history/audit events where
practical.

### Storage

Use Django's normal file storage abstraction.

* Development should use local filesystem storage by default.
* Deployment should support S3-compatible storage through environment variables.
* Do not require S3 or MinIO for normal local development.
* Add the relevant storage environment variables to `.env.example`, with comments
  separating Django settings from Access Atlas application settings.

Likely package direction:

* `django-storages` for S3-compatible deployment storage.
* Evaluate image/thumbnail handling before choosing a gallery package.
* A lightweight JavaScript gallery/lightbox is acceptable if image handling is
  handled cleanly elsewhere.

### Deferred

* Site visit linking.
* Trip context through site visits.
* Date range filtering.
* Hidden photo review/restore filters.
* Manual photo ordering.
* Captions or notes.
* Site or trip cover photos.
* Local S3-like development through MinIO.
* Background thumbnail generation.
