## Site photos

* Hook into an s3 backend for storage of files (when in a deployment scenario)
* Display site photos at a site
* Add a new tab for photos. Investigate if there are any out of the box django or good js viewers like. https://github.com/codingjoe/django-pictures
* Allow filtering by date. Organsie photos by date uploaded (we can assume same date same site visit)
* Build in functionaltiy were users can tag photos and associated them with a site visit
* Photos without a tagged site visit just display the date and unknown site visit were as photos with an assocaited site visit display the site visit and the date.
* I like the photo grouping the google photos uses
* Ask agent if its best to pin the photos to a trip or site visit. I am leaning on trip for simplicity
* How does dev work with s3 backend? I assume I can add to docker compose file?
* Use django storages and update default backend with an env
* env for file path (s3 or local)

## Notes / concerns to lock down before implementation

### Main architectural decision: what photos belong to

This is the most important question in the doc.

The candidates are:

1. Site
2. Trip
3. Site Visit

My recommendation:

- **photos should belong to a Site as the primary object**
- **Site Visit should be optional metadata**
- **Trip should be derivable through the Site Visit when present**

Reason:

- the photo's long-lived value is usually tied to the site
- a trip is operational context, not the core identity of the image
- site visit tagging is still useful for planning/history context

So I would not pin photos to Trip as the primary relation.

### Recommended first scope

Keep v1 narrow:

1. add a `Photos` tab on Site detail
2. upload photos against a Site
3. optionally tag a Site Visit
4. group by upload date
5. simple gallery/lightbox viewing
6. local file storage in development, S3-compatible storage in deployment

That is enough to prove the feature without dragging in bulk media management.

### Storage approach

Your note about `django-storages` is the right direction.

My recommendation:

- use Django's normal `FileField/ImageField`
- use storage backend switching via settings/env
- local filesystem in development
- S3-compatible backend in deployment

That means:

- **do not** make Docker Compose depend on S3 for normal local development
- instead keep dev local-first and let deployment switch to S3 through env

If you want an S3-like local test target later, MinIO is the usual answer, but I would not make it part of v1.


-> yes to the recommendation
### Grouping and filtering

Google Photos-style grouping is a good inspiration, but I would keep the first implementation simple:

- group by upload date
- filter by date range later if needed

I would not try to replicate a sophisticated photo-product layout in the first pass.

-> agreeded. Lets not even have filter by date yet (planning on doing a massive filter pass on the whole website so can include it in that feature). Lets just group by upload date

### Site Visit association rules

The doc assumes:

- same upload date probably means same site visit

I would not encode that as a rule.

My recommendation:

- uploaded date is just uploaded date
- site visit association is explicit metadata, optional
- if absent, show:
  - date
  - `No site visit`

That is safer than inferring operational context from upload date.

-> I want to use the photo meta data and date taken to infer taken date. These days with phones this is often accruate.

### Image processing / display concern

Before implementation, decide whether you want:

1. original file only
2. original + derived thumbnail

My recommendation:

- generate/store thumbnails or use a library that does this well

Reason:

- galleries become expensive quickly if every page pulls full originals

This is the part where a package choice matters.

-> lets have thumbnails to ensure the website remains fast

### Package/library concern

The doc mentions `django-pictures`. I think it is worth evaluating, but the more important capability is:

- image derivatives / responsive output
- sane template helpers

The gallery/lightbox itself can also be solved separately with small JS if needed.

So I would evaluate packages based on image handling first, not just gallery presentation.

### Permissions and workflow

Before coding, decide:

1. who can upload
2. who can delete
3. whether uploads should be recorded in object history

My recommendation:

- same authenticated users who can edit planning data can upload/delete
- record photo create/delete in object history if practical

-> Like the rest of the site, I think we want to avoid deleting anything. Lets instead opt for a hidden feature were you can hide photos. Maybe the hidden photos can later be seen with a filters feature.

-> anyone authetnicated can upload throught the website

-> uploads should have a histroy event.

### Open questions I would want answered before coding

1. Should photos be reorderable manually?
   - My recommendation: no.

2. Should captions/notes exist in v1?
   - My recommendation: optional short caption later, not required in v1.

3. Should the first photo appear elsewhere in the site UI as a cover/preview?
   - My recommendation: no, not in the first pass.
