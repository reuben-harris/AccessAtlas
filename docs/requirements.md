## Jobs And Requirements

- Revisit the job requirements UX. It is still not especially useful in practice.
- Explore a more checklist-like or summary-oriented requirement view.
- Add better requirement summaries at the trip level.
- Consider whether requirements should eventually become first-class reusable objects instead of only free text.
- **Explore linking jobs to external ticketing systems in a generic way.**
- Revisit job templates linking to SOP or instruction material, likely supporting multiple links.

Questions:

- Are requirements better as lightweight free text plus quantity, or as a stronger object model?
- What level should external ticket linkage live at?

Loose thoughts:

- "Default Requirements" may not be the right term.
- Action-style requirements such as "call Gerhard" feel awkward in the current model.

* **add a tab to the Trip page with a table with all the requirements**
* **Add a tab to the trip page for requirements. ALlow clickup style checklist (currently is checked is represented as a status so consider changing this)**

## Notes / concerns to lock down before implementation

### Recommended first scope

Keep the first pass narrow:

1. Add a `Requirements` tab on Trip detail.
2. Show a flat table of all requirements across the trip's jobs.
3. Improve requirement readability and completion handling there.
4. Do not redesign the full requirement data model yet.

That gives you a useful planning surface without committing to a larger object-model rewrite.

### Main concern: UX improvement vs data-model rewrite

The document currently mixes:

- a near-term UX improvement:
  - trip-level visibility
  - checklist-style interaction
- and larger future model questions:
  - reusable requirement objects
  - external ticket linkage
  - richer SOP/instruction relationships

Those should stay separate. My recommendation is:

- **v1:** trip-level requirement tab and better checklist UX
- **later:** reusable requirement model and external system links

### Checklist behavior needs one decision

Right now "checked" is represented through a broader status concept. If you want a ClickUp-style checklist feel, decide whether:

1. requirements become simple `done / not done`
2. requirements keep a richer status enum

My recommendation:

- keep the existing status field in the data model for now
- present it in the UI as a simpler checklist-style interaction if the status space is still effectively binary in practice

That avoids a migration until you are sure you want to simplify the model.

### Trip-level table shape

I recommend the Trip `Requirements` tab show:

- requirement text
- job
- site
- quantity (if present)
- status
- maybe notes/context if short

And I would keep it as a plain table first, not a card/checklist mosaic.

### External ticket linkage should not be part of the first pass

This is a separate feature. It needs decisions about:

- whether links belong to jobs, requirements, or both
- whether there is one external link or many
- whether the integration is just URL storage or structured provider-aware linkage

My recommendation:

- leave external ticketing out of the requirement UX implementation

### Reusable requirement objects should stay deferred

The document asks whether requirements should become first-class reusable objects. That is worth discussing later, but I would not let it block the usability work now.

Reason:

- reusable objects introduce naming, deduplication, template coupling, and migration questions
- the current pain sounds more like visibility and interaction than normalization

### Open questions I would want answered before coding

1. Should the Trip `Requirements` tab be read-only summary first, or directly editable?
   - My recommendation: directly editable for status only in v1. -> make it directly editable table. I want a column that has the is checked as a checkbox in the row. The user can click this checkbox and it updates the db

2. Should checklist completion update the underlying existing status field?
   - My recommendation: yes. -> I think we should look to merge the status and is checked into one thing

3. Should requirements be grouped by site visit, by job, or just one sortable table?
   - My recommendation: one sortable/filterable table first. -> yes

4. Should completed requirements be visible by default?
   - My recommendation: yes, but allow quick filtering later if needed. -> yes

## My Notes

-> Ok lets break this down into two features and focus on the UX overhaul first.