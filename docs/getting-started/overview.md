# Overview

Access Atlas helps teams plan field deployments against sites that come from an
external source of truth.

The app is organised around a small set of planning objects:

- Trips group planned field deployments.
- Site Visits record attendance at one site during a Trip.
- Jobs describe work to complete for a site.
- Work Programmes group Jobs into dated batches.
- Job Templates provide reusable starting points.
- Requirements capture tools, parts, permissions, notes, and other needs.
- Access Records describe local site access routes or methods.

Sites are synced into Access Atlas as read-only references. Local users can plan
against them, attach Access Records and photos, and review history, but they do
not edit canonical site identity or coordinates inside Access Atlas.

## Application Shape

Access Atlas is a Django server-rendered application with PostgreSQL, Tabler,
HTMX, `django-simple-history`, and `django-allauth` for optional OIDC login.

The UI follows a NetBox-style shell: left navigation, top search, object list
pages, object detail pages, edit forms, maps, and history views.

## Common Workflow

1. Sync sites from the configured feed.
2. Create or import Job Templates.
3. Create Work Programmes and Jobs.
4. Plan Trips and Site Visits.
5. Assign Jobs to Site Visits.
6. Submit and approve Trips when approval is needed.
7. Close out field work and review Object History.
