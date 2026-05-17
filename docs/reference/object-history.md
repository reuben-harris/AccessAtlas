# Object History

Object History records who changed what and when.

Access Atlas uses `django-simple-history` for audit/history on core planning
objects and site/access objects.

## Where History Appears

- Global history page
- Object-specific history pages
- History detail pages with field-level differences

## Covered Objects

History is available for Sites, Access Records, Access Record Revisions, Site
Photos, Trips, Site Visits, Site Visit Job assignments, Job Templates, Work
Programmes, Requirements, Jobs, and related requirement templates.

API Tokens and User Preferences are operational records and do not have the same
Object History pages.
