# Domain Model

This document defines the proof-of-concept domain model for Access Atlas.

The proof of concept is intentionally small. It focuses on the task side of field planning: trips, site visits, jobs, requirements, basic visibility, and the external site source-of-truth integration. Travel planning, access information, maps, tracks, offline trip packets, and spatial data are deferred until the core workflow has been tested.

This is not a database schema. Table names, column names, API shapes, and implementation details can come later.

## Proof Of Concept Model Summary

```text
Trip
  has many Site Visits

Site
  comes from an external source of truth
  is referenced by Access Atlas

Site Visit
  belongs to one Trip
  references one Site
  has many Jobs

Job
  references one Site
  may be unassigned
  may be assigned to one Site Visit
  has Requirements

Job Template
  creates Jobs
  has Template Requirements

Requirement
  belongs to one Job

Template Requirement
  belongs to one Job Template

Object History
  records changes to proof-of-concept objects
```

## Core Entities

### User

A person using Access Atlas.

Access Atlas owns the user record used for attribution and future authentication integration.

Likely fields:

- Email.
- Display name.
- Active state.

Notes:

- Email should be the unique login identifier.
- The proof of concept should not require passwords.
- Logged-in users can do everything in the proof of concept.
- The user model should be minimal but custom from the start so Microsoft organization SSO can be added later.

### Trip

A planned field deployment.

Access Atlas owns trips.

Likely fields:

- Name.
- Start date.
- End date.
- Trip leader.
- Team members.
- Status.
- Notes.

Relationships:

- A trip has many site visits.

Notes:

- A trip is the main planning container.
- The proof of concept does not need detailed travel planning.
- The proof of concept does not need day-by-day itinerary modeling.
- The proof of concept does not need trip locations such as hotels, depots, airports, or home base.

### Site

A managed field site from an external source of truth.

Access Atlas references sites but should not own canonical site identity, coordinates, or addresses.

Likely external fields:

- External source name.
- External site identifier.
- Site name.
- Coordinates if available.
- Address or location description if available.
- Status if available.

Access Atlas may store a snapshot:

- Display name at planning time.
- Coordinates at planning time if available.
- External reference at planning time.

Relationships:

- A site can have many jobs.
- A site can have many site visits over time.

Notes:

- Synced site fields are read-only in Access Atlas.
- If the external site changes, Access Atlas should refresh its reference.
- If the external site is deleted or unavailable, historic trips should remain understandable.
- Access Atlas should mark stale or missing site references rather than silently losing context.
- For early development, the site feed can point at the Django-served dummy feed before a real external adapter exists.

### Site Visit

A planned visit to one site during a trip.

Access Atlas owns site visits.

Likely fields:

- Trip.
- Site reference.
- Planned start.
- Planned end.
- Notes.
- Status.

Relationships:

- A site visit belongs to one trip.
- A site visit references one site.
- A site visit has one or more jobs.

Notes:

- A site visit represents one planned attendance at one site during a trip.
- A site visit groups the jobs planned for that attendance.
- A site visit should not be created without a site.
- Multiple site visits to the same site may exist if the plan requires returning later or splitting jobs across different days or times.
- Scheduled site visits are ordered by planned start. Unscheduled visits appear after scheduled visits.
- The proof of concept does not need access information or travel estimates.

### Job

A specific unit of work to complete at a site.

Access Atlas owns jobs.

Likely fields:

- Site reference.
- Title.
- Description.
- Estimated duration.
- Priority.
- Status.
- Notes.
- Created from template, if applicable.

Relationships:

- A job references one site.
- A job may be unassigned.
- A job may be assigned to one site visit.
- A job has zero or more requirements.

Notes:

- A job exists before and after trip assignment.
- An unassigned job is still a job, not a separate object type.
- A job may be created from a job template.
- Assigning a job to a site visit plans that job into a trip.
- A job should only be assigned to a site visit for the same site.

### Job Template

A reusable starting point for creating common jobs.

Access Atlas owns job templates.

Likely fields:

- Title.
- Description.
- Estimated duration.
- Priority.
- Notes.
- Active state.

Relationships:

- A job template can create many jobs.
- A job template has zero or more template requirements.

Notes:

- Job templates make repeated work easy to create once the system is set up.
- Creating a job from a template should copy the template fields into a new job.
- Creating a job from a template should copy template requirements into job requirements.
- Jobs should remain editable after creation from a template.
- Updating a job template should not silently change existing jobs that were created from it.

### Template Requirement

A reusable requirement attached to a job template.

Access Atlas owns template requirements.

Likely fields:

- Type.
- Name.
- Quantity.
- Notes.
- Required or optional.

Relationships:

- A template requirement belongs to one job template.

Notes:

- Template requirements are copied to job requirements when a job is created from a template.
- Template requirements are not shared live references on created jobs.

### Requirement

Something needed to complete a job.

Access Atlas owns requirements.

Examples:

- Tool.
- Part.
- Cable.
- Consumable.
- Permission.
- Site-specific note.
- Item already stored at site.

Likely fields:

- Type.
- Name.
- Quantity.
- Notes.
- Required or optional.
- Checked or confirmed state.

Relationships:

- A requirement belongs to one job.

Notes:

- Requirements are intended to reduce missed equipment or preparation.
- Requirements should be free-form in the proof of concept.
- A shared catalog of tools, parts, and consumables can come later if needed.

### Object History

A record of changes made to an object.

Access Atlas should expose object history in the application.

Implementation direction:

- Use `django-simple-history` unless a concrete incompatibility appears.
- Track history for proof-of-concept models where user changes matter.
- Attribute changes to the logged-in user.

Notes:

- History should make it clear who changed what and when.
- The proof of concept should expose history on object detail pages in a NetBox-like style.
- History is important because proof-of-concept permissions are intentionally broad.

## Proof Of Concept Planning Flow

1. Jobs exist for known sites.
2. Jobs may be unassigned.
3. A user creates job templates for repeated work.
4. A user creates jobs manually or from job templates.
5. A user creates a trip.
6. A user adds site visits to the trip.
7. A user assigns matching jobs to each site visit.
8. A user records or reviews job estimates, requirements, and notes.
9. A user updates simple statuses as planning progresses.

## Proof Of Concept Ownership Rules

Access Atlas owns:

- Trips.
- Site visits.
- Jobs.
- Job templates.
- Requirements.
- Template requirements.
- Object history.
- Planning state.
- Completion state.
- Job estimates.
- Notes.

External systems own:

- Canonical site identity.
- Canonical site coordinates.
- Canonical site addresses.
- Large files and photos.

Access Atlas may store references, links, and small snapshots where needed for planning and history.

## Proof Of Concept Assumptions

- A job always belongs to exactly one site.
- A site visit always references exactly one site.
- A site visit can contain multiple jobs.
- An unassigned job is a job with no site visit assignment.
- A job can only be assigned to a site visit for the same site.
- A job template is not tied to a single site.
- A job created from a template must still be assigned to one site.
- Template requirements are copied into job requirements when a job is created.
- Logged-in users can do everything in the proof of concept.
- History records should capture meaningful changes to proof-of-concept objects.
- A trip can have multiple site visits.
- A trip does not need trip locations in the proof of concept.
- A site visit does not need travel or access data in the proof of concept.

## Deferred Concepts

These concepts are intentionally deferred until after the core planning workflow is usable.

### Version 2 Candidates

- Trip days.
- Trip locations such as hotels, depots, airports, staging points, and home base.
- Text-based access information.
- Map-based planning.
- Basic travel estimates.
- Offline trip packets.

### Later Candidates

- Tracks.
- KML import/export.
- GeoJSON import/export.
- PostGIS-backed spatial storage.
- Advanced map filtering.
- Automatic nearby job suggestions.
- Calendar integrations.
- Native mobile apps.

## Open Decisions

These decisions need product input before implementation or before expanding beyond the proof of concept.

Status: deferred. Review these with the project owner the next time the domain model is discussed.

1. Can a job be split across multiple site visits, or should that require separate jobs?
2. Can multiple teams work on the same trip, or is one trip always one field team?
3. Should completed historic trips remain editable, or should they become locked once completed?
4. What approval states are needed after the proof of concept?
5. Should job requirements remain free-form, or should there later be a shared catalog of tools, parts, and consumables?
6. When trip days are introduced, should they be required for every trip or optional for more detailed planning?
7. When trip locations are introduced, should they be reusable across trips or copied into each trip?
8. When access information is introduced, should it belong to sites globally or be captured per site visit?

## Current Recommendations

These are working recommendations only. They should be reviewed before implementation.

1. Do not split one job across multiple site visits; create separate follow-up jobs instead.
2. Treat one trip as one field team for the initial model.
3. Lock completed trips by default, with an explicit reopen or admin correction path.
4. Start with simple statuses:
   - Trip: `draft`, `planned`, `completed`, `cancelled`.
   - Site Visit: `planned`, `skipped`, `completed`.
   - Job: `unassigned`, `planned`, `completed`, `cancelled`.
5. Keep job requirements free-form in the proof of concept.
6. Add trip approval later by extending trip statuses, for example with `planned_approved`, rather than building an approval workflow in the proof of concept.
