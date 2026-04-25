# To-Do

This file is a rough thinking space, not a committed roadmap. Items here range from likely features to open questions to loose ideas.

## Core Workflow

- Improve the dashboard so it is more useful for day-to-day planning.
- Show assigned jobs more clearly from both the jobs list and job detail pages.
- Revisit whether trips should stay freely editable across status changes or become more locked down.
- Explore creating a new trip from an existing trip instead of encouraging heavy reuse of completed trips.

Questions:

- Should trip lifecycle be more rigid once work has progressed?
- Is a copy-from-existing-trip workflow enough to avoid messy reuse?

## Trip Lifecycle And Approval

- Revisit trip approval without introducing a heavy permissions model.
- Consider replacing manual trip status edits with more guided workflow actions.
- Keep thinking about how trip close-out, completion, and approval should fit together.

Questions:

- Is approval as simple as "someone other than the trip leader approves"?
- Should trip status changes become action-driven rather than freely editable?

Loose thoughts:

- Submit-for-approval could replace some manual status editing.

## Search, Filters, And Bulk Actions

- Improve global search:
  - clearer result presentation
  - better distinction between header and results
  - better object naming
  - counts for results
- Add richer filtering across the app in a lightweight way.
- Add bulk actions such as bulk edit and bulk cancel for jobs.
- Add sortable table columns where it improves grouping and scanning.

Questions:

- How much of the NetBox filter style is worth copying directly?
- Can filters stay fast and lightweight while still being expressive?

## Jobs And Requirements

- Revisit the job requirements UX. It is still not especially useful in practice.
- Explore a more checklist-like or summary-oriented requirement view.
- Add better requirement summaries at the trip level.
- Consider whether requirements should eventually become first-class reusable objects instead of only free text.
- Explore linking jobs to external ticketing systems in a generic way.
- Revisit job templates linking to SOP or instruction material, likely supporting multiple links.

Questions:

- Are requirements better as lightweight free text plus quantity, or as a stronger object model?
- What level should external ticket linkage live at?

Loose thoughts:

- "Default Requirements" may not be the right term.
- Action-style requirements such as "call Gerhard" feel awkward in the current model.

## Views And Navigation

- Keep refining alternate views across the app.
- Extend map filtering, for example by job type.
- Decide whether pages should remember the last selected view for a user.
- Improve navigation affordances when moving from a created object back to its parent list.

Questions:

- Should jobs reopen in the last-used view, such as the map?
- How much view state should be remembered per user?

Loose thoughts:

- Mermaid/domain-structure style navigation was once interesting but may no longer be worth prioritising.
- Gantt-style planning still needs clearer value before committing to it.

## Team And User Experience

- Refine team member selection when creating or editing trips.
- Keep an eye on how user identity data behaves once real OIDC testing happens.
- Confirm whether avatar initials should stay display-name-first with email fallback.

Loose thoughts:

- ClickUp-style multi-select tagging for team members still feels like a good fit.

## Reporting And Printouts

- Add a trip summary print/export flow.
- Include requirement summaries in a printable form.
- Consider whether printed views should emphasise packing/checklist workflows.

## Travel And Journey Planning

- Add journey planning only when it becomes worth the complexity.
- Think about route planning, accommodation, vehicle needs, and field logistics together rather than as isolated features.
- If this area grows, it should probably absorb things like road ends, access notes, and relevant contacts in a coherent model.

Questions:

- What is the minimum useful journey-planning slice?
- Which parts belong in site sync versus Access Atlas planning data?

## Integrations

- Weather integration
- Road closure integration
- Ticketing integration
- Possibly training or onboarding guidance later

Questions:

- Should these stay built-in for a while rather than jumping straight to plugins?
- What toggles or settings model would keep integrations manageable?

Loose thoughts:

- Training/workflow guidance as a plugin is still just an idea.

## Technical And Platform

- Revisit deployment ergonomics for database wiring and container runtime expectations.
- Simplify the Dockerfile if there is real cleanup value there.
- Keep validating that the container/deployment path feels straightforward for ECS-style deployment.

## Loose Ideas

- Better warnings or reminders for bookings and external trip tasks
- Remembering or surfacing operational prerequisites for certain trip types
- More holistic consistency work across the whole app

# Reubens thoughts for agent to tidy

## Pages List

* Tables need to be limited to 25
* The user should be able to go to the next page
* The number of pages should be dispalyed at the bottom
* The number of entries to show should be adjustable (default 25). With bigger options. 
* The enlarged search should add a ? parameter in the URL bar like netbox (assuming this is the best way to do that)

# Other

* Move the add site button to next to the site visit form (on the page when you open a trip http://localhost:8000/trips/1/)