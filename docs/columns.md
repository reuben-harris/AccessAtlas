## Columns

* Make columns sortable in top-level table views
* Remember the selected sort order as a user preference for that page

### Agreed shape

* Start with top-level list pages only
* Use single-column sorting only
* Sorting should still be reflected in the URL
* If the user returns to the page with no explicit sort in the URL, use their saved sort preference for that page
* If the URL explicitly includes a sort value, that should win over the saved preference
* An explicit user sort choice should update the saved preference for that page
* Global History should use the same user-facing sorting behavior, but it does not need to become a true Django `ListView`
* Global History can be refactored into a class-based list-like custom view rather than forcing a queryset abstraction that does not fit the merged history stream

### Why this shape

* The URL keeps the current view state visible and shareable
* The saved preference makes the page feel consistent when the user comes back later
* Keeping sorting page-specific avoids surprising global behavior

### First scope

* Sites list
* Trips list
* Jobs list
* Job Templates list
* History list

### Recommended defaults and columns

* Sites
  * default sort: `code`
  * sortable columns:
    * code
    * name
    * source
    * sync status
* Trips
  * default sort: `start date`
  * sortable columns:
    * name
    * start date
    * end date
    * leader
    * status
* Jobs
  * default sort: `title`
  * sortable columns:
    * title
    * site
    * status
    * priority
    * estimate
* Job Templates
  * default sort: `title`
  * sortable columns:
    * title
    * priority
    * estimate
    * active
* History
  * default sort: newest first
  * sortable columns:
    * date
    * object
    * type
    * action
    * user

### Deferred

* Embedded child tables
* Multi-column sorting
* Column visibility or show/hide preferences
* Column reordering
