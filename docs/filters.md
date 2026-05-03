## Filters

* Add filter functionality to Trips, Jobs and Sites Lists
* The filters functionality should sit below the custom views. Currently only jobs has custom views and it would sit below Table and Map buttons.
* I like the quick access of the filters on the map page. I want to somehow keep this easy access while extending the feature
* The job status filter on the maps page should be moved into this site wide filters feature. This would mean these filters apply to now both the table and map view.
* [Have the ability to filter with more advance logic the same as this netbox feature](https://github.com/netbox-community/netbox/issues/7604)
* Filters save to the users preferences so if they leave and revisit the page the filters remain
* Sites page gets a default filter that excludes stale sites
* I like the quick access of the job status filters on the map page currently. This should be retained somehow. I also would like those filters to show on the fullscreen map if possible (and try it out maybe its not a good idea)

### Agent notes and questions

* This feature should probably be split into two layers:
  * a shared simple filter bar that most users interact with
  * a more advanced expression or logic builder later if it is still needed
* I would not start with NetBox-style advanced logic. That is a larger feature in its own right and will complicate the simple filter workflow if introduced too early.
* The current jobs map status toggles should become part of the shared Jobs filters model, but the quick access can still remain as shortcut controls on the map page.
* If map and table share the same filter state, the filter state should be stored once per page and then applied to both views consistently.
* Filter state should probably still be reflected in the URL even if a saved user preference exists. The URL should remain the visible source of the current view state.
* Saved preference should be the fallback when the user returns to the page without explicit filter parameters in the URL.
* Sites default filter excluding stale sites makes sense, but we should decide whether:
  * the default is only applied when the user has no saved preference and no URL filter
  * or whether it is always applied unless the user explicitly asks to see stale sites
* My recommendation is the first option. Defaults should not silently override an explicit user choice.
* First implementation should likely cover:
  * Jobs
  * Sites
  * Trips
* Embedded child tables should stay out of scope initially.
* We should decide whether filters only narrow the current list page, or whether dashboard shortcuts and other links can deep-link directly into filtered views.
* My recommendation is yes: dashboard and other workflow shortcuts should open these filtered list or map views directly.

### Recommended first scope

* Jobs
  * shared filters across table and map
  * keep quick status buttons on the map as a shortcut into the same shared state
* Sites
  * include default hide-stale behavior
* Trips
  * basic field filters only

### Deferred

* advanced boolean logic builder
* embedded child-table filters
* very large filter sets or saved named filters


# new notes
* Filter site photos by date
* Ability to filter history by user