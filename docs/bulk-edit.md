## Bulk Edit

* Add checkboxes on the far left of tabler views to allow a user to select multiple rows. Do this were there is already a edit button on the row.
* Add a bulk edit button down the bottom right of the tabler view were a user can select multiple entries
* Add checkboxes on the map view under jobs. When you open the tool tip/popup you can select job by job or all jobs

### Refinement notes

* Do not treat bulk edit as a generic feature across every object type at first. The safest first implementation is Jobs only.
* Sites should stay out of scope because synced site fields are read-only.
* Trips should be reviewed separately later because trip state changes have stronger downstream workflow effects.
* Treat the first pass as bulk field update, not bulk workflow automation.
* Jobs list is the best first surface.
* Jobs map selection can follow once the list-based workflow is solid.

### Recommended first scope

* Jobs list:
  * checkbox column
  * selected count
  * bulk edit button
  * dedicated bulk edit form or page
* Jobs map later:
  * select individual jobs from the popup
  * select all jobs shown in the popup for that site

### Recommended rules

* List and map should eventually share the same selected Job IDs in the current browser session
* Bulk updates should be all-or-nothing for a submission
* Mixed current values should appear as blank or unchanged in the bulk edit form
* Only fields the user explicitly sets in the bulk edit form should be updated

### Candidate Job fields for a first pass

* status
* priority
* estimated duration
* possibly notes

### Avoid in the first pass

* bulk site reassignment
* site visit assignment changes
* more complex workflow transitions hidden inside bulk edit
