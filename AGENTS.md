# Agent Instructions

This project is Access Atlas, a domain-specific field work planning tool.

## Product Boundary

Keep the proof of concept small.

The first implementation should focus on the task side of field planning and the external site source-of-truth integration: trips, site visits, jobs, requirements, local site references, and basic visibility. The goal is to make the core workflow usable enough to steer the product before adding travel, access, maps, offline support, or spatial data.

The public README should stay concise, generic, and presentable. Keep detailed planning rationale, exclusions, and implementation memory in this file or in `docs/`.

## Domain Language

Use the proof-of-concept vocabulary consistently:

- `Trip`: a planned field deployment.
- `Site Visit`: a planned visit to one site during a trip.
- `Job`: a specific unit of work to complete at a site.
- `Job Template`: a reusable starting point for creating common jobs.
- `Unassigned Job`: a job that has not yet been assigned to a trip.
- `Requirement`: something needed to complete a job.
- `Object History`: records of who changed what and when.

Avoid using `task` as a product concept. It is too generic for this application.

Use `docs/domain-model.md` as the current working definition of the domain model. Update that document when product decisions change the meaning or relationship of core entities.

Use `docs/site-source-integration.md` as the current working definition of the external site source-of-truth feed. Keep the proof-of-concept contract narrow: one HTTP JSON feed, required fields only, bearer-token authentication, and local upsert of site references.

The domain model has deferred open decisions. When the user next asks to discuss the domain model, resume from the `Open Decisions` and `Current Recommendations` sections in `docs/domain-model.md` rather than starting over.

## Source Of Truth

Access Atlas should not own canonical site identity, coordinates, or addresses.

Those should come from an external source-of-truth system such as NetBox or another company system. Access Atlas may store references and small snapshots so historic trips remain understandable if the external source changes.

The app may integrate with different external systems depending on the organization. Do not hard-code the product story around one company or one source system, even if NetBox is a likely first integration.

Access Atlas owns proof-of-concept planning data:

- Trips.
- Site visits.
- Jobs and unassigned jobs.
- Job templates.
- Job estimates and requirements.
- Local site references synced from the configured site feed.
- Object history for proof-of-concept objects.
- Planning and completion state.
- Notes.

## Proof Of Concept Scope

Prioritize the proof-of-concept workflow:

1. Configure one external site feed endpoint.
2. Sync local site references from that feed.
3. Create and view trips.
4. Add site visits to a trip.
5. Create reusable job templates.
6. Create and review unassigned jobs, including jobs created from templates.
7. Assign jobs to site visits.
8. Record job estimates, notes, and requirements.
9. Track simple statuses for trips, site visits, and jobs.
10. Show object history so changes can be attributed to users.
11. Provide basic visibility for team leaders and managers.

## Deliberately Out Of Scope For The Proof Of Concept

Do not introduce these unless the user explicitly changes direction:

- Generic task management.
- Manual JSON site upload.
- Optional site feed metadata fields.
- Multiple site feed endpoints.
- Incremental site sync.
- Webhook-based site sync.
- Plugin-based source-of-truth integrations.
- Writing data back to the source of truth.
- Deleting local site references when they disappear from the feed.
- Custom user-defined views.
- Advanced filtering systems.
- Board or Gantt layouts.
- Automatic nearby job suggestions.
- Calendar integrations.
- Native mobile apps.
- Direct storage of photos or large files.
- Replacing the external site source of truth.
- Editing canonical site coordinates or addresses.
- Editing synced site code, name, latitude, or longitude in Access Atlas.
- Trip days.
- Trip locations such as hotels, depots, airports, staging points, and home base.
- Travel planning.
- Travel estimates.
- Access information.
- Tracks.
- KML import/export.
- GeoJSON import/export.
- PostGIS-backed spatial storage.
- Map-based planning.
- Offline trip packets.

Also avoid presenting these excluded features prominently in the public README. They are agent memory and product guardrails, not user-facing marketing copy.

## UX Principles

The app should feel like a practical planning tool for field technicians and team leaders.

For the proof of concept, prefer boring object pages over rich planning interfaces. The goal is to validate the source-of-truth integration and core workflow before investing in maps, travel planning, or offline features.

The UI should copy the broad NetBox layout pattern: persistent left navigation, top search, and consistent object list/detail/edit pages. The proof of concept must support light and dark mode, preferably through Tabler's built-in theme support.

When adding UI, keep the first screen useful. Do not build a marketing landing page unless explicitly requested.

## Engineering Notes

Use `docs/architecture.md` as the current working architecture direction.

Access Atlas is a Django server-rendered application using PostgreSQL as the primary database, Tabler for layout, and HTMX for focused partial updates.

The project is licensed under `AGPL-3.0-or-later`. Preserve the license choice unless the user explicitly changes it.

The intended GitHub remote is `git@github.com:reuben-harris/AccessAtlas.git`.

When scaffolding the Django app, include `pyproject.toml`, `.python-version`, VS Code debugger support, GitHub Actions CI, and Dependabot from the start. Add the GHCR container image workflow with the rest of the GitHub Actions once the proof-of-concept app and Dockerfile exist; do not add it before then. Use Python 3.14 and Django 6.0 unless the user explicitly changes direction. CI should use current official action majors: `actions/checkout@v6` and `actions/setup-python@v6`.

Use a minimal custom user model with email as the unique identifier. For the proof of concept, authentication can be passwordless/internal: users identify by email and then can access the app. Logged-in users can do everything. This broad permission model requires history/audit records for important object changes. Prefer `django-simple-history` for model history unless a concrete incompatibility appears.

Configure the site feed URL and token via environment variables. The Django-served dummy feed endpoint should require the bearer token too.

Do not introduce React by default.

Vite, TypeScript, Stimulus, Biome, Leaflet, and PostGIS are deferred until the project needs them. If map features are introduced, Leaflet is the current preferred first mapping library. If structured browser-side code is introduced, revisit Vite, TypeScript, Stimulus, and Biome rather than drifting into unstructured standalone JavaScript.

Large files and photos should normally live in external storage such as SharePoint or S3-compatible systems. The proof of concept does not need to implement file/photo storage.
