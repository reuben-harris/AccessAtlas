# Agent Instructions

This project is Access Atlas, a field work planning application.

## Product Summary

Access Atlas plans field work around externally managed sites.

The application owns:

- Trips
- Site visits
- Jobs and unassigned jobs
- Job templates
- Job requirements
- Notes
- Object history
- User preferences

The application does not own canonical site identity or coordinates. Those come from a configured external site feed and remain read-only inside Access Atlas.

## Domain Language

Use the product language consistently:

- `Trip`: a planned field deployment
- `Site Visit`: a planned attendance at one site during a trip
- `Job`: a unit of work for a site
- `Unassigned Job`: a job not yet planned into a site visit
- `Job Template`: a reusable starting point for a job
- `Requirement`: something needed to complete a job
- `Object History`: who changed what and when

Avoid `task` as a product term unless the user explicitly chooses it for a new feature.

## Ownership Boundaries

Access Atlas should stay agnostic about the upstream source of truth.

External systems own:

- Site identity
- Site code
- Site name
- Coordinates
- Address or canonical location details

Access Atlas owns planning-specific data:

- Trips
- Site visits
- Jobs
- Templates
- Requirements
- Planning status
- Notes
- Audit/history records

Model and service layers should own business rules and state transitions. Forms should handle input shape and presentation, not duplicate core validation logic that already belongs to models or services.

Site-visit planned time validation is a known exception to revisit carefully.
The model owns the scheduling rules, but the form currently mirrors some of that
logic so browser input problems surface as clear field errors instead of silently
saving an unscheduled visit. If this pattern grows, extract a shared validation
helper rather than letting model/form rules drift apart.

## Current Architecture Defaults

- Django server-rendered application
- PostgreSQL primary database
- Tabler for layout and UI foundation
- Light/dark theme support
- HTMX where partial updates improve the workflow
- Minimal custom user model with email as the unique identifier
- `django-simple-history` for audit/history
- `django-allauth` wired for OIDC support
- Local development runs Django directly and PostgreSQL through Docker Compose

Prefer the existing Django/template approach unless a new feature clearly needs more client-side structure.

## Auth Notes

- Auth modes:
  - `local`
  - `oidc`
  - `local-oidc`
- Local login is passwordless and email-based.
- OIDC is configured through environment variables.
- Email is the stable identity key.
- Avoid adding custom auth adapters unless real provider testing proves the defaults are insufficient.
- If display name is absent, the UI should fall back cleanly to email.

## Site Feed Contract

Keep the site feed narrow:

- one configured HTTP JSON endpoint
- bearer-token authentication
- required fields only
- upsert local site references

The unique site identity is `source_name + external_id`.

Do not add direct write-back to the source system unless the user explicitly changes direction.

## UX Conventions

- Keep the NetBox-style layout: left navigation, top search, consistent object pages.
- Prefer practical object pages over elaborate planning surfaces unless the user explicitly asks to expand them.
- Preserve a consistent feel across list, detail, and edit views.
- Status, history, and planning relationships should be visible without requiring deep navigation.
- When adding or reorganizing CSS, include concise comments around sections or non-obvious rules so a human can navigate the stylesheet quickly later.
- When adding or changing non-trivial Python logic, include concise comments or docstrings around workflow-heavy code paths, adapter layers, or policy decisions so a Django engineer can understand why the flow exists without reverse-engineering it from tests.
- Apply the same standard to JavaScript: add concise comments around non-obvious state flow, third-party library integration points, preference persistence, and rendering adapters. Avoid narrating obvious DOM reads, loops, or event wiring.

## Active Constraints

These are current guardrails, not permanent doctrine:

- Do not turn Access Atlas into generic task management.
- Do not let synced site fields become editable locally.
- Keep source-of-truth integration simple and feed-based.
- Prefer stable, boring implementation choices over speculative abstractions.
- When the public docs and the app diverge, update the docs to match the current app.

## Deferred Areas

These exist as future discussion topics, not active commitments:

- Richer trip approval workflow
- Bulk actions and richer filtering
- Additional planning views beyond the current object pages and map view
- Journey and travel planning
- Reporting/print views
- External operational integrations
- More structured frontend tooling if the client-side surface grows significantly

## Documentation Strategy

The public `README.md` should stay concise and current.

Use `AGENTS.md` as the long-lived internal memory file for product language, architectural defaults, guardrails, and deferred decisions. Avoid scattering that material across user-facing docs unless it helps a real human reader right now.

## Repository Workflow

Use conventional commit messages for commits unless the user explicitly asks for something else.

When implementing a feature in incremental passes, keep the initial feature
changes uncommitted until the small follow-up tweaks/fixes are done, then fold
those tweaks into the same feature commit instead of creating extra fix commits.

When a follow-up tweak reaches beyond the new feature and adjusts an existing
shared element in its own right, split it into a separate commit. A good rule
is: keep required feature-completion fixes with the feature, but separate
standalone shared polish so history stays easier to review and revert.

Do not mix unrelated maintenance changes into a UI or feature fix commit.
Dependency automation, CI, docs-only updates, and unrelated shell/layout fixes
should stand on their own even when they are each small. If reverting one part
would reasonably be useful without reverting the other, the changes belong in
separate commits.

After modifying Python files, run the Python lint/check pass before finishing
the change. At minimum, run both `ruff check` and `ruff format --check`
against the touched Python scope; run broader project checks when the change
reaches shared behavior.

When a change touches Python behavior in a way that could affect tests, run
`uv run pytest` before finishing if the local environment can support it. If
pytest cannot run because the database or sandbox environment is blocking it,
note that explicitly instead of implying the test pass is covered.

When modifying existing commented logic, update the comments at the same time.
Stale comments are worse than no comments. Prefer short orienting comments that
explain policy or flow over narration of obvious line-by-line behavior.

For helper functions, prefer docstrings when the function defines a reusable
contract, policy decision, or input/output expectation that an IDE tooltip
would genuinely help with. Skip docstrings for tiny obvious helpers unless the
name cannot carry the intent on its own.

## Planning Workflow

For larger agreed feature sets, keep an active checklist and update it as work
progresses. If new prerequisite or cleanup items are discovered, add them ahead
of the remaining checklist items rather than losing the original sequence. This
helps preserve the agreed feature direction while still adapting to discoveries
made during implementation.
