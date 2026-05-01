## Pages List

* Tables across the website need to be default limited to 25
* The user should be able to go to the next page
* The number of pages should be dispalyed at the bottom
* The number of entries to show should be adjustable (default 25). With bigger options.
* The enlarged search should add a ? parameter in the URL bar like netbox (assuming this is the best way to do that)

### Agreed scope

* Apply this to top-level list pages first, not embedded child tables
* Default page size is `25`
* The page-size UI should offer `25`, `50`, and `100`
* The backend should still accept any manual `per_page` value from the URL
* `per_page` is URL-driven only, not a saved user preference
* Use numbered page links at the bottom, not just previous/next
* Embedded tables can be reviewed later case by case after the initial rollout
