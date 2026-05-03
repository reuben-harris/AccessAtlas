## Tom Select

### Goal

Replace the current custom searchable-select enhancement with `django-tomselect`
across the app.

The current custom pattern is:

- a normal `<select>`
- a manually inserted search input from `static/js/app.js`

This feature should remove that pattern and move the affected fields onto Tom
Select instead.

### First-pass scope

Implement Tom Select for the fields that currently use the custom searchable
select behavior:

1. `SiteVisitForm.site`
2. `JobForm.site`
3. `JobFromTemplateForm.site`
4. `JobFromTemplateForm.template`
5. `TripForm.team_members`
6. `AssignJobForm.job`

Leave `TripForm.trip_leader` alone for now. Its current native select is
acceptable and does not need to be part of this first pass.

### Interaction goals

- `team_members` should move fully from checkbox list to a Tom Select
  multi-select.
- The selected team members shown inside the Tom Select control are enough; we
  do not need to preserve the old checkbox visibility.
- `team_members` should use the Tom Select `remove_button` plugin.
- Site and template fields should become searchable single-select Tom Select
  controls.

### Implementation shape

- Use `django-tomselect`: https://github.com/OmenApps/django-tomselect
- Do not use remote loading in the first pass.
- Use server-rendered option lists first.
- Preserve normal Django form submission and server-side validation.
- Preserve no-JS fallback where the native select still works if JavaScript
  fails.

### Explicitly out of scope for v1

- Remote / async autocomplete endpoints
- `input_autogrow`
- Styling polish beyond what is required to keep the controls functional
- Reworking `trip_leader`

### Functional requirements

- Tom Select must fully replace the custom searchable-select behavior on the
  migrated fields.
- Do not allow both enhancement systems to operate on the same field.
- Invalid form submissions must keep selected values.
- Existing validation and approval-reset flows must continue to work.

### Styling and theme

Function first.

The first pass should prioritize working behavior over visual polish. Once the
widget behavior is stable, do a follow-up pass for:

- Tabler alignment
- dark mode
- validation/focus states
- spacing and chip layout

### Testing

#### Python

- selected values save correctly for migrated fields
- invalid forms preserve submitted selections
- existing form validation still behaves correctly

#### Manual verification

- create/edit trip with team members
- create/edit site visit with site search
- create job with site search
- create job from template with searchable site/template fields
- validation errors still render correctly
- remove buttons work for team members
